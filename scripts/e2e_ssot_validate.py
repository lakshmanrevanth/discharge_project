"""Real end-to-end SSoT §12.1 validation for corpus patients P1019–P1024.

Requires live Mock EHR :8050, Primary MCP :8200, Secondary MCP :8201, and AWS Bedrock.
No mocks — Extractor → Normalizer → Validator (+ Monitor / RAG / Summary checks).
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.extractor.graph import run_extraction
from agents.monitor.agent import discover_clinical_intake
from agents.normalizer.graph import run_normalization
from agents.summary.agent import run_summary
from agents.validator.graph import run_validation
from rag.pipeline import ask
from shared.guardrails.guardrail_manager import evaluate_hitl_escalation

OUT = ROOT / "data" / "reports" / "e2e_ssot_results.json"

# SSoT §12.1 expected outcomes (validation oracle)
EXPECT = {
    "P1019": {
        "auto_approve": True,
        "blocked": False,
        "risk_max": "low",  # must be low
        "must_not_rules": ["allergy_contradiction_check"],
    },
    "P1020": {
        "auto_approve": True,
        "blocked": False,
        "risk_max": "low",
        "must_not_rules": ["allergy_contradiction_check"],
    },
    "P1021": {
        "auto_approve": False,
        "blocked": True,
        "must_any_rules": [
            "follow_up_missing_check",
            "bill_settlement_check",
        ],
        "must_not_rules": ["allergy_contradiction_check"],
    },
    "P1022": {
        "auto_approve": False,
        "blocked": True,
        "risk_min": "high",
        "must_rules": ["allergy_contradiction_check"],
        "must_not_rules": ["follow_up_missing_check"],
    },
    "P1023": {
        "auto_approve": True,
        "blocked": False,
        "risk_max": "low",
        "must_not_rules": ["allergy_contradiction_check"],
    },
    "P1024": {
        "auto_approve": False,
        "blocked": True,
        "risk_min": "high",
        "must_rules": ["allergy_contradiction_check"],
        "must_not_rules": ["follow_up_missing_check"],
    },
}

_RISK_RANK = {"low": 0, "medium": 1, "high": 2}


def _rule_ids(report: dict) -> set[str]:
    ids: set[str] = set()
    for bucket in (
        "completeness_issues",
        "ehr_discrepancies",
        "medication_conflicts",
        "findings",
        "all_findings",
    ):
        for item in report.get(bucket) or []:
            if isinstance(item, dict) and item.get("rule_id"):
                ids.add(str(item["rule_id"]))
    # nested audit trail
    trail = report.get("audit_trail") or {}
    for item in trail.get("findings") or []:
        if isinstance(item, dict) and item.get("rule_id"):
            ids.add(str(item["rule_id"]))
    return ids


def _check_patient(pid: str, report: dict) -> list[str]:
    exp = EXPECT[pid]
    fails: list[str] = []
    risk = str(report.get("risk_level") or "").lower()
    blocked = bool(report.get("discharge_blocked"))
    gate = report.get("release_gate") or evaluate_hitl_escalation(risk, blocked)
    auto = bool(gate.get("auto_approve_allowed"))
    rules = _rule_ids(report)

    if exp.get("auto_approve") is True and not auto:
        fails.append(f"expected auto-approve, got gate={gate.get('action')} risk={risk} blocked={blocked}")
    if exp.get("auto_approve") is False and auto:
        fails.append(f"expected HITL, got auto-approve risk={risk} blocked={blocked}")
    if "blocked" in exp and blocked != exp["blocked"]:
        fails.append(f"discharge_blocked expected {exp['blocked']}, got {blocked}")
    if "risk_max" in exp and _RISK_RANK.get(risk, 99) > _RISK_RANK[exp["risk_max"]]:
        fails.append(f"risk expected <= {exp['risk_max']}, got {risk}")
    if "risk_min" in exp and _RISK_RANK.get(risk, -1) < _RISK_RANK[exp["risk_min"]]:
        fails.append(f"risk expected >= {exp['risk_min']}, got {risk}")
    for rid in exp.get("must_rules") or []:
        if rid not in rules:
            fails.append(f"missing required rule_id={rid}; have={sorted(rules)}")
    must_any = exp.get("must_any_rules") or []
    if must_any and not any(r in rules for r in must_any):
        fails.append(f"expected one of {must_any}; have={sorted(rules)}")
    for rid in exp.get("must_not_rules") or []:
        if rid in rules:
            fails.append(f"unexpected rule_id={rid}")
    return fails


async def run_one(pid: str) -> dict:
    print(f"\n===== {pid} extract → normalize → validate =====", flush=True)
    ext = await run_extraction(pid)
    print(f"{pid} extraction keys={list(ext.keys()) if isinstance(ext, dict) else type(ext)}", flush=True)
    norm = await run_normalization(pid, ext)
    print(
        f"{pid} lang={norm.get('source_language')} conf={norm.get('translation_confidence')}",
        flush=True,
    )
    report = await run_validation(pid, norm)
    fails = _check_patient(pid, report)
    status = "PASS" if not fails else "FAIL"
    print(f"{pid} RESULT {status} risk={report.get('risk_level')} blocked={report.get('discharge_blocked')} rules={sorted(_rule_ids(report))}", flush=True)
    if fails:
        for f in fails:
            print(f"  - {f}", flush=True)
    return {
        "patient_id": pid,
        "status": status,
        "failures": fails,
        "risk_level": report.get("risk_level"),
        "risk_score": report.get("risk_score"),
        "discharge_blocked": report.get("discharge_blocked"),
        "release_gate": report.get("release_gate"),
        "rule_ids": sorted(_rule_ids(report)),
        "source_language": norm.get("source_language"),
        "translation_confidence": norm.get("translation_confidence"),
        "report": report,
        "normalized_extraction": norm.get("normalized_extraction"),
        "normalization_notes": norm.get("notes"),
        "extraction_notes": ext.get("notes") if isinstance(ext, dict) else None,
    }


async def main() -> int:
    patients = ["P1019", "P1020", "P1021", "P1022", "P1023", "P1024"]
    results: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patients": [],
        "monitor_ok": False,
        "monitor_preview": "",
        "rag": {},
        "summary_p1019": {},
        "summary_p1022_gate": {},
    }

    # Monitor (live Primary watcher)
    try:
        preview = await discover_clinical_intake()
        results["monitor_ok"] = bool(preview)
        results["monitor_preview"] = (preview or "")[:500]
        print("Monitor OK", flush=True)
    except Exception as exc:
        results["monitor_preview"] = str(exc)
        print("Monitor FAIL", exc, flush=True)

    for pid in patients:
        try:
            row = await run_one(pid)
        except Exception as exc:
            print(f"{pid} ERROR {exc}", flush=True)
            traceback.print_exc()
            row = {
                "patient_id": pid,
                "status": "FAIL",
                "failures": [str(exc)],
                "error": traceback.format_exc()[-2000:],
            }
        results["patients"].append(row)

    # RAG — real in-context + refusal (P1019)
    print("\n===== RAG =====", flush=True)
    try:
        hit = await ask("P1019", "What medications were prescribed at discharge?")
        miss = await ask("P1019", "What is the capital of France and today's stock price of AAPL?")
        results["rag"] = {
            "in_context_ok": bool(hit.get("answer")) and not hit.get("refused"),
            "refusal_ok": bool(miss.get("refused")),
            "sample_answer": (hit.get("answer") or "")[:400],
            "refusal_answer": (miss.get("answer") or "")[:200],
            "hit_notes": hit.get("notes"),
            "miss_notes": miss.get("notes"),
        }
        print("RAG", results["rag"]["in_context_ok"], results["rag"]["refusal_ok"], flush=True)
    except Exception as exc:
        results["rag"] = {"error": str(exc)}
        print("RAG ERROR", exc, flush=True)

    # Summary — auto-approve case should generate; hard-HITL should refuse/gate
    print("\n===== Summary =====", flush=True)
    by_pid = {p["patient_id"]: p for p in results["patients"]}
    p1019 = by_pid.get("P1019") or {}
    p1022 = by_pid.get("P1022") or {}
    try:
        if p1019.get("report"):
            rep = p1019["report"]
            summ = await run_summary(
                patient_id="P1019",
                risk_level=str(rep.get("risk_level") or "low"),
                discharge_blocked=bool(rep.get("discharge_blocked")),
                extraction=p1019.get("normalized_extraction") or {},
                audience="patient",
            )
            results["summary_p1019"] = {
                "ok": not summ.refused and bool(summ.sections),
                "refused": summ.refused,
                "sections": list(summ.sections.keys()),
                "refuse_reason": summ.refuse_reason,
            }
            print("Summary P1019", results["summary_p1019"], flush=True)
    except Exception as exc:
        results["summary_p1019"] = {"ok": False, "error": str(exc)}
        print("Summary P1019 ERROR", exc, flush=True)

    try:
        if p1022.get("report"):
            rep = p1022["report"]
            summ = await run_summary(
                patient_id="P1022",
                risk_level=str(rep.get("risk_level") or "high"),
                discharge_blocked=True,
                extraction=p1022.get("normalized_extraction") or {},
                audience="patient",
            )
            results["summary_p1022_gate"] = {
                "ok": bool(summ.refused),  # must refuse when gated
                "refused": summ.refused,
                "refuse_reason": summ.refuse_reason,
                "sections": list(summ.sections.keys()),
            }
            print("Summary P1022 gate", results["summary_p1022_gate"], flush=True)
    except Exception as exc:
        results["summary_p1022_gate"] = {"ok": False, "error": str(exc)}
        print("Summary P1022 ERROR", exc, flush=True)

    passed = sum(1 for p in results["patients"] if p.get("status") == "PASS")
    failed = len(results["patients"]) - passed
    results["summary"] = {"total": len(results["patients"]), "passed": passed, "failed": failed}
    results["rag_ok"] = bool(results.get("rag", {}).get("in_context_ok")) and bool(
        results.get("rag", {}).get("refusal_ok")
    )
    results["summary_ok"] = bool(results.get("summary_p1019", {}).get("ok")) and bool(
        results.get("summary_p1022_gate", {}).get("ok")
    )
    results["monitor_checked"] = results["monitor_ok"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Slim copy for readability (full reports still included for forensics)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\n===== E2E DONE =====", flush=True)
    print(json.dumps(results["summary"], indent=2), flush=True)
    for p in results["patients"]:
        print(f"  {p['patient_id']}: {p.get('status')} — {p.get('failures')}", flush=True)
    print("Wrote", OUT, flush=True)
    return 0 if failed == 0 and results["rag_ok"] and results["summary_ok"] and results["monitor_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
