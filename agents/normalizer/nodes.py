"""Normalizer graph nodes — Prompts + Sampling via Medical Lang Bridge (SSoT §5.3).

Beginner picture:
  - No direct LLM calls here. We call the Medical Lang Bridge MCP tool.
  - That tool Sampling-asks our sampling_callback to run LiteLLM.
  - We pass the MCP prompt body as `instructions` (system_prompt).
  - After Sampling: expand abbrev / canonicalize meds / ICD-10 (§6.2, §12.3).
  - Primary languages from rules.yaml; unexpected → fallback note.
"""

from __future__ import annotations

import json

from fastmcp import Client

from agents.normalizer.sampling_callback import sampling_callback
from agents.normalizer.state import NormalizerState
from shared.clinical_normalize import post_normalize_extraction
from shared.language import (
    detect_source_language,
    get_primary_language_codes,
    is_english,
    language_path,
    normalize_lang_code,
)
from shared.logger import get_logger
from shared.models.normalization import NormalizationResult
from shared.settings import get_service

logger = get_logger("normalizer")


def _primary_mcp_url() -> str:
    svc = get_service("primary_mcp")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8200))
    path = svc.get("transport_path", "/clinicaltools")
    return f"http://{host}:{port}{path}"


def _prompt_text(get_prompt_result) -> str:
    parts = []
    for message in get_prompt_result.messages:
        text = getattr(message.content, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _resource_text(read_result) -> str:
    blocks = read_result
    if hasattr(read_result, "contents"):
        blocks = read_result.contents
    parts = []
    for block in blocks or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        elif isinstance(block, dict) and "text" in block:
            parts.append(str(block["text"]))
    return "\n".join(parts)


def _tool_result_to_text(result: object) -> str:
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return text
    data = getattr(result, "data", None)
    if isinstance(data, str):
        return data
    if data is not None:
        return json.dumps(data)
    return str(result)


def _clinical_text_blob(extraction: dict) -> str:
    """Flatten extraction into one clinical text blob for the Lang Bridge."""
    return json.dumps(extraction, ensure_ascii=False, indent=2)


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _deep_merge_prefer_filled(base: object, overlay: object) -> object:
    """Merge overlay onto base; never let null/empty wipe a filled source value."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for key, oval in overlay.items():
            if key not in out:
                if not _is_empty(oval):
                    out[key] = oval
                continue
            out[key] = _deep_merge_prefer_filled(out[key], oval)
        return out
    if _is_empty(overlay):
        return base
    return overlay


def _apply_translated_overlay(extraction: dict, translated_text: str) -> dict:
    """Merge Sampling output back into the extraction dict (preserve filled fields)."""
    result = json.loads(json.dumps(extraction))  # deep copy via JSON
    try:
        overlay = json.loads(translated_text)
    except json.JSONDecodeError:
        result.setdefault("notes", [])
        if isinstance(result["notes"], list):
            result["notes"].append("normalized_text:" + translated_text[:2000])
        return result

    if not isinstance(overlay, dict):
        return result

    if any(k in overlay for k in ("discharge", "lab", "bill", "patient_id")):
        return _deep_merge_prefer_filled(result, overlay)

    return result


async def prepare_node(state: NormalizerState) -> dict:
    """Fetch MCP Prompt + medical-abbreviations Resource (no Sampling yet)."""
    import time

    from shared.tracing.langfuse import observation, record_span

    url = _primary_mcp_url()
    extraction = state.get("extraction") or {}
    raw_lang = state.get("source_language") or detect_source_language(extraction)
    source_language = normalize_lang_code(raw_lang)
    errors = list(state.get("errors", []))

    async with Client(url) as client:
        with observation(
            "Prompt",
            kind="prompt",
            input_payload={"name": "abbreviation-normalization-prompt", "source_language": source_language},
            metadata={"agent": "Normalizer Agent"},
        ) as pspan:
            prompt_result = await client.get_prompt(
                "abbreviation-normalization-prompt",
                {"source_language": source_language},
            )
            prompt_text = _prompt_text(prompt_result)
            pspan.set_output({"chars": len(prompt_text)})

        try:
            read_result = await client.read_resource("resource://medical-abbreviations")
            abbreviations_yaml = _resource_text(read_result)
            record_span(
                "Resources",
                kind="resource",
                input_payload={"uri": "resource://medical-abbreviations"},
                output_payload={"chars": len(abbreviations_yaml)},
                metadata={"agent": "Normalizer Agent"},
            )
        except Exception as exc:
            abbreviations_yaml = ""
            errors.append(f"abbreviations resource: {exc}")

    logger.info(
        "Normalizer prepare patient=%s lang=%s path=%s prompt_chars=%s abbrev_chars=%s",
        state["patient_id"],
        source_language,
        language_path(source_language),
        len(prompt_text),
        len(abbreviations_yaml),
    )
    return {
        "source_language": source_language,
        "prompt_text": prompt_text,
        "abbreviations_yaml": abbreviations_yaml,
        "errors": errors,
    }


async def bridge_node(state: NormalizerState) -> dict:
    """Call Medical Lang Bridge with sampling_callback wired (SSoT §3.6)."""
    import time

    from shared.tracing.langfuse import record_mcp_tool, record_translation

    url = _primary_mcp_url()
    extraction = state.get("extraction") or {}
    source_language = normalize_lang_code(state.get("source_language") or "auto")
    errors = list(state.get("errors", []))
    instructions = state.get("prompt_text") or ""

    if not extraction:
        errors.append("empty extraction — nothing to normalize")
        return {
            "bridge_raw": json.dumps(
                {
                    "error": "empty_extraction",
                    "translated_text": "",
                    "confidence": 0.0,
                    "source_language": source_language,
                }
            ),
            "errors": errors,
        }

    # Clinical JSON only — MCP prompt goes to `instructions` (system_prompt)
    clinical_text = _clinical_text_blob(extraction)
    params = {
        "text": clinical_text,
        "source_language": source_language,
        "instructions": instructions,
    }

    # Sampling → LiteLLM records "LLM Generation"; tool is a sibling under normalize.
    t0 = time.perf_counter()
    async with Client(url, sampling_handler=sampling_callback) as client:
        result = await client.call_tool(
            "medical_lang_bridge",
            params,
            raise_on_error=False,
        )
    elapsed = (time.perf_counter() - t0) * 1000
    bridge_raw = _tool_result_to_text(result)
    record_mcp_tool(
        "medical_lang_bridge",
        params={"source_language": source_language, "text_chars": len(clinical_text)},
        result={"chars": len(bridge_raw)},
        duration_ms=elapsed,
        success="error" not in bridge_raw.lower()[:80],
    )
    try:
        parsed = json.loads(bridge_raw)
    except json.JSONDecodeError:
        parsed = {"raw": bridge_raw[:500]}
    record_translation(
        source_language=source_language,
        result=parsed if isinstance(parsed, dict) else {"raw_chars": len(bridge_raw)},
        metadata={"agent": "Normalizer Agent"},
    )

    logger.info(
        "Lang Bridge returned %s char(s) for patient=%s lang=%s",
        len(bridge_raw),
        state["patient_id"],
        source_language,
    )
    return {"bridge_raw": bridge_raw, "errors": errors}


async def assemble_node(state: NormalizerState) -> dict:
    """Parse bridge JSON → post-normalize → NormalizationResult (confidence required)."""
    errors = list(state.get("errors", []))
    extraction = state.get("extraction") or {}
    source_language = normalize_lang_code(state.get("source_language") or "auto")
    bridge_raw = state.get("bridge_raw") or "{}"
    abbrev_yaml = state.get("abbreviations_yaml") or ""

    try:
        bridge = json.loads(bridge_raw)
    except json.JSONDecodeError as exc:
        errors.append(f"bridge JSON parse failed: {exc}")
        bridge = {
            "translated_text": bridge_raw,
            "confidence": 0.0,
            "model_used": "",
        }

    if bridge.get("error"):
        errors.append(str(bridge["error"]))

    confidence = bridge.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
        errors.append("missing/invalid translation confidence — defaulted to 0.0")

    translated = bridge.get("translated_text") or ""
    if isinstance(translated, dict):
        translated = json.dumps(translated, ensure_ascii=False)
    else:
        translated = str(translated)

    normalized = _apply_translated_overlay(extraction, translated)
    if translated.strip().startswith("{"):
        try:
            maybe = json.loads(translated)
            if isinstance(maybe, dict) and (
                "discharge" in maybe or "lab" in maybe or "bill" in maybe
            ):
                # Prefer filled source fields over empty translated slots
                normalized = _deep_merge_prefer_filled(extraction, maybe)
                if "patient_id" not in normalized:
                    normalized["patient_id"] = state["patient_id"]
        except json.JSONDecodeError:
            pass
    else:
        normalized.setdefault("notes", [])
        if isinstance(normalized.get("notes"), list):
            normalized["notes"] = list(normalized["notes"]) + [
                f"english_narrative: {translated[:3000]}"
            ]

    # Deterministic post-pass on the structured dict (safe for nested JSON)
    normalized = post_normalize_extraction(normalized, abbrev_yaml)

    for key in ("discharge", "lab", "bill"):
        section = normalized.get(key)
        if isinstance(section, dict) and section:
            section["language"] = "en"

    detected = normalize_lang_code(bridge.get("source_language") or source_language)
    # English source text is already usable — don't let a timid model score
    # drop a clean case below the quality threshold (rules.yaml 0.70).
    if is_english(detected):
        confidence = max(float(confidence), 0.95)
    path = language_path(detected)
    if path == "fallback":
        primary = "/".join(get_primary_language_codes())
        errors.append(
            f"fallback language '{detected}' — not in primary seed/rules set "
            f"({primary}); translated via multilingual Sampling anyway"
        )

    result = NormalizationResult(
        patient_id=str(state["patient_id"]),
        source_language=detected,
        translation_confidence=max(0.0, min(1.0, confidence)),
        model_used=str(bridge.get("model_used") or ""),
        normalized_extraction=normalized,
        notes=errors,
    )
    from shared.tracing.langfuse import record_span

    dumped = result.model_dump()
    record_span(
        "Output",
        kind="span",
        input_payload={"patient_id": state["patient_id"]},
        output_payload={
            "translation_confidence": dumped.get("translation_confidence"),
            "source_language": dumped.get("source_language"),
            "model_used": dumped.get("model_used"),
        },
        metadata={"agent": "Normalizer Agent"},
    )
    logger.info(
        "Normalization complete patient=%s lang=%s path=%s confidence=%s",
        state["patient_id"],
        detected,
        path,
        result.translation_confidence,
    )
    return {"result": dumped, "errors": errors}
