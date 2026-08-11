"""Smoke tests for rebuilt HITL Streamlit (spec §N)."""

from __future__ import annotations

from dashboard.state import PAGES, ensure_session_defaults
from dashboard.styles import PIPELINE_STEPS, nav_label, pipeline_step_states


def test_pages_and_rag_nav_label():
    assert len(PAGES) == 6
    assert PAGES[0] == "Document Viewer"
    assert PAGES[-1] == "Upload new patients"
    assert "Document Viewer" in PAGES
    assert "RAG Q&A" in PAGES
    assert "Corrections" in PAGES
    assert "HITL Corrections" not in PAGES
    assert nav_label("RAG Q&A") == "RAG Assistant"
    assert nav_label("Document Viewer") == "Document Viewer"
    assert nav_label("Corrections") == "Corrections"
    assert nav_label("Upload new patients") == "Upload New Patients"


def test_pipeline_steps_order():
    keys = [k for k, _ in PIPELINE_STEPS]
    assert keys == [
        "monitor",
        "extract",
        "normalize",
        "validate",
        "index",
        "gate",
        "summary_or_hitl",
    ]


def test_idle_pipeline_all_pending():
    steps = pipeline_step_states(None, validation=None, summary=None)
    assert all(state == "pending" for _, _, state, _ in steps)


def test_blocked_gate_skips_summary():
    pr = {
        "stages_run": [
            "monitor",
            "extract",
            "normalize",
            "validate",
            "index",
            "gate",
            "summary_or_hitl",
        ],
        "discharge_blocked": True,
        "needs_hitl": True,
    }
    val = {"discharge_blocked": True, "needs_hitl": True}
    steps = pipeline_step_states(pr, validation=val, summary=None)
    by_key = {k: s for k, _, s, _ in steps}
    assert by_key["gate"] == "blocked"
    assert by_key["summary_or_hitl"] == "skipped"
    assert by_key["validate"] == "done"


def test_clear_case_with_summary_done():
    pr = {
        "stages_run": [
            "monitor",
            "extract",
            "normalize",
            "validate",
            "index",
            "gate",
            "summary_or_hitl",
        ],
    }
    val = {"discharge_blocked": False, "needs_hitl": False}
    summary = {"sections": [{"name": "patient", "markdown": "Hello"}]}
    steps = pipeline_step_states(pr, validation=val, summary=summary)
    by_key = {k: s for k, _, s, _ in steps}
    assert by_key["gate"] == "done"
    assert by_key["summary_or_hitl"] == "done"


def test_live_validation_overrides_stale_host_snapshot():
    """After HITL re-validate, live validation wins over blocked Host snapshot."""
    pr = {
        "stages_run": ["validate", "gate", "summary_or_hitl"],
        "discharge_blocked": True,
        "needs_hitl": True,
        "validation": {"discharge_blocked": True, "needs_hitl": True},
    }
    live = {"discharge_blocked": False, "needs_hitl": False}
    steps = pipeline_step_states(pr, validation=live, summary=None)
    by_key = {k: s for k, _, s, _ in steps}
    assert by_key["gate"] == "done"
    assert by_key["summary_or_hitl"] == "active"


def test_ensure_session_defaults_idle_first(monkeypatch):
    class FakeState(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError as exc:
                raise AttributeError(item) from exc

        def __setattr__(self, key, value):
            self[key] = value

    fake = FakeState()

    class FakeSt:
        session_state = fake

    import dashboard.state as state_mod

    monkeypatch.setattr(state_mod, "st", FakeSt, raising=False)
    # ensure_session_defaults imports streamlit internally
    import streamlit as st_mod

    monkeypatch.setattr(st_mod, "session_state", fake)
    ensure_session_defaults()
    assert fake["pipeline_result"] is None
    assert fake["case"] is None
    assert fake["validation"] is None
    assert fake["summary"] is None
    assert fake["patient_id"]
    assert fake["page"] == PAGES[0]


def test_bridge_normalize_validation_shape():
    from dashboard.bridge import normalize_validation

    report = {
        "patient_id": "P1022",
        "risk_level": "high",
        "risk_score": 12,
        "discharge_blocked": True,
        "all_findings": [
            {
                "rule_id": "allergy_contradiction_check",
                "severity": "critical",
                "message": "Discharge medication 'Amoxicilline' conflicts",
                "blocking": True,
                "field": "medications",
            }
        ],
        "missing_fields": ["age"],
        "rules_version": "abc",
    }
    val = normalize_validation(report)
    assert val["needs_hitl"] is True
    assert val["risk"]["level"] == "high"
    assert val["findings"][0]["severity"] == "Critical"
    assert "age" in val["missing_soft"] or "medications" in val["missing_blocking"]


def test_patient_search_hints_not_hardcoded():
    from dashboard.components.common import filter_patient_hints, patient_display_name

    ids = ["P1003", "P1018", "P1019", "P2001"]
    assert filter_patient_hints("1003", ids) == ["P1003"]
    assert "P1018" in filter_patient_hints("robert", ids) or filter_patient_hints(
        "anderson", ids
    )
    assert filter_patient_hints("", ids) == []
    assert patient_display_name("P1003") == "Sarah Williams"
    assert patient_display_name("P9999") == "Patient"


def test_selected_patient_card_html():
    from dashboard.styles import selected_patient_card_html

    empty = selected_patient_card_html("", "")
    assert "No patient selected" in empty
    filled = selected_patient_card_html("P1020", "Diego Morales")
    assert "P1020" in filled and "Diego Morales" in filled
    assert "Selected Patient" not in filled


def test_ui_chrome_pipeline_html():
    from dashboard.ui_chrome import pipeline_track_html

    html = pipeline_track_html(
        [
            ("monitor", "Monitor", "pending", "○"),
            ("gate", "Gate", "blocked", "✕"),
        ]
    )
    assert "pipeline-track" in html
    assert "blocked" in html


def test_corrections_rerun_is_validate_only():
    """Corrections Re-run must call bridge.revalidate_case — not extract/normalize."""
    from pathlib import Path

    src = Path("dashboard/corrections.py").read_text(encoding="utf-8")
    assert "bridge.revalidate_case" in src
    assert "run_extraction" not in src
    assert "run_normalization" not in src
    assert "no re-extract" in src


def test_case_to_normalization_keeps_hitl_overlays():
    from dashboard.bridge import case_to_normalization

    case = {
        "patient_id": "P1012",
        "age": 55,
        "medications": [{"medicine_name": "Aspirin", "strength": "81mg"}],
        "bill": {"payment_status": "Paid"},
        "follow_up_appointment": "2026-09-01",
        "discharge_ok": True,
        "_normalization": {"patient_id": "P1012", "translation_confidence": 0.9},
        "_normalized_extraction": {
            "discharge": {"patient_id": "P1012", "age": 40},
            "bill": {"payment_status": "Unpaid"},
        },
    }
    norm = case_to_normalization(case)
    discharge = norm["normalized_extraction"]["discharge"]
    assert discharge["age"] == 55
    assert discharge["medications"][0]["medicine_name"] == "Aspirin"
    assert discharge["follow_up_appointment"] == "2026-09-01"
    assert discharge["discharge_approved"] is True
    assert norm["normalized_extraction"]["bill"]["payment_status"] == "Paid"


def test_revalidate_case_langfuse_is_validator_only(monkeypatch, tmp_path):
    """HITL revalidate opens Host → Validator only (no Extractor/Normalizer)."""
    import json

    import dashboard.bridge as bridge
    import shared.tracing.langfuse as lf

    monkeypatch.setattr(lf, "_client", None)
    monkeypatch.setattr(lf, "_client_checked", True)
    monkeypatch.setattr(lf, "get_path", lambda _key: tmp_path)

    async def fake_validation(patient_id, normalization):
        assert lf.get_current_trace_id()
        return {
            "patient_id": patient_id,
            "risk_level": "low",
            "risk_score": 1,
            "discharge_blocked": False,
            "recommendation": "auto",
            "all_findings": [],
            "extraction_after_elicitation": normalization.get("normalized_extraction"),
        }

    monkeypatch.setattr(
        "agents.validator.graph.run_validation", fake_validation
    )

    case = {
        "patient_id": "P1012",
        "age": 55,
        "_normalization": {"patient_id": "P1012", "translation_confidence": 1.0},
        "_normalized_extraction": {"discharge": {"patient_id": "P1012", "age": 55}},
    }
    out = bridge.revalidate_case(case)
    assert out.get("error") is None
    assert out.get("trace_id")
    assert out.get("stages_run") == ["validate"]

    trace_file = tmp_path / "traces" / f"{out['trace_id']}.json"
    assert trace_file.exists()
    events = json.loads(trace_file.read_text(encoding="utf-8")).get("events") or []
    names = [e.get("name") for e in events if isinstance(e, dict)]
    assert "Host Agent" in names
    assert "Validator Agent" in names
    assert "Workflow Output" in names
    assert "Extractor Agent" not in names
    assert "Normalizer Agent" not in names
    val_ev = next(e for e in events if e.get("name") == "Validator Agent")
    assert (val_ev.get("metadata") or {}).get("mode") == "hitl_revalidate"
