"""EHR Validation Tool (SSoT §3.5, §5.4 Table 4 — 7 cross-validation rules).

Beginner picture: call the Mock EHR REST API (:8050) for one patient_id,
then compare it with the normalized discharge/lab/bill extraction. Critical
rules are absolute blocks; Warning rules only add risk-score weight (the
gate — Validator's risk_node — decides what that means).

Allergy/medicine matching is canonical, not string-equal (§12.3) — reuses
shared/clinical_normalize.py so there is one clear path, not a second
matching algorithm here.
"""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP

from mcp_servers.primary.rules_loader import load_rules
from shared.clinical_normalize import canonicalize_med_name, medication_conflicts_with_allergy
from shared.logger import get_logger
from shared.settings import get_service

logger = get_logger("ehr_validation")


def _mock_ehr_base_url() -> str:
    svc = get_service("mock_ehr")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8050))
    return f"http://{host}:{port}"


async def _get_json(client: httpx.AsyncClient, path: str) -> dict:
    resp = await client.get(path)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def _finding(
    rule_id: str,
    severity: str,
    message: str,
    weight: int = 0,
    blocking: bool = False,
    field: str | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "field": field,
        "weight": weight,
        "blocking": blocking,
    }


def _is_truthy(value: object) -> bool:
    """Beginner helper: treat True / 'true' / 'yes' / '1' as approved."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"", "false", "no", "0", "n", "none", "null"}:
        return False
    return text in {"true", "yes", "1", "y", "approved"}


async def cross_validate(patient_id: str, extraction: dict) -> list[dict]:
    """Run all 7 FA5 Table 4 rules for one patient; return Finding dicts."""
    rules = load_rules()
    weights = rules.get("risk_scoring_matrix", {}).get("weights", {})
    policies = rules.get("clinical_validation_policies", {})

    discharge = extraction.get("discharge") or {}
    bill = extraction.get("bill") or {}

    findings: list[dict] = []
    base_url = _mock_ehr_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        patient = await _get_json(client, f"/patients/{patient_id}")
        allergies_payload = await _get_json(client, f"/patients/{patient_id}/allergies")
        meds_payload = await _get_json(client, f"/patients/{patient_id}/medications")
        labs_payload = await _get_json(client, f"/patients/{patient_id}/labs")
        care_payload = await _get_json(client, f"/patients/{patient_id}/care-plan")

    # Patient missing from EHR → skip med/allergy/lab/care-plan compares.
    # Bill + discharge_approved still come from intake documents.
    if not patient:
        findings.append(
            _finding(
                "ehr_patient_not_found",
                "warning",
                f"Patient {patient_id} was not found in Mock EHR — "
                "skipped medication/allergy/lab/care-plan cross-checks.",
                field="patient_id",
            )
        )
        _check_discharge_approved(discharge, findings)
        _check_bill_settlement(extraction, discharge, bill, weights, findings)
        return findings

    allergies = allergies_payload.get("allergies", [])
    ehr_meds = meds_payload.get("medications", [])
    ehr_labs = labs_payload.get("labs", [])
    care_plan = care_payload.get("care_plan", {})

    discharge_meds = discharge.get("medications") or []
    ehr_med_names = {canonicalize_med_name(m.get("name", "")) for m in ehr_meds if m.get("name")}
    discharge_med_names = {
        canonicalize_med_name(m.get("medicine_name", "")) for m in discharge_meds if m.get("medicine_name")
    }

    # 1. allergy_contradiction_check — Critical, absolute block.
    for med in discharge_meds:
        name = med.get("medicine_name") or ""
        conflict = medication_conflicts_with_allergy(name, allergies)
        if conflict:
            findings.append(
                _finding(
                    "allergy_contradiction_check",
                    "critical",
                    f"Discharge medication '{name}' conflicts with documented allergy '{conflict}'.",
                    weight=weights.get("allergy_contradiction", 8),
                    blocking=True,
                    field="medications",
                )
            )

    # 2. med_omission_check (Warning) — EHR med not present at discharge.
    # Skip when the omitted med conflicts with a documented allergy: withholding
    # that drug on discharge is correct (HITL remove-flagged / Re-run), not an omission.
    for med_name in sorted(ehr_med_names - discharge_med_names):
        if medication_conflicts_with_allergy(med_name, allergies):
            continue
        findings.append(
            _finding(
                "med_omission_check",
                "warning",
                f"EHR medication '{med_name}' is not present in discharge medications.",
                weight=weights.get("medication_omission", 3),
                field="medications",
            )
        )

    # New meds on discharge not in EHR history — medication_added / high-risk variant.
    high_risk_meds = {m.lower() for m in policies.get("high_risk_meds_need_counseling", [])}
    for med_name in sorted(discharge_med_names - ehr_med_names):
        if med_name.lower() in high_risk_meds:
            findings.append(
                _finding(
                    "high_risk_med_missing_in_ehr",
                    "critical",
                    f"High-risk medication '{med_name}' added on discharge but absent from EHR orders.",
                    weight=weights.get("high_risk_med_missing_in_ehr", 9),
                    blocking=True,
                    field="medications",
                )
            )
        else:
            findings.append(
                _finding(
                    "medication_added",
                    "warning",
                    f"Discharge medication '{med_name}' is not in EHR medication history.",
                    weight=weights.get("medication_added", 4),
                    field="medications",
                )
            )

    # 3. diagnosis_mismatch_check (Warning) — compare ICD-10 codes.
    # Normalizer already attaches icd10/icd10_list via shared/clinical_normalize.py
    # apply_icd10_map(), so this stays a simple set comparison — no new logic.
    ehr_dx_codes = {str(c) for c in (patient.get("primary_dx") or [])}
    discharge_dx_codes = set(discharge.get("icd10_list") or [])
    if discharge.get("icd10"):
        discharge_dx_codes.add(str(discharge["icd10"]))
    discharge_dx_codes = {c for c in discharge_dx_codes if c}
    if ehr_dx_codes and discharge_dx_codes and not (ehr_dx_codes & discharge_dx_codes):
        findings.append(
            _finding(
                "diagnosis_mismatch_check",
                "warning",
                f"Discharge diagnosis codes {sorted(discharge_dx_codes)} do not match "
                f"EHR primary_dx {sorted(ehr_dx_codes)}.",
                weight=weights.get("diagnosis_mismatch", 4),
                field="discharge_diagnosis",
            )
        )

    # 4. follow_up_missing_check — Critical, absolute block (§16 row 12: FA5 wins).
    # Oracle (§12.3): missing only when care plan requires follow-up AND discharge
    # omits it. Documented follow-up (any wording) → no followup_missing flag.
    followup_text = (discharge.get("follow_up_appointment") or discharge.get("follow_up_appointments") or "").strip()
    if care_plan.get("followup_required") and not followup_text:
        findings.append(
            _finding(
                "follow_up_missing_check",
                "critical",
                f"Care plan requires {care_plan.get('speciality')} follow-up within "
                f"{care_plan.get('window_days')} days, but discharge omits it.",
                weight=weights.get("followup_missing", 2),
                blocking=True,
                field="follow_up_appointment",
            )
        )

    # 5. lab_follow_up_mismatch_check (Warning) — use EHR abnormal+action_in_ehr,
    # never the raw source ref range (§12.3). Odd source labels are ignored when
    # EHR says abnormal=False.
    if policies.get("abnormal_lab_requires_followup", True):
        for lab_row in ehr_labs:
            if lab_row.get("abnormal") and not (lab_row.get("action_in_ehr") or "").strip():
                findings.append(
                    _finding(
                        "lab_follow_up_mismatch_check",
                        "warning",
                        f"Abnormal lab '{lab_row.get('test')}' ({lab_row.get('value')}) "
                        "has no documented action_in_ehr.",
                        weight=weights.get("abnormal_lab_unresolved", 3),
                        field="labs",
                    )
                )

    _check_discharge_approved(discharge, findings)
    _check_bill_settlement(extraction, discharge, bill, weights, findings)
    _check_service_line_guardrails(patient, findings)
    return findings


# Hard HITL service lines from rules.yaml hitl_hard_guardrails (SSoT §6.3).
_SERVICE_LINE_GUARDRAILS = (
    ("service_line_pediatric", "pediatric"),
    ("service_line_obstetric", "obstetric"),
    ("service_line_oncology", "oncology"),
)


def _check_service_line_guardrails(patient: dict, findings: list[dict]) -> None:
    """Always HITL for pediatric / obstetric / oncology (SSoT §6.3)."""
    line = str(patient.get("service_line") or "").strip().lower()
    if not line:
        return
    for rule_id, needle in _SERVICE_LINE_GUARDRAILS:
        if needle in line:
            findings.append(
                _finding(
                    rule_id,
                    "critical",
                    f"Service line '{patient.get('service_line')}' always requires "
                    "Mandatory HITL (hard guardrail).",
                    blocking=True,
                    field="service_line",
                )
            )


def _check_discharge_approved(discharge: dict, findings: list[dict]) -> None:
    """6. discharge_approval_check — Critical, absolute block."""
    if not _is_truthy(discharge.get("discharge_approved")):
        findings.append(
            _finding(
                "discharge_approval_check",
                "critical",
                "Discharge is not marked as approved by the treating physician.",
                blocking=True,
                field="discharge_approved",
            )
        )


def _check_bill_settlement(
    extraction: dict,
    discharge: dict,
    bill: dict,
    weights: dict,
    findings: list[dict],
) -> None:
    """7. bill_settlement_check — Critical; bills live in intake, not EHR."""
    if "bill" not in extraction or extraction.get("bill") is None:
        findings.append(
            _finding(
                "bill_settlement_check",
                "critical",
                "Bill document is missing from the extraction — cannot confirm payment.",
                weight=weights.get("bill_unpaid_with_discharge_ok", 5),
                blocking=True,
                field="bill",
            )
        )
        return

    payment_status = (bill.get("payment_status") or "").strip().lower()
    if payment_status != "paid":
        weight = (
            weights.get("bill_unpaid_with_discharge_ok", 5)
            if _is_truthy(discharge.get("discharge_approved"))
            else 0
        )
        findings.append(
            _finding(
                "bill_settlement_check",
                "critical",
                f"Bill payment_status='{bill.get('payment_status') or 'unknown'}' — "
                "not settled before release.",
                weight=weight,
                blocking=True,
                field="payment_status",
            )
        )


def register_ehr_validation_tools(mcp: FastMCP) -> None:
    """Attach the EHR Validation tool to the Primary MCP server."""

    @mcp.tool(
        name="ehr_validation",
        title="EHR Validation Tool",
        description=(
            "Cross-check a normalized discharge extraction against Mock EHR "
            "medications, allergies, labs, and care plan — the 7 FA5 Table 4 "
            "rules. Allergy/medicine matching is canonical (§12.3)."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ehr_validation(patient_id: str, extraction: dict) -> str:
        """Run all cross-validation checks; return {"patient_id", "findings"}."""
        findings = await cross_validate(patient_id, extraction)
        logger.info("EHR validation patient=%s findings=%s", patient_id, len(findings))
        return json.dumps({"patient_id": patient_id, "findings": findings}, ensure_ascii=False, indent=2)
