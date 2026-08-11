"""Validator graph nodes — Rules Engine (+Elicitation), EHR Validation, Risk
score (Secondary MCP), Reporter (SSoT §5.4, §5.5).

Beginner picture (4 simple steps, one clear path):
  1. completeness_node — clinical_rules_engine tool (Primary MCP). May run
     ONE elicitation call for non-blocking gaps (SSoT §3.7); this agent's
     MCP client auto-declines until Streamlit exists (elicitation_handler.py).
  2. ehr_node — ehr_validation tool (Primary MCP) against Mock EHR.
  3. risk_node — calculate_risk_score (Secondary MCP) + the translation
     confidence quality threshold (rules.yaml quality_thresholds).
  4. report_node — clinical_insight_reporter tool (Primary MCP); persists
     the JSON+HTML audit report and decides discharge_blocked (release gate).
"""

from __future__ import annotations

import json

from fastmcp import Client

from agents.validator.elicitation_handler import resolve_elicitation_handler
from agents.validator.state import ValidatorState
from shared.guardrails.guardrail_manager import evaluate_hitl_escalation
from shared.logger import get_logger
from shared.rules_config import load_rules
from shared.settings import get_service

logger = get_logger("validator")


def _primary_mcp_url() -> str:
    svc = get_service("primary_mcp")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8200))
    path = svc.get("transport_path", "/clinicaltools")
    return f"http://{host}:{port}{path}"


def _secondary_mcp_url() -> str:
    svc = get_service("secondary_mcp")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8201))
    path = svc.get("transport_path", "/analyticstools")
    return f"http://{host}:{port}{path}"


def _tool_result_to_dict(result: object) -> dict:
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw_text": text}
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    return {"error": f"unrecognized tool result: {result!r}"}


async def completeness_node(state: ValidatorState) -> dict:
    """Rules Engine completeness check + ONE elicitation when needed (SSoT §3.7)."""
    url = _primary_mcp_url()
    errors = list(state.get("errors", []))
    extraction = state.get("extraction") or {}

    async with Client(url, elicitation_handler=resolve_elicitation_handler) as client:
        result = await client.call_tool(
            "clinical_rules_engine",
            {"patient_id": state["patient_id"], "extraction": extraction},
            raise_on_error=False,
        )
    payload = _tool_result_to_dict(result)
    if payload.get("error"):
        errors.append(str(payload["error"]))

    logger.info(
        "Completeness patient=%s findings=%s missing=%s outcome=%s",
        state["patient_id"],
        len(payload.get("completeness_findings", [])),
        len(payload.get("missing_fields", [])),
        payload.get("elicitation_outcome"),
    )
    return {
        "extraction": payload.get("extraction") or extraction,
        "completeness_findings": payload.get("completeness_findings", []),
        "missing_fields": payload.get("missing_fields", []),
        "elicitation_outcome": payload.get("elicitation_outcome"),
        "errors": errors,
    }


async def ehr_node(state: ValidatorState) -> dict:
    """EHR cross-validation (7 Table 4 rules) against Mock EHR."""
    url = _primary_mcp_url()
    errors = list(state.get("errors", []))
    extraction = state.get("extraction") or {}

    async with Client(url) as client:
        result = await client.call_tool(
            "ehr_validation",
            {"patient_id": state["patient_id"], "extraction": extraction},
            raise_on_error=False,
        )
    payload = _tool_result_to_dict(result)
    if payload.get("error"):
        errors.append(str(payload["error"]))

    ehr_findings = payload.get("findings", [])
    logger.info("EHR validation patient=%s findings=%s", state["patient_id"], len(ehr_findings))
    return {"ehr_findings": ehr_findings, "errors": errors}


def _elicitation_finding(outcome: str, missing_fields: list[str]) -> dict:
    """Decline/cancel forces Mandatory HITL, never averaged away by score (§3.7).

    Severity stays ``info`` (not clinical Critical) — this is a gate note about
    the elicitation outcome. ``blocking`` still forces Needs Review / Mandatory HITL.
    """
    action = (outcome or "unknown").strip().lower()
    blocking = action in {"decline", "cancel", "declined", "cancelled"}
    return {
        "rule_id": f"elicitation_{action}",
        "severity": "info",
        "message": (
            f"Missing-field elicitation was {action}d "
            f"({', '.join(missing_fields) or 'no fields listed'}). "
            "Fill gaps on Corrections, or accept/decline there before release."
        ),
        "field": None,
        "weight": 0,
        "blocking": blocking,
    }


def _quality_finding(normalization: dict, rules: dict) -> dict | None:
    """low_translation_confidence hard guardrail (rules.yaml quality_thresholds)."""
    quality = rules.get("quality_thresholds", {})
    min_conf = quality.get("translation_confidence_min", 0.70)
    confidence = normalization.get("translation_confidence")
    if confidence is None or confidence >= min_conf:
        return None
    weights = rules.get("risk_scoring_matrix", {}).get("weights", {})
    return {
        "rule_id": "translation_confidence_below_threshold",
        "severity": "critical",
        "message": f"Translation confidence {confidence:.2f} is below threshold {min_conf}.",
        "field": "translation_confidence",
        "weight": weights.get("low_translation_confidence", 3),
        "blocking": True,
    }


async def risk_node(state: ValidatorState) -> dict:
    """Aggregate risk score via Secondary MCP; hold Primary open too (SSoT §3.1)."""
    primary_url = _primary_mcp_url()
    secondary_url = _secondary_mcp_url()
    errors = list(state.get("errors", []))
    rules = load_rules()

    all_findings = list(state.get("completeness_findings", [])) + list(state.get("ehr_findings", []))

    outcome = state.get("elicitation_outcome")
    if outcome in {"decline", "cancel"}:
        all_findings.append(_elicitation_finding(outcome, state.get("missing_fields", [])))

    quality_finding = _quality_finding(state.get("normalization") or {}, rules)
    if quality_finding:
        all_findings.append(quality_finding)

    # Dual MCP: Primary + Secondary open together while scoring (SSoT §3.1).
    async with Client(primary_url) as primary, Client(secondary_url) as secondary:
        # Touch Primary rules resource so both servers are actively used.
        try:
            await primary.read_resource("resource://clinical-rules/cross-validation")
        except Exception as exc:
            logger.info("Primary rules resource read skipped: %s", exc)
        result = await secondary.call_tool(
            "calculate_risk_score",
            {"findings": all_findings},
            raise_on_error=False,
        )
    payload = _tool_result_to_dict(result)
    if payload.get("error"):
        errors.append(str(payload["error"]))

    # Critical / blocking findings → absolute block (ignores score).
    discharge_blocked = any(f.get("blocking") for f in all_findings)
    # Secondary hard guardrails force High; blocked cases also force High (§8 / §15).
    risk_tier = payload.get("risk_tier", "low")
    if discharge_blocked or payload.get("triggered_hard_guardrails"):
        risk_tier = "high"

    gate = evaluate_hitl_escalation(risk_tier, discharge_blocked)

    logger.info(
        "Risk score patient=%s score=%s tier=%s blocked=%s gate=%s",
        state["patient_id"],
        payload.get("risk_score"),
        risk_tier,
        discharge_blocked,
        gate.get("action"),
    )
    return {
        "all_findings": all_findings,
        "risk_score": payload.get("risk_score", 0),
        "risk_tier": risk_tier,
        "discharge_blocked": discharge_blocked,
        "release_gate": gate,
        "errors": errors,
    }


async def report_node(state: ValidatorState) -> dict:
    """Persist the JSON+HTML audit report (SSoT §5.5) — runs unconditionally."""
    url = _primary_mcp_url()
    errors = list(state.get("errors", []))
    normalization = state.get("normalization") or {}

    async with Client(url) as client:
        result = await client.call_tool(
            "clinical_insight_reporter",
            {
                "patient_id": state["patient_id"],
                "normalized_extraction": state.get("extraction") or {},
                "findings": state.get("all_findings", []),
                "risk_score": state.get("risk_score", 0),
                "risk_tier": state.get("risk_tier", "low"),
                "discharge_blocked": state.get("discharge_blocked", False),
                "translation_confidence": normalization.get("translation_confidence", 0.0),
                "elicitation_outcome": state.get("elicitation_outcome"),
                "release_gate": state.get("release_gate") or {},
            },
            raise_on_error=False,
        )
    report = _tool_result_to_dict(result)
    if report.get("error"):
        errors.append(str(report["error"]))

    logger.info(
        "Report complete patient=%s tier=%s blocked=%s",
        state["patient_id"],
        state.get("risk_tier"),
        state.get("discharge_blocked"),
    )
    return {"report": report, "errors": errors}
