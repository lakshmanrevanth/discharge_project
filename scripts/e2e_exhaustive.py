"""Exhaustive extract → normalize → validate for corpus + synthetic patients.

Requires Mock EHR :8050, Primary MCP :8200, Secondary MCP :8201, Bedrock.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.extractor.graph import run_extraction
from agents.normalizer.graph import run_normalization
from agents.validator.elicitation_handler import (
    reset_elicitation_handler,
    set_elicitation_handler,
)
from agents.validator.graph import run_validation
from fastmcp.client.elicitation import ElicitResult
from shared.clinical_normalize import canonicalize_med_name


async def _e2e_accept_elicitation(message, response_type, params, context):
    """Headless accept so soft-field gaps do not force decline→High HITL."""
    data = params.get("elicited_values") if isinstance(params, dict) else None
    data = data or {}
    if response_type is not None:
        try:
            model = response_type(**data) if data else response_type()
            payload = model.model_dump(exclude_none=True)
            return ElicitResult(action="accept", content=payload)
        except Exception:
            try:
                payload = response_type().model_dump(exclude_none=True)
                return ElicitResult(action="accept", content=payload)
            except Exception:
                pass
    return ElicitResult(action="accept", content=dict(data))

OUT = ROOT / "data" / "reports" / "e2e_exhaustive_results.json"

# patient_id -> expectations
EXPECT = {
    "P1019": {
        "blocked": False,
        "must_not": ["allergy_contradiction_check"],
        "risk_max": "low",
    },
    "P1020": {
        "blocked": False,
        "must_not": ["allergy_contradiction_check"],
        "risk_max": "low",
    },
    "P1021": {
        "blocked": True,
        "must_not": ["allergy_contradiction_check"],
        "must_any": ["follow_up_missing_check", "bill_settlement_check"],
    },
    "P1022": {
        "blocked": True,
        "must": ["allergy_contradiction_check"],
        "must_not": ["follow_up_missing_check", "incomplete_prescription_fields"],
        "meds_complete": True,
        "has_diagnosis": True,
    },
    "P1023": {
        "blocked": False,
        "must_not": ["allergy_contradiction_check"],
        "risk_max": "low",
    },
    "P1024": {
        "blocked": True,
        "must": ["allergy_contradiction_check"],
        "must_not": ["follow_up_missing_check"],
    },
    # Synthetic
    "P9991": {
        "blocked": False,
        "must_not": [
            "allergy_contradiction_check",
            "medication_added",
            "med_omission_check",
            "incomplete_prescription_fields",
        ],
        "paracetamol_reconciles": True,
    },
    "P9992": {
        "blocked": True,
        "must": ["allergy_contradiction_check"],
    },
    "P9993": {
        "blocked": False,
        "must_not": [
            "medication_added",
            "med_omission_check",
            "incomplete_prescription_fields",
        ],
        "paracetamol_reconciles": True,
    },
    "P9994": {
        "blocked": False,
        "must_not": [
            "medication_added",
            "med_omission_check",
            "allergy_contradiction_check",
        ],
    },
    "P9995": {
        "blocked": True,
        "must": ["allergy_contradiction_check"],
    },
}

_RISK = {"low": 0, "medium": 1, "high": 2}


def _rule_ids(report: dict) -> set[str]:
    ids: set[str] = set()
    for key in (
        "findings",
        "all_findings",
        "completeness_issues",
        "ehr_issues",
        "risk_findings",
    ):
        for f in report.get(key) or []:
            if isinstance(f, dict) and f.get("rule_id"):
                ids.add(str(f["rule_id"]))
    return ids


def _discharge_med_names(norm: dict) -> list[str]:
    discharge = (norm.get("normalized_extraction") or {}).get("discharge") or {}
    if not discharge and isinstance(norm.get("discharge"), dict):
        discharge = norm["discharge"]
    meds = discharge.get("medications") or []
    return [
        canonicalize_med_name(m.get("medicine_name") or m.get("name") or "")
        for m in meds
        if isinstance(m, dict)
    ]


def _has_diagnosis(norm: dict) -> bool:
    discharge = (norm.get("normalized_extraction") or {}).get("discharge") or {}
    if not discharge and isinstance(norm.get("discharge"), dict):
        discharge = norm["discharge"]
    dx = discharge.get("discharge_diagnosis") or []
    return bool(dx)


def _meds_complete(norm: dict) -> bool:
    discharge = (norm.get("normalized_extraction") or {}).get("discharge") or {}
    if not discharge and isinstance(norm.get("discharge"), dict):
        discharge = norm["discharge"]
    for m in discharge.get("medications") or []:
        if not isinstance(m, dict):
            return False
        for field in ("medicine_name", "strength", "frequency", "route"):
            if not str(m.get(field) or "").strip():
                return False
    return bool(discharge.get("medications"))


async def _run_one(pid: str) -> dict:
    exp = EXPECT[pid]
    errors: list[str] = []
    token = set_elicitation_handler(_e2e_accept_elicitation)
    try:
        try:
            ext = await run_extraction(pid)
            norm = await run_normalization(pid, ext)
            report = await run_validation(pid, norm)
        except Exception as exc:  # noqa: BLE001
            return {"patient_id": pid, "ok": False, "errors": [f"pipeline: {exc}"]}
    finally:
        reset_elicitation_handler(token)

    rules = _rule_ids(report if isinstance(report, dict) else {})
    blocked = bool((report or {}).get("discharge_blocked"))

    risk = (
        ((report or {}).get("risk") or {}).get("level")
        or (report or {}).get("risk_level")
        or "unknown"
    )

    if exp.get("blocked") is True and not blocked:
        errors.append(f"expected blocked, got blocked={blocked} risk={risk}")
    if exp.get("blocked") is False and blocked:
        errors.append(f"expected not blocked, got blocked={blocked} rules={sorted(rules)}")

    for rid in exp.get("must") or []:
        if rid not in rules:
            errors.append(f"missing required rule {rid}")
    for rid in exp.get("must_not") or []:
        if rid in rules:
            errors.append(f"unexpected rule {rid}")
    if exp.get("must_any"):
        if not any(r in rules for r in exp["must_any"]):
            errors.append(f"expected one of {exp['must_any']}, got {sorted(rules)}")

    if "risk_max" in exp and risk in _RISK:
        if _RISK[risk] > _RISK[exp["risk_max"]]:
            errors.append(f"risk {risk} exceeds max {exp['risk_max']}")

    meds = _discharge_med_names(norm if isinstance(norm, dict) else {})
    if exp.get("meds_complete") and not _meds_complete(norm):
        errors.append(f"incomplete meds: {meds}")
    if exp.get("has_diagnosis") and not _has_diagnosis(norm):
        errors.append("missing discharge_diagnosis")
    if exp.get("paracetamol_reconciles"):
        if "Paracetamol" not in meds:
            errors.append(f"expected Paracetamol after canonicalize, got {meds}")
        if "medication_added" in rules or "med_omission_check" in rules:
            errors.append("Paracetamol/Acetaminophen failed to reconcile with EHR")

    return {
        "patient_id": pid,
        "ok": not errors,
        "blocked": blocked,
        "risk": risk,
        "rules": sorted(rules),
        "meds": meds,
        "errors": errors,
    }


async def main() -> int:
    results = []
    for pid in EXPECT:
        print(f"=== {pid} ===", flush=True)
        row = await _run_one(pid)
        results.append(row)
        status = "PASS" if row["ok"] else "FAIL"
        print(f"  {status} blocked={row.get('blocked')} risk={row.get('risk')} meds={row.get('meds')}")
        for e in row.get("errors") or []:
            print(f"   - {e}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed → {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
