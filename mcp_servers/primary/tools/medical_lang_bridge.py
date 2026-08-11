"""Medical Lang Bridge Tool + Sampling (SSoT §3.5, §3.6).

Beginner picture:
  1. This tool does NOT call the LLM itself.
  2. It asks the Normalizer client to run the LLM (MCP Sampling).
  3. Focus languages = primary set from rules.yaml (en, es, hi, de, fr, nl).
  4. If a new language appears → fallback path (still translate with
     nova-lite). We never reject the case.
  5. Sampling system_prompt comes from the MCP prompt the agent fetched
     (instructions=…). The tool only adds a short technical appendix.

Contract:
  tool → ctx.session.create_message(..., ModelPreferences)
  client → sampling_callback → LiteLLM → CreateMessageResult
"""

from __future__ import annotations

import json

from fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

from mcp_servers.primary.rules_loader import load_rules
from mcp_servers.primary.sampling import build_model_preferences
from shared.language import (
    get_primary_language_codes,
    is_english,
    language_path,
    normalize_lang_code,
)
from shared.logger import get_logger
from shared.settings import get_bedrock_config

logger = get_logger("medical_lang_bridge")


def _abbreviation_block() -> str:
    """Short abbreviation map text from rules.yaml for the sampling user msg."""
    rules = load_rules()
    abbrev = (
        rules.get("normalization_standards", {}).get("abbreviation_map", {}) or {}
    )
    lines = [f"{k} = {v}" for k, v in abbrev.items()]
    return "\n".join(lines)


def _technical_appendix(source_language: str) -> str:
    """Small fixed appendix so replies stay machine-parseable.

    Main clinical instructions come from the MCP prompt (`instructions`).
    This appendix only reminds the model of JSON shape + primary/fallback.
    """
    lang = normalize_lang_code(source_language)
    path = language_path(lang)
    primary = ", ".join(get_primary_language_codes())
    return (
        "\n\n--- Technical appendix (Medical Lang Bridge) ---\n"
        f"Declared source language: {lang} (path={path}).\n"
        f"PRIMARY languages: {primary}.\n"
        "If instructions above conflict with this appendix on OUTPUT SHAPE, "
        "follow this appendix for the reply format.\n"
        "Reply with ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "translated_text": "<English text OR JSON of the normalized extraction>",\n'
        '  "confidence": <float 0.0 to 1.0>,\n'
        '  "source_language": "<detected code>"\n'
        "}\n"
    )


def _build_system_prompt(source_language: str, instructions: str) -> str:
    """Prefer MCP prompt body; fall back to a minimal built-in if empty."""
    body = (instructions or "").strip()
    if not body:
        # Safety net if the client forgot to pass the MCP prompt
        primary = ", ".join(get_primary_language_codes())
        body = (
            "You are a clinical language normalizer. Translate to English, "
            "expand abbreviations, and canonicalize medicine names "
            "(Metformina→Metformin, Amoxicilline→Amoxicillin, etc.). "
            f"Primary languages: {primary}. Fallback languages: still translate."
        )
    return body + _technical_appendix(source_language)


def register_lang_bridge_tools(mcp: FastMCP) -> None:
    """Attach the Medical Lang Bridge tool to the Primary MCP server."""

    @mcp.tool(
        name="medical_lang_bridge",
        title="Medical Lang Bridge Tool",
        description=(
            "Translate and normalize clinical text via MCP Sampling. "
            "Pass source_language as a short code or 'auto'. "
            "Pass instructions= the body from MCP prompt "
            "'abbreviation-normalization-prompt' (agent must get_prompt first). "
            "Primary languages from rules.yaml; unexpected langs use fallback. "
            "The calling client must provide a sampling_callback — this tool "
            "does not run the LLM itself."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def medical_lang_bridge(
        text: str,
        source_language: str,
        ctx: Context,
        instructions: str = "",
    ) -> str:
        """Issue a Sampling request; return JSON with translated_text + confidence."""
        lang = normalize_lang_code(source_language)

        if not (text or "").strip():
            return json.dumps(
                {
                    "error": "empty_text",
                    "translated_text": "",
                    "confidence": 0.0,
                    "source_language": lang,
                }
            )

        preferences = build_model_preferences(lang)
        max_tokens = max(int(get_bedrock_config()["max_tokens"]), 4096)
        path = language_path(lang)
        abbrev = _abbreviation_block()
        user_msg = (
            f"Source language (declared): {lang}\n"
            f"Language path: {path}  # primary = rules.yaml set; fallback = other\n"
            f"Already English: {is_english(lang)}\n"
            "If language is auto/unknown, detect it from the clinical text below.\n\n"
            f"Abbreviation map (from rules.yaml):\n{abbrev}\n\n"
            f"--- CLINICAL TEXT ---\n{text}"
        )

        system_prompt = _build_system_prompt(lang, instructions)
        logger.info(
            "Sampling request lang=%s path=%s hints=%s chars=%s instructions_chars=%s",
            lang,
            path,
            [h.name for h in (preferences.hints or [])],
            len(text),
            len(instructions or ""),
        )

        # SSoT §3.6 — create_message on the client session (Sampling primitive).
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=user_msg),
                )
            ],
            system_prompt=system_prompt,
            model_preferences=preferences,
            max_tokens=max_tokens,
            temperature=0.0,
        )

        content = result.content
        reply_text = getattr(content, "text", None) or str(content)
        model_used = getattr(result, "model", "") or ""

        parsed = _parse_sampling_json(reply_text)
        parsed["model_used"] = model_used
        detected = normalize_lang_code(parsed.get("source_language"))
        if detected == "auto":
            detected = lang
        parsed["source_language"] = detected
        logger.info(
            "Sampling done model=%s confidence=%s detected_lang=%s",
            model_used,
            parsed.get("confidence"),
            detected,
        )
        return json.dumps(parsed, ensure_ascii=False, indent=2)


def _parse_sampling_json(reply_text: str) -> dict:
    """Best-effort parse of the model's JSON reply."""
    text = (reply_text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            conf = data.get("confidence", 0.0)
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.0
            return {
                "translated_text": data.get("translated_text") or data.get("text") or text,
                "confidence": max(0.0, min(1.0, conf)),
                "source_language": data.get("source_language"),
            }
    except json.JSONDecodeError:
        pass

    return {
        "translated_text": reply_text,
        "confidence": 0.5,
        "source_language": None,
        "notes": ["sampling reply was not valid JSON; used raw text"],
    }
