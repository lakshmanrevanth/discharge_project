"""Elicitation callback fills must reach the HITL/RAG case (not only the gate)."""

from __future__ import annotations

from dashboard.bridge import case_after_validation, case_from_normalization
from rag.indexing_agent import case_to_index_text


def test_case_after_validation_uses_post_elicitation_extraction():
    norm = {
        "patient_id": "P1024",
        "normalized_extraction": {
            "discharge": {
                "patient_id": "P1024",
                "patient_name": "Bram de Vries",
                "attending_physician": None,
                "age": None,
            },
            "bill": {},
        },
    }
    report = {
        "patient_id": "P1024",
        "extraction_after_elicitation": {
            "discharge": {
                "patient_id": "P1024",
                "patient_name": "Bram de Vries",
                "attending_physician": "shashwat",
                "age": 42,
            },
            "bill": {},
        },
    }
    pre = case_from_normalization(norm)
    assert pre.get("attending_physician") in (None, "")

    case = case_after_validation(norm, report)
    assert case.get("attending_physician") == "shashwat"
    assert case.get("age") == 42
    text = case_to_index_text(case)
    assert "Attending Physician: shashwat" in text
    assert "Age: 42" in text


def test_case_after_validation_falls_back_without_post_extract():
    norm = {
        "patient_id": "P1024",
        "normalized_extraction": {
            "discharge": {"patient_id": "P1024", "age": 30},
            "bill": {},
        },
    }
    case = case_after_validation(norm, {"patient_id": "P1024"})
    assert case.get("age") == 30
