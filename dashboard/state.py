"""Session state + HITL feedback persistence (spec §E / §P)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.settings import REPO_ROOT


def _discover_patients() -> list[str]:
    """Live intake/report IDs only — never hard-code a sample corpus."""
    try:
        from dashboard.components.common import discover_patient_ids

        return discover_patient_ids()
    except Exception:
        return []


PATIENTS = _discover_patients()

# Clinical workflow first; upload is an admin action (rendered last in the sidebar).
CLINICAL_PAGES = (
    "Document Viewer",
    "Validation Report",
    "Corrections",
    "RAG Q&A",
    "Discharge Summary",
)
ADMIN_PAGES = ("Upload new patients",)
PAGES = CLINICAL_PAGES + ADMIN_PAGES


def ensure_session_defaults() -> None:
    import streamlit as st

    live = _discover_patients()
    defaults: dict[str, Any] = {
        "patient_id": live[0] if live else "",
        "page": CLINICAL_PAGES[0],
        "last_clinical_page": CLINICAL_PAGES[0],
        "pipeline_result": None,
        "case": None,
        "validation": None,
        "summary": None,
        "trace_id": None,
        "rag_session_id": None,
        "rag_history": [],
        "langfuse_trace_url": "",
        "last_error": None,
        "doc_count": None,
        "approval_note": "",
        "risk_override": "Keep model",
        "upload_results": None,
        "upload_pipeline": None,
        "patient_query": "",
        "edited_meds": None,
        "edited_meds_pid": None,
        "edited_meds_epoch": None,
        "meds_editor_epoch": 0,
        "elicitation_values": {},
        "elicitation_values_pid": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.patient_id and live:
        st.session_state.patient_id = live[0]
    if st.session_state.page not in PAGES:
        st.session_state.page = CLINICAL_PAGES[0]
    if st.session_state.get("last_clinical_page") not in CLINICAL_PAGES:
        st.session_state.last_clinical_page = CLINICAL_PAGES[0]


def feedback_path() -> Path:
    root = REPO_ROOT / "data" / "hitl"
    root.mkdir(parents=True, exist_ok=True)
    return root / "feedback.jsonl"


def append_feedback(payload: dict[str, Any]) -> Path:
    path = feedback_path()
    row = {
        **payload,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return path


def risk_badge_class(level: str | None) -> str:
    lv = (level or "").lower()
    if lv == "high":
        return "badge-bad"
    if lv == "medium":
        return "badge-warn"
    if lv == "low":
        return "badge-ok"
    return "badge-mute"
