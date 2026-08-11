"""Discharge Summary Generator — Google ADK (SSoT §5.7, §4 streaming).

Framework: Google ADK (MUST NOT use LangGraph for this agent — SSoT §2).
Job:
  1. Refuse when discharge_blocked or risk_level=high (release gate).
  2. Fetch summary-generation-prompt via MCP get_prompt (never hardcode).
  3. Generate patient-friendly text one section at a time
     (patient → meds → labs → bill → instructions).
  4. Run ToxicityFilter on the instructions section before yielding it.

The A2A executor streams each section as its own artifact (streaming=True).
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import Client
from google.adk.agents import LlmAgent

from shared.guardrails.toxicity_filter import filter_toxicity
from shared.llm import arun_completion
from shared.logger import get_logger
from shared.models.summary import DischargeSummary
from shared.settings import get_service, load_agent_config

logger = get_logger("summary")

# Fixed section order from SSoT §4 / agent_config.yaml (fallback if config missing).
_DEFAULT_SECTION_ORDER = ["patient", "meds", "labs", "bill", "instructions"]

_SECTION_HINTS = {
    "patient": "Write a short, warm intro with the patient's name, age, gender, "
    "admission/discharge dates, ward/bed, doctors, and discharge diagnosis. "
    "Plain English. No jargon.",
    "meds": "List every discharge medication in plain English: name, strength, "
    "how often, how to take (route), and for how long. One short bullet per med.",
    "labs": "Summarize lab results in plain English. Mention abnormal values "
    "clearly. If there are no labs, say so briefly.",
    "bill": "Summarize the hospital bill: total amount and whether it is paid. "
    "Keep it short and clear. If no bill data, say so.",
    "instructions": "Write clear home-care instructions and follow-up advice "
    "the patient can follow. Be kind and specific. No scary or harmful language.",
}


def _primary_mcp_url() -> str:
    svc = get_service("primary_mcp")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8200))
    path = svc.get("transport_path", "/clinicaltools")
    return f"http://{host}:{port}{path}"


def section_order() -> list[str]:
    """Read fixed section order from agent_config.yaml (SSoT §4)."""
    cfg = load_agent_config()
    order = cfg.get("agents", {}).get("summary", {}).get("section_order")
    if isinstance(order, list) and order:
        return [str(s) for s in order]
    return list(_DEFAULT_SECTION_ORDER)


def is_summary_allowed(risk_level: str | None, discharge_blocked: bool) -> bool:
    """Release gate: High or blocked → no auto-summary (§5.7, §8 GuardrailManager)."""
    from shared.guardrails.guardrail_manager import evaluate_hitl_escalation

    gate = evaluate_hitl_escalation(risk_level, discharge_blocked)
    # Medium unblocked may still summarize; Mandatory HITL (High/blocked) may not.
    return not gate["mandatory_hitl"]


def _prompt_text(get_prompt_result: Any) -> str:
    """Pull plain text out of an MCP get_prompt result."""
    parts: list[str] = []
    for message in getattr(get_prompt_result, "messages", []) or []:
        content = getattr(message, "content", None)
        text = getattr(content, "text", None) if content is not None else None
        if text:
            parts.append(text)
        elif isinstance(content, str):
            parts.append(content)
    return "\n".join(parts).strip()


async def fetch_summary_prompt(risk_level: str, audience: str) -> str:
    """MCP get_prompt('summary-generation-prompt') — never hardcode (§3.4)."""
    url = _primary_mcp_url()
    async with Client(url) as client:
        result = await client.get_prompt(
            "summary-generation-prompt",
            {"risk_level": risk_level, "audience": audience},
        )
    text = _prompt_text(result)
    if not text:
        raise RuntimeError("summary-generation-prompt returned empty text from MCP")
    return text


def _slice_context(section: str, extraction: dict) -> dict:
    """Give the LLM only the slice it needs for this section (beginner-simple)."""
    discharge = extraction.get("discharge") or {}
    lab = extraction.get("lab") or {}
    bill = extraction.get("bill") or {}

    if section == "patient":
        return {
            "patient_id": discharge.get("patient_id") or extraction.get("patient_id"),
            "patient_name": discharge.get("patient_name"),
            "age": discharge.get("age"),
            "gender": discharge.get("gender"),
            "address": discharge.get("address"),
            "admission_date": discharge.get("admission_date"),
            "discharge_date": discharge.get("discharge_date"),
            "ward": discharge.get("ward"),
            "bed_no": discharge.get("bed_no"),
            "attending_physician": discharge.get("attending_physician"),
            "consulting_doctors": discharge.get("consulting_doctors"),
            "discharge_diagnosis": discharge.get("discharge_diagnosis"),
        }
    if section == "meds":
        return {"medications": discharge.get("medications") or []}
    if section == "labs":
        return {"lab": lab}
    if section == "bill":
        return {"bill": bill}
    if section == "instructions":
        return {
            "discharge_instructions": discharge.get("discharge_instructions"),
            "follow_up_appointment": discharge.get("follow_up_appointment")
            or discharge.get("follow_up_appointments"),
            "allergies": discharge.get("allergies") or [],
        }
    return {"extraction": extraction}


async def _generate_one_section(
    *,
    section: str,
    prompt_instructions: str,
    audience: str,
    risk_level: str,
    extraction: dict,
) -> str:
    """One LiteLLM call for one section — the single generation path."""
    context = _slice_context(section, extraction)
    system = (
        f"{prompt_instructions}\n\n"
        f"You are writing ONLY the '{section}' section for a {audience} audience "
        f"(case risk_level={risk_level}). "
        f"{_SECTION_HINTS.get(section, '')} "
        "Reply with the section text only — no JSON, no markdown headings, "
        "no preamble like 'Here is the section'."
    )
    user = (
        f"Section to write: {section}\n"
        f"Clinical data (JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    text, model = await arun_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        hint_names=["nova-lite"],
        temperature=0.2,
    )
    logger.info("Summary section=%s model=%s chars=%s", section, model, len(text or ""))
    return (text or "").strip()


async def iter_summary_sections(
    *,
    patient_id: str,
    risk_level: str,
    discharge_blocked: bool,
    extraction: dict,
    audience: str = "patient",
) -> AsyncIterator[tuple[str, str]]:
    """Yield (section_name, text) in fixed order, or nothing if the gate refuses.

    Callers (A2A executor) stream each yielded section as an artifact.
    """
    if not is_summary_allowed(risk_level, discharge_blocked):
        reason = (
            f"Summary refused for {patient_id}: "
            f"risk_level={risk_level!r}, discharge_blocked={discharge_blocked}. "
            "Release gate requires human review first (SSoT §5.7 / §8)."
        )
        logger.warning(reason)
        yield "refused", reason
        return

    prompt = await fetch_summary_prompt(risk_level, audience)
    for section in section_order():
        text = await _generate_one_section(
            section=section,
            prompt_instructions=prompt,
            audience=audience,
            risk_level=risk_level,
            extraction=extraction,
        )
        if section == "instructions":
            text = filter_toxicity(text)
        yield section, text


async def run_summary(
    *,
    patient_id: str,
    risk_level: str,
    discharge_blocked: bool,
    extraction: dict,
    audience: str = "patient",
) -> DischargeSummary:
    """Build a full DischargeSummary (used by tests / non-streaming callers)."""
    sections: dict[str, str] = {}
    notes: list[str] = []
    refused = False
    refuse_reason: str | None = None

    async for name, text in iter_summary_sections(
        patient_id=patient_id,
        risk_level=risk_level,
        discharge_blocked=discharge_blocked,
        extraction=extraction,
        audience=audience,
    ):
        if name == "refused":
            refused = True
            refuse_reason = text
            notes.append(text)
            break
        sections[name] = text

    return DischargeSummary(
        patient_id=patient_id,
        risk_level=risk_level,
        audience=audience,
        refused=refused,
        refuse_reason=refuse_reason,
        sections=sections,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Google ADK agent (framework identity — SSoT §2 row 5)
# ---------------------------------------------------------------------------
# Like Monitor: A2A executor calls run_summary / iter_summary_sections directly
# for a clear beginner path. The LlmAgent object satisfies the ADK framework
# requirement; Host (Phase 12) can wire a Runner later if needed.

summary_agent = LlmAgent(
    name="discharge_summary_generator",
    model=os.environ.get("SUMMARY_MODEL", "gemini-2.0-flash"),
    description=(
        "Discharge Summary Generator. Streams a patient-friendly summary "
        "section-by-section after the release gate allows the case."
    ),
    instruction=(
        "Generate a patient-friendly discharge summary only when the release "
        "gate allows it (not High risk, not discharge_blocked). "
        "Stream sections in order: patient, meds, labs, bill, instructions. "
        "Always fetch summary-generation-prompt via MCP. Never invent clinical facts."
    ),
)


def build_summary_agent() -> LlmAgent:
    """Return the Google ADK Summary agent instance."""
    return summary_agent
