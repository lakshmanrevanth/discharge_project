"""Clinical Insight Reporter Tool (SSoT §3.5, §5.5).

Beginner picture: after completeness + EHR cross-validation + risk scoring
have all run, this tool writes ONE JSON report and ONE HTML report to
data/reports/. It runs unconditionally — even a blocked/High case still
gets a report; the Release Gate reads risk_tier/discharge_blocked from this
same payload instead of re-deriving anything.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from mcp_servers.primary.rules_loader import load_rules, read_text_file
from shared.guardrails.guardrail_manager import evaluate_hitl_escalation
from shared.logger import get_logger
from shared.rules_config import get_rules_version
from shared.settings import get_path

logger = get_logger("clinical_insight_reporter")

# rule_id -> which report bucket it belongs to (SSoT §5.5 required contents)
_EHR_DISCREPANCY_RULES = {
    "diagnosis_mismatch_check",
    "follow_up_missing_check",
    "lab_follow_up_mismatch_check",
    "discharge_approval_check",
    "bill_settlement_check",
    "ehr_patient_not_found",
}
_MEDICATION_CONFLICT_RULES = {
    "allergy_contradiction_check",
    "med_omission_check",
    "medication_added",
    "high_risk_med_missing_in_ehr",
    "high_risk_med_no_counseling",
}


def _fill(template: str, values: dict) -> str:
    text = template
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", "" if val is None else str(val))
    return text


def build_report(
    patient_id: str,
    normalized_extraction: dict,
    findings: list[dict],
    risk_score: int,
    risk_tier: str,
    discharge_blocked: bool,
    translation_confidence: float,
    elicitation_outcome: str | None,
    release_gate: dict | None = None,
    trace_id: str | None = None,
) -> dict:
    """Assemble the JSON audit/risk report (SSoT §5.5 — 8 required contents)."""
    rules = load_rules()
    recommendations = rules.get("reporting", {}).get("recommendations", {})
    discharge = normalized_extraction.get("discharge") or {}
    bill = normalized_extraction.get("bill") or {}

    missing_fields = [
        f["field"]
        for f in findings
        if f.get("rule_id") == "missing_mandatory_field" and f.get("field")
    ]
    ehr_discrepancies = [f for f in findings if f.get("rule_id") in _EHR_DISCREPANCY_RULES]
    medication_conflicts = [f for f in findings if f.get("rule_id") in _MEDICATION_CONFLICT_RULES]

    gate = release_gate or evaluate_hitl_escalation(risk_tier, discharge_blocked)
    recommendation = recommendations.get(
        "high" if discharge_blocked or gate.get("mandatory_hitl") else risk_tier, ""
    )

    # The caller (Validator) passes the live case trace_id, because this tool
    # runs in the Primary MCP *process* — the ContextVar the agents use does not
    # cross that boundary. Never mint a new id here: an id no span was ever
    # written under stamps a LangFuse URL that opens an empty, forever-loading
    # trace page. No id → no URL, and the dashboard falls back to the live one.
    from shared.tracing.langfuse import get_current_trace_id, trace_url

    tid = str(trace_id or "").strip() or get_current_trace_id()
    if not tid:
        logger.warning(
            "No case trace_id supplied for %s — report stamped without a LangFuse URL",
            patient_id,
        )

    return {
        "patient_id": patient_id,
        "patient_name": discharge.get("patient_name"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rules_version": get_rules_version(),
        "missing_fields": missing_fields,
        "ehr_discrepancies": ehr_discrepancies,
        "medication_conflicts": medication_conflicts,
        "translation_confidence": translation_confidence,
        "risk_level": risk_tier,
        "risk_score": risk_score,
        "recommendation": recommendation,
        "discharge_blocked": discharge_blocked,
        "release_gate": gate,
        "elicitation_outcome": elicitation_outcome,
        "bill_amount": bill.get("total_amount"),
        "bill_payment_status": bill.get("payment_status"),
        "audit_trail": {
            "trace_ids": [tid] if tid else [],
            "langfuse_url": trace_url(tid) if tid else None,
            "tool_calls": [
                "clinical_rules_engine",
                "ehr_validation",
                "calculate_risk_score",
                "clinical_insight_reporter",
            ],
        },
        "all_findings": findings,
    }



def _render_html(template: str, report: dict) -> str:
    def _list_html(items: list[dict]) -> str:
        if not items:
            return "<li>None</li>"
        return "".join(f"<li>{i['rule_id']}: {i['message']}</li>" for i in items)

    values = {
        "patient_id": report["patient_id"],
        "patient_name": report.get("patient_name") or "",
        "generated_at": report["generated_at"],
        "rules_version": report["rules_version"][:12],
        "risk_level": report["risk_level"],
        "risk_score": report["risk_score"],
        "recommendation": report["recommendation"],
        "discharge_blocked": "YES" if report["discharge_blocked"] else "no",
        "translation_confidence": report.get("translation_confidence"),
        "missing_fields": ", ".join(report["missing_fields"]) or "None",
        "ehr_discrepancies": _list_html(report["ehr_discrepancies"]),
        "medication_conflicts": _list_html(report["medication_conflicts"]),
        "bill_amount": report.get("bill_amount"),
        "bill_payment_status": report.get("bill_payment_status") or "unknown",
    }
    return _fill(template, values)


def write_report_files(patient_id: str, report: dict, html: str) -> dict[str, str]:
    out_dir = get_path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{patient_id}_report.json"
    html_path = out_dir / f"{patient_id}_report.html"
    pdf_path = out_dir / f"{patient_id}_report.pdf"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    try:
        from shared.pdf_export import write_audit_pdf

        write_audit_pdf(report, pdf_path)
    except Exception as exc:
        logger.warning("PDF export skipped for %s: %s", patient_id, exc)
        pdf_path = None
    logger.info("Report written for %s: %s / %s", patient_id, json_path, html_path)
    paths = {"json_path": str(json_path), "html_path": str(html_path)}
    if pdf_path and Path(pdf_path).is_file():
        paths["pdf_path"] = str(pdf_path)
    return paths


def register_reporter_tools(mcp: FastMCP) -> None:
    """Attach the Clinical Insight Reporter tool to the Primary MCP server."""

    @mcp.tool(
        name="clinical_insight_reporter",
        title="Clinical Insight Reporter Tool",
        description=(
            "Write the JSON + HTML + PDF discharge audit/risk report for one "
            "patient case to data/reports/. Runs unconditionally after "
            "completeness + EHR validation + risk scoring (SSoT §5.5). "
            "Stamps rules_version = SHA-256 of rules.yaml and LangFuse trace_ids."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def clinical_insight_reporter(
        patient_id: str,
        normalized_extraction: dict,
        findings: list[dict],
        risk_score: int,
        risk_tier: str,
        discharge_blocked: bool,
        translation_confidence: float = 0.0,
        elicitation_outcome: str | None = None,
        release_gate: dict | None = None,
        trace_id: str | None = None,
    ) -> str:
        """Build + persist the report; return the same JSON as a string.

        ``trace_id`` is the caller's live LangFuse case trace id — it is what
        makes ``audit_trail.langfuse_url`` point at a trace that actually exists.
        """
        report = build_report(
            patient_id,
            normalized_extraction,
            findings,
            risk_score,
            risk_tier,
            discharge_blocked,
            translation_confidence,
            elicitation_outcome,
            release_gate=release_gate,
            trace_id=trace_id,
        )
        template = await read_text_file(get_path("report_template"))
        html = _render_html(template, report)
        report["report_files"] = write_report_files(patient_id, report, html)

        logger.info(
            "Report complete patient=%s tier=%s blocked=%s",
            patient_id,
            risk_tier,
            discharge_blocked,
        )
        return json.dumps(report, ensure_ascii=False, indent=2)
