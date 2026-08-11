"""Clinical Rules Engine Tool + Elicitation (SSoT §3.5, §3.7, §5.4 completeness).

Beginner picture:
  1. Check discharge fields against rules.yaml `mandatory_clinical_fields`.
  2. FA5 Table 3 says a few of those are BLOCKING if missing (patient_id,
     patient_name, discharge_diagnosis, discharge_approved, medications) —
     that "blocking" split is FA5-only, not in rules.yaml, so it is a small
     cited constant here (§6.1) rather than invented.
  3. Every OTHER missing mandatory field is non-blocking — batch them into
     ONE ctx.elicit() call so the reviewer can fill them in (SSoT §3.7).
  4. Any medication row missing medicine_name/strength/frequency/route is
     also blocking — `incomplete_prescription_fields` is a hard HITL
     guardrail in rules.yaml (§6.3), never elicited.
"""

from __future__ import annotations

import json

from fastmcp import Context, FastMCP

from mcp_servers.primary.elicitation import build_missing_fields_schema
from mcp_servers.primary.rules_loader import load_rules
from shared.logger import get_logger

logger = get_logger("clinical_rules_engine")

# FA5 Table 3 "Blocking If Missing" — Discharge Report.
BLOCKING_DISCHARGE_FIELDS = {
    "patient_id",
    "patient_name",
    "discharge_diagnosis",
    "discharge_approved",
    "medications",
}
# FA5 Table 3 "Blocking If Missing" — Prescription (per med).
BLOCKING_PRESCRIPTION_FIELDS = {"medicine_name", "strength", "frequency", "route"}

# FA5 Table 3 — Lab Report / Bill (checked when those packets exist).
LAB_REQUIRED_FIELDS = ("patient_id", "vendor_name", "lab_name", "report_date", "tests")
LAB_BLOCKING_FIELDS = {"patient_id", "tests"}
BILL_REQUIRED_FIELDS = (
    "patient_id",
    "hospital_name",
    "billing_date",
    "line_items",
    "total_amount",
    "payment_status",
)
BILL_BLOCKING_FIELDS = {"patient_id", "total_amount", "payment_status"}

# An empty list is a real, complete answer for these fields ("no known
# allergies" / "no additional consulting doctors") — do not flag it as a
# gap. Every other list field (e.g. medications) treats [] as missing.
_EMPTY_LIST_IS_VALID = {"allergies", "consulting_doctors"}

# Soft demographic gaps: score-only (rules.yaml missing_address / missing_gender).
# They never elicit and never hard-block — a case with only these can still
# auto-approve when total score stays <= low_max.
_SOFT_FIELD_WEIGHT_KEYS = {
    "address": "missing_address",
    "gender": "missing_gender",
}


def _is_missing(field: str, value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return field not in _EMPTY_LIST_IS_VALID
    return False


def _has_incomplete_prescription(medications: list[dict]) -> bool:
    """True if any medication row is missing a blocking prescription field."""
    for row in medications or []:
        for field in BLOCKING_PRESCRIPTION_FIELDS:
            if _is_missing(field, row.get(field)):
                return True
    return False


def _packet_findings(
    packet: dict,
    *,
    doc_label: str,
    required: tuple[str, ...],
    blocking: set[str],
    weights: dict,
) -> list[dict]:
    """FA5 Table 3 completeness findings for one lab or bill packet."""
    findings: list[dict] = []
    for field in required:
        if not _is_missing(field, packet.get(field)):
            continue
        is_blocking = field in blocking
        findings.append(
            {
                "rule_id": "missing_mandatory_field",
                "severity": "critical" if is_blocking else "warning",
                "message": (
                    f"{'Blocking' if is_blocking else 'Required'} {doc_label} field "
                    f"'{field}' is missing (FA5 Table 3)."
                ),
                "field": field,
                "weight": weights.get("missing_mandatory_field", 3) if is_blocking else 1,
                "blocking": is_blocking,
            }
        )
    return findings


def check_completeness(extraction: dict, rules: dict) -> tuple[list[dict], list[str]]:
    """Return (completeness_findings, fields_to_elicit) for one case.

    Findings may be blocking (FA5 Table 3) or soft/score-only (address/gender).
    Non-blocking mandatory gaps that are not soft go into fields_to_elicit.
    """
    discharge = extraction.get("discharge") or {}
    mandatory = list(rules.get("mandatory_clinical_fields", []))
    # FA5 Table 3 blocking field — not always in rules.yaml mandatory list.
    if "discharge_approved" not in mandatory:
        mandatory.append("discharge_approved")
    weights = rules.get("risk_scoring_matrix", {}).get("weights", {})

    findings: list[dict] = []
    to_elicit: list[str] = []

    for field in mandatory:
        if not _is_missing(field, discharge.get(field)):
            continue

        # Soft demographic — score only, never elicit / never hard-block.
        if field in _SOFT_FIELD_WEIGHT_KEYS:
            weight_key = _SOFT_FIELD_WEIGHT_KEYS[field]
            findings.append(
                {
                    "rule_id": weight_key,
                    "severity": "info",
                    "message": f"Soft demographic field '{field}' is missing.",
                    "field": field,
                    "weight": weights.get(weight_key, 1),
                    "blocking": False,
                }
            )
            continue

        if field in BLOCKING_DISCHARGE_FIELDS:
            findings.append(
                {
                    "rule_id": "missing_mandatory_field",
                    "severity": "critical",
                    "message": f"Blocking field '{field}' is missing (FA5 Table 3).",
                    "field": field,
                    "weight": weights.get("missing_mandatory_field", 3),
                    "blocking": True,
                }
            )
        else:
            to_elicit.append(field)

    if _has_incomplete_prescription(discharge.get("medications") or []):
        findings.append(
            {
                "rule_id": "incomplete_prescription_fields",
                "severity": "critical",
                "message": (
                    "One or more medications is missing medicine_name/"
                    "strength/frequency/route."
                ),
                "field": "medications",
                "weight": weights.get("incomplete_prescription_fields", 4),
                "blocking": True,
            }
        )

    # Lab / Bill packets — only when present in the extraction (SSoT §6.1 Table 3).
    if extraction.get("lab") is not None:
        findings.extend(
            _packet_findings(
                extraction.get("lab") or {},
                doc_label="lab",
                required=LAB_REQUIRED_FIELDS,
                blocking=LAB_BLOCKING_FIELDS,
                weights=weights,
            )
        )
    if extraction.get("bill") is not None:
        findings.extend(
            _packet_findings(
                extraction.get("bill") or {},
                doc_label="bill",
                required=BILL_REQUIRED_FIELDS,
                blocking=BILL_BLOCKING_FIELDS,
                weights=weights,
            )
        )

    return findings, to_elicit


# Fields the schema stores as a plain string but the extraction shape
# expects as a list (elicitation only supports flat primitives — §3.7).
_LIST_SHAPED_FIELDS = {"consulting_doctors", "allergies"}


def _apply_elicited_values(discharge: dict, elicited: dict) -> dict:
    updated = dict(discharge)
    for key, value in elicited.items():
        if value is None:
            continue
        if key in _LIST_SHAPED_FIELDS and isinstance(value, str):
            updated[key] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            updated[key] = value
    return updated


def register_rules_engine_tools(mcp: FastMCP) -> None:
    """Attach the Clinical Rules Engine tool to the Primary MCP server."""

    @mcp.tool(
        name="clinical_rules_engine",
        title="Clinical Rules Engine Tool",
        description=(
            "Check completeness of a discharge extraction against rules.yaml "
            "mandatory fields (SSoT §6.1). Blocking gaps are returned as "
            "findings; non-blocking gaps trigger ONE MCP Elicitation call so "
            "a reviewer can fill them in (accept/decline/cancel)."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def clinical_rules_engine(patient_id: str, extraction: dict, ctx: Context) -> str:
        """Run completeness + (if needed) one elicitation; return JSON findings."""
        rules = load_rules()
        findings, to_elicit = check_completeness(extraction, rules)

        elicitation_outcome: str | None = None
        elicited_values: dict = {}
        updated_extraction = extraction

        if to_elicit:
            schema = build_missing_fields_schema(to_elicit)
            logger.info("Eliciting %s missing field(s) for %s", len(to_elicit), patient_id)
            try:
                result = await ctx.elicit(
                    message=(
                        f"Patient {patient_id}: please supply these missing discharge "
                        f"fields if available, or decline: {', '.join(to_elicit)}"
                    ),
                    response_type=schema,
                )
                elicitation_outcome = result.action
                if result.action == "accept" and result.data is not None:
                    raw = result.data
                    if hasattr(raw, "model_dump"):
                        elicited_values = raw.model_dump(exclude_none=True)
                    elif isinstance(raw, dict):
                        elicited_values = {
                            k: v for k, v in raw.items() if v is not None
                        }
                    else:
                        elicited_values = {}
                    discharge = _apply_elicited_values(
                        extraction.get("discharge") or {}, elicited_values
                    )
                    updated_extraction = dict(extraction)
                    updated_extraction["discharge"] = discharge
                    to_elicit = [f for f in to_elicit if f not in elicited_values]
            except Exception as exc:
                # Bad accept payload must not abort the whole Rules Engine tool
                logger.warning(
                    "Elicitation failed for %s (%s) — treating as decline",
                    patient_id,
                    exc,
                )
                elicitation_outcome = "decline"

        payload = {
            "patient_id": patient_id,
            # Includes both hard-blocking gaps and soft score-only findings.
            "completeness_findings": findings,
            "missing_fields": to_elicit,
            "elicitation_outcome": elicitation_outcome,
            "elicited_values": elicited_values,
            "extraction": updated_extraction,
        }
        logger.info(
            "Completeness patient=%s findings=%s to_elicit=%s outcome=%s",
            patient_id,
            len(findings),
            len(to_elicit),
            elicitation_outcome,
        )
        return json.dumps(payload, ensure_ascii=False, indent=2)
