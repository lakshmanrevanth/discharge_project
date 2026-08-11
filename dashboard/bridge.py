"""Bridge HITL UI → V3 Host / Monitor / Validator / RAG / Summary.

No duplicated clinical rules — agents own risk / allergy / bill logic.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from shared.guardrails.guardrail_manager import evaluate_hitl_escalation
from shared.settings import REPO_ROOT, get_path

SECTION_TITLES = {
    "patient": "Patient overview",
    "meds": "Medications",
    "labs": "Laboratory results",
    "bill": "Billing",
    "instructions": "Discharge instructions",
}


def _run(coro):
    """Run an async coroutine from sync Streamlit handlers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def _input_root() -> Path:
    try:
        return get_path("data_input")
    except Exception:
        return REPO_ROOT / "data" / "input"


def list_patient_documents(patient_id: str) -> dict[str, Any]:
    """List intake files for one patient (Roots-safe paths under data/input)."""
    pid = str(patient_id).strip().upper()
    root = _input_root()
    files: list[dict[str, Any]] = []
    mapping = {
        "doctor_reports": "discharge",
        "lab_reports": "lab",
        "bills": "bill",
    }
    for folder, doc_type in mapping.items():
        d = root / folder
        if not d.is_dir():
            continue
        for path in sorted(d.iterdir()):
            if not path.is_file():
                continue
            if pid.lower() not in path.name.lower():
                continue
            # Prefer text / OCR sidecars in the list; still include binaries
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "abs_path": str(path),
                    "name": path.name,
                    "doc_type": doc_type,
                    "suffix": path.suffix.lower(),
                    "size": path.stat().st_size,
                }
            )
    # Optional Monitor enrichment (non-fatal if MCP down)
    try:
        from agents.monitor.agent import discover_clinical_intake

        raw = _run(discover_clinical_intake())
        preview = json.loads(raw) if isinstance(raw, str) and raw.strip().startswith("{") else {}
        return {"files": files, "monitor": preview, "patient_id": pid}
    except Exception as exc:
        return {"files": files, "patient_id": pid, "monitor_error": str(exc)}


def read_doc_preview(rel_or_abs: str, limit: int = 6000) -> str:
    root = _input_root()
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = root / rel_or_abs
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return "[path outside roots — blocked]"
    if not path.exists():
        return "[file missing]"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf"}:
        sidecar = Path(str(path) + ".ocr.txt")
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8", errors="replace")[:limit]
        return f"[{path.suffix} binary — open OCR sidecar if available]"
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def _findings_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in (
        "all_findings",
        "findings",
        "completeness_issues",
        "ehr_discrepancies",
        "medication_conflicts",
    ):
        for item in report.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            key = f"{item.get('rule_id')}|{item.get('message')}|{item.get('field')}"
            if key in seen:
                continue
            seen.add(key)
            row = dict(item)
            # UI chrome expects action labels
            if not row.get("action"):
                row["action"] = "Block" if row.get("blocking") else "Score"
            if row.get("severity"):
                row["severity"] = str(row["severity"]).title()
            findings.append(row)
    return findings


def normalize_validation(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """Map V3 Clinical Insight Reporter → HITL validation shape."""
    if not report:
        return None
    findings = _findings_from_report(report)
    risk_level = str(report.get("risk_level") or "low")
    blocked = bool(report.get("discharge_blocked"))
    gate = report.get("release_gate") or evaluate_hitl_escalation(risk_level, blocked)
    needs_hitl = not bool(gate.get("auto_approve_allowed"))

    soft: list[str] = []
    blocking: list[str] = []
    for f in findings:
        field = str(f.get("field") or "").strip()
        rule = str(f.get("rule_id") or "")
        if rule.startswith("elicitation_"):
            # Gate note — show elicited field names under Soft gaps for the reviewer.
            msg = str(f.get("message") or "")
            m = re.search(r"\(([^)]+)\)", msg)
            if m and "no fields listed" not in m.group(1).lower():
                for part in m.group(1).split(","):
                    name = part.strip()
                    if name and name not in soft:
                        soft.append(name)
            continue
        if rule in {"missing_address", "missing_gender"} and field:
            soft.append(field)
        elif f.get("blocking") or str(f.get("severity") or "").lower() == "critical":
            if field:
                blocking.append(field)
            elif rule:
                blocking.append(rule)
    # Completeness missing_fields from reporter
    for field in report.get("missing_fields") or []:
        text = str(field).strip()
        if text and text not in soft and text not in blocking:
            soft.append(text)

    uris = {}
    trail = report.get("audit_trail") or {}
    if trail.get("json_path"):
        uris["json"] = trail["json_path"]
    if trail.get("html_path"):
        uris["html"] = trail["html_path"]
    # Common on-disk locations
    json_path = REPO_ROOT / "data" / "reports" / f"{report.get('patient_id')}_report.json"
    html_path = REPO_ROOT / "data" / "reports" / f"{report.get('patient_id')}_report.html"
    if json_path.exists():
        uris.setdefault("json", str(json_path))
    if html_path.exists():
        uris.setdefault("html", str(html_path))

    return {
        **report,
        "findings": findings,
        "risk": {
            "level": risk_level,
            "score": report.get("risk_score"),
        },
        "discharge_blocked": blocked,
        "needs_hitl": needs_hitl,
        "missing_soft": soft,
        "missing_blocking": blocking,
        "rules_version": report.get("rules_version"),
        "report_uris": uris,
        "release_gate": gate,
    }


def fetch_ehr_medications(patient_id: str) -> list[dict[str, Any]]:
    """Load Mock EHR meds for HITL table seed (any patient_id). Never invent rows."""
    pid = str(patient_id or "").strip().upper()
    if not pid:
        return []
    try:
        import httpx
        from shared.settings import get_service

        ehr = get_service("mock_ehr")
        base = f"http://{ehr.get('host', '127.0.0.1')}:{int(ehr.get('port', 8050))}"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{base}/patients/{pid}/medications")
            if resp.status_code != 200:
                return []
            payload = resp.json()
        raw = payload.get("medications") if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for m in raw:
            if not isinstance(m, dict):
                continue
            name = (m.get("name") or m.get("medicine_name") or "").strip()
            if not name:
                continue
            out.append(
                {
                    "medicine_name": name,
                    "name": name,
                    "strength": m.get("dose") or m.get("strength") or "",
                    "frequency": m.get("frequency") or "",
                    "route": m.get("route") or "",
                    "period": m.get("period") or "",
                }
            )
        return out
    except Exception as exc:
        from shared.logger import get_logger

        get_logger("dashboard_bridge").info("EHR meds seed skipped for %s: %s", pid, exc)
        return []


def case_from_normalization(norm: dict[str, Any]) -> dict[str, Any]:
    """Flatten V3 normalization into a HITL working case dict."""
    ne = norm.get("normalized_extraction") or {}
    discharge = dict(ne.get("discharge") or {})
    bill = ne.get("bill") if isinstance(ne.get("bill"), dict) else {}
    meds = list(discharge.get("medications") or [])
    meds_source = "discharge"
    pid = str(norm.get("patient_id") or discharge.get("patient_id") or "").strip().upper()
    # HITL table must not be blank for new patients — seed from Mock EHR when needed
    if not meds and pid:
        ehr_meds = fetch_ehr_medications(pid)
        if ehr_meds:
            meds = ehr_meds
            meds_source = "ehr"
    case: dict[str, Any] = {
        **discharge,
        "patient_id": pid or discharge.get("patient_id"),
        "bill": bill,
        "medications": meds,
        "allergies": list(discharge.get("allergies") or discharge.get("adr_allergy_info") or []),
        "follow_up_appointment": (
            discharge.get("follow_up_appointment")
            or discharge.get("follow_up_appointments")
            or ""
        ),
        "discharge_ok": bool(discharge.get("discharge_approved")),
        "_meds_source": meds_source,
        "_normalization": norm,
        "_normalized_extraction": ne,
    }
    return case


def case_after_validation(
    norm: dict[str, Any],
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build HITL case preferring extraction after Rules Engine elicitation.

    ``run_validation`` returns the audit report plus
    ``extraction_after_elicitation`` (callback fills). Critical edits alone
    used to reindex from pre-validate ``norm``, which dropped soft elicitation.
    """
    post = (report or {}).get("extraction_after_elicitation")
    if isinstance(post, dict) and post:
        base = dict(norm or {})
        base["normalized_extraction"] = post
        if not base.get("patient_id"):
            base["patient_id"] = (report or {}).get("patient_id") or norm.get("patient_id")
        return case_from_normalization(base)
    return case_from_normalization(norm or {})


def case_to_normalization(case: dict[str, Any]) -> dict[str, Any]:
    """Push HITL case edits back into a NormalizationResult-shaped dict."""
    base = dict(case.get("_normalization") or {})
    ne = dict(case.get("_normalized_extraction") or {})
    discharge = dict(ne.get("discharge") or {})

    # Overlay editable fields
    for key in (
        "patient_id",
        "patient_name",
        "age",
        "gender",
        "address",
        "admission_date",
        "discharge_date",
        "ward",
        "bed_no",
        "attending_physician",
        "consulting_doctors",
        "discharge_diagnosis",
        "medications",
        "allergies",
        "follow_up_appointment",
        "discharge_instructions",
    ):
        if key in case:
            discharge[key] = case[key]
    if "discharge_ok" in case:
        discharge["discharge_approved"] = bool(case.get("discharge_ok"))
    if case.get("follow_up_appointment"):
        discharge["follow_up_appointments"] = case["follow_up_appointment"]
    if case.get("allergies") is not None:
        discharge["adr_allergy_info"] = list(case.get("allergies") or [])

    ne["discharge"] = discharge
    if isinstance(case.get("bill"), dict):
        ne["bill"] = case["bill"]
    base["normalized_extraction"] = ne
    base["patient_id"] = case.get("patient_id") or base.get("patient_id")
    if "translation_confidence" not in base:
        base["translation_confidence"] = 1.0
    return base


def load_working_case(patient_id: str) -> dict[str, Any]:
    """Load a case from a prior report or a minimal shell (no fake clinical data)."""
    pid = str(patient_id).strip().upper()
    # Prefer last audit report on disk
    report_path = REPO_ROOT / "data" / "reports" / f"{pid}_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            # Reports don't always embed full extraction — shell only
            return {
                "patient_id": pid,
                "patient_name": report.get("patient_name") or "",
                "medications": [],
                "allergies": [],
                "bill": {
                    "payment_status": report.get("bill_payment_status"),
                    "total_amount": report.get("bill_amount"),
                },
                "follow_up_appointment": "",
                "discharge_ok": False,
            }
        except Exception:
            pass
    return {
        "patient_id": pid,
        "medications": [],
        "allergies": [],
        "bill": {},
        "follow_up_appointment": "",
        "discharge_ok": False,
    }


def _normalize_summary(summary_obj: Any) -> dict[str, Any] | None:
    if summary_obj is None:
        return None
    if hasattr(summary_obj, "model_dump"):
        data = summary_obj.model_dump()
    elif isinstance(summary_obj, dict):
        data = dict(summary_obj)
    else:
        return None
    if data.get("refused"):
        return None
    # Convert sections dict → list[{name, markdown}] for hero renderer
    sections = data.get("sections")
    if isinstance(sections, dict):
        data["sections"] = [
            {"name": k, "markdown": v}
            for k, v in sections.items()
            if str(v or "").strip()
        ]
    return data


async def _local_pipeline(patient_id: str) -> dict[str, Any]:
    """Extract → Normalize → Validate → Index → Gate → Summary (V3 graphs).

    The whole run sits inside ONE LangFuse case trace, so (a) every agent span
    nests under a single Host Agent root and (b) the trace_id handed to the UI
    is the id LangFuse actually ingested. A local uuid4 here produced a sidebar
    link to a trace that does not exist — the page then loads forever.
    """
    from shared.tracing.langfuse import case_trace

    with case_trace(patient_id) as tid:
        return await _local_pipeline_run(patient_id, tid)


async def _local_pipeline_run(patient_id: str, tid: str) -> dict[str, Any]:
    """Body of the local pipeline, running inside an open case trace."""
    from agents.extractor.graph import run_extraction
    from agents.normalizer.graph import run_normalization
    from agents.summary.agent import run_summary
    from agents.validator.graph import run_validation
    from rag.indexing_agent import run_indexing

    stages: list[str] = ["monitor"]
    try:
        from agents.monitor.agent import discover_clinical_intake

        await discover_clinical_intake()
    except Exception:
        pass

    ext = await run_extraction(patient_id)
    stages.append("extract")
    norm = await run_normalization(patient_id, ext)
    stages.append("normalize")
    report = await run_validation(patient_id, norm)
    stages.append("validate")
    validation = normalize_validation(report) or {}
    case = case_from_normalization(norm)

    indexed = False
    try:
        await run_indexing(patient_id)
        indexed = True
        stages.append("index")
    except Exception as exc:
        return {
            "trace_id": tid,
            "patient_id": patient_id,
            "case": case,
            "validation": validation,
            "summary": None,
            "stages_run": stages,
            "indexed": False,
            "needs_hitl": bool(validation.get("needs_hitl")),
            "discharge_blocked": bool(validation.get("discharge_blocked")),
            "gate": {
                "allow_summary": not bool(validation.get("needs_hitl")),
                "reason": f"index_error: {exc}",
            },
            "error": f"index_error: {exc}",
            "status": "partial",
        }

    stages.append("gate")
    blocked = bool(validation.get("discharge_blocked"))
    needs = bool(validation.get("needs_hitl"))
    allow = not (blocked or needs)
    summary = None
    if allow:
        stages.append("summary_or_hitl")
        summ = await run_summary(
            patient_id=patient_id,
            risk_level=str((validation.get("risk") or {}).get("level") or "low"),
            discharge_blocked=False,
            extraction=norm.get("normalized_extraction") or {},
            audience="patient",
        )
        summary = _normalize_summary(summ)
    else:
        # Host may list the stage even when withheld — UI must show skipped
        stages.append("summary_or_hitl")

    return {
        "trace_id": tid,
        "patient_id": patient_id,
        "case": case,
        "validation": validation,
        "summary": summary,
        "stages_run": stages,
        "indexed": indexed,
        "needs_hitl": needs,
        "discharge_blocked": blocked,
        "gate": {
            "allow_summary": allow,
            "reason": None if allow else "mandatory_hitl_or_blocked",
        },
        "status": "ok",
    }


def run_host_pipeline(patient_id: str, *, use_fixture: bool = True) -> dict[str, Any]:
    """Run the full case pipeline via V3 agent graphs (same clinical path as Host).

    ``use_fixture`` is accepted for UI compatibility; V3 always reads live
    intake under data/input/ (no separate fixture pack).
    """
    del use_fixture  # V3: live intake only — no parallel fixture path
    try:
        return _run(_local_pipeline(patient_id))
    except Exception as exc:
        return {
            # No trace id: the run died before LangFuse ingested anything, and a
            # made-up id would render a trace link that never resolves.
            "trace_id": None,
            "patient_id": patient_id,
            "case": None,
            "validation": None,
            "summary": None,
            "stages_run": [],
            "indexed": False,
            "needs_hitl": True,
            "discharge_blocked": True,
            "gate": {"allow_summary": False, "reason": str(exc)},
            "error": str(exc),
            "status": "error",
        }


def revalidate_case(
    case: dict[str, Any],
    *,
    elicit_answers: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Re-run Validator on the edited working case (optional elicit answers).

    ``trace_id`` continues the case's existing LangFuse trace (HITL re-run —
    SSoT §9); without one a fresh case trace is opened so the spans still land
    somewhere reachable instead of scattering into per-span orphan traces.
    """
    from agents.validator.graph import run_validation

    pid = str(case.get("patient_id") or "")
    if elicit_answers:
        for key, val in elicit_answers.items():
            if val is not None:
                case[key] = val

    norm = case_to_normalization(case)

    async def _go():
        from shared.tracing.langfuse import case_trace

        # Install staged elicitation handler when answers provided
        token = None
        try:
            if elicit_answers is not None:
                from agents.validator.elicitation_handler import (
                    reset_elicitation_handler,
                    set_elicitation_handler,
                )
                from dashboard.elicitation_callback import (
                    stage_elicitation_response,
                    streamlit_elicitation_handler,
                )
                
                stage_elicitation_response("accept", elicit_answers)

                async def _handler(message, response_type, params, context):
                    return await streamlit_elicitation_handler(
                        message, response_type, params, context
                    )

                token = set_elicitation_handler(_handler)
            with case_trace(pid, existing=trace_id, host_name="HITL Revalidate") as tid:
                report = await run_validation(pid, norm)
            return tid, report
        finally:
            if token is not None:
                from agents.validator.elicitation_handler import reset_elicitation_handler

                reset_elicitation_handler(token)

    try:
        tid, report = _run(_go())
        validation = normalize_validation(report)
        updated = case_after_validation(norm, report if isinstance(report, dict) else None)
        # Preserve bill/med edits from the working case
        updated["medications"] = case.get("medications") or updated.get("medications")
        updated["allergies"] = case.get("allergies") or updated.get("allergies")
        updated["bill"] = case.get("bill") or updated.get("bill")
        updated["follow_up_appointment"] = case.get("follow_up_appointment")
        updated["discharge_ok"] = case.get("discharge_ok")
        if elicit_answers:
            for key, val in elicit_answers.items():
                if val not in ("", None):
                    updated[key] = val
        updated["_normalization"] = updated.get("_normalization") or norm
        # Keep post-elicitation extraction on the case (do not wipe with pre-validate norm)
        if isinstance(report, dict) and isinstance(report.get("extraction_after_elicitation"), dict):
            updated["_normalized_extraction"] = report["extraction_after_elicitation"]
        # Hand the trace id back so the UI can link this re-run's LangFuse trace.
        return {"case": updated, "result": validation, "trace_id": tid}
    except Exception as exc:
        return {"case": case, "result": None, "error": str(exc)}


def ensure_indexed(case: dict[str, Any], validation: dict[str, Any] | None) -> dict[str, Any]:
    del validation  # indexing is by patient_id in V3 FAISS path
    from rag.indexing_agent import load_hitl_corrected_case, run_indexing

    pid = str(case.get("patient_id") or "")
    try:
        hitl = load_hitl_corrected_case(pid)
        if hitl is not None:
            # Refresh FAISS from the latest session case after Corrections
            corrected = case if isinstance(case, dict) else hitl
            msg = _run(run_indexing(pid, force=True, corrected_case=corrected))
        else:
            msg = _run(run_indexing(pid))
        return {"indexed_chunks": msg, "indexed": True}
    except Exception as exc:
        return {"indexed_chunks": 0, "indexed": False, "error": str(exc)}


def reindex_after_hitl(case: dict[str, Any]) -> dict[str, Any]:
    """Save HITL-corrected case and rebuild FAISS so RAG matches Corrections."""
    from rag.indexing_agent import run_indexing

    pid = str(case.get("patient_id") or "")
    if not pid:
        return {"indexed": False, "error": "missing patient_id"}
    try:
        msg = _run(run_indexing(pid, force=True, corrected_case=case))
        return {"indexed_chunks": msg, "indexed": True}
    except Exception as exc:
        return {"indexed_chunks": 0, "indexed": False, "error": str(exc)}


def clear_hitl_rag_snapshot(patient_id: str) -> None:
    """After fresh Process, drop prior HITL snapshot so RAG uses new extract."""
    from rag.indexing_agent import clear_hitl_corrected_case

    clear_hitl_corrected_case(patient_id)


def ask_rag(
    patient_id: str,
    question: str,
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    from rag.pipeline import ask

    try:
        out = _run(ask(patient_id, question, session_id=session_id))
        return out
    except Exception as exc:
        return {"error": {"code": "RAG_ERROR", "message": str(exc)}}


def maybe_summarize(case: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    from agents.summary.agent import run_summary

    blocked = bool(validation.get("discharge_blocked"))
    needs = bool(validation.get("needs_hitl"))
    if blocked or needs:
        return {
            "error": {
                "code": "SUMMARY_REFUSED_BLOCKED",
                "message": "Release gate closed — clear HITL blocks before summarizing.",
            }
        }
    pid = str(case.get("patient_id") or "")
    risk = str((validation.get("risk") or {}).get("level") or validation.get("risk_level") or "low")
    norm = case_to_normalization(case)
    extraction = norm.get("normalized_extraction") or {}
    try:
        summ = _run(
            run_summary(
                patient_id=pid,
                risk_level=risk,
                discharge_blocked=False,
                extraction=extraction,
                audience="patient",
            )
        )
        data = _normalize_summary(summ)
        if data is None:
            return {
                "error": {
                    "code": "SUMMARY_REFUSED_BLOCKED",
                    "message": getattr(summ, "refuse_reason", None) or "Summary refused",
                }
            }
        return {"summary": data}
    except Exception as exc:
        return {"error": {"code": "SUMMARY_ERROR", "message": str(exc)}}
