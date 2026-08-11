"""HITL-corrected case must feed RAG index (not only raw intake)."""

from __future__ import annotations

import json

from rag.indexing_agent import case_to_index_text, save_hitl_corrected_case


def test_case_to_index_text_lists_reviewed_meds_only():
    text = case_to_index_text(
        {
            "patient_id": "P1022",
            "patient_name": "Daan Bakker",
            "allergies": ["Penicillin"],
            "medications": [
                {
                    "medicine_name": "Paracetamol",
                    "strength": "500 mg",
                    "frequency": "q6h PRN",
                    "route": "ORAAL",
                    "period": "5 dagen",
                }
            ],
            "discharge_diagnosis": ["Pneumonia (J18.9)"],
        }
    )
    assert "Paracetamol" in text
    assert "Amoxicillin" not in text
    assert "HITL-REVIEWED" in text
    assert "Penicillin" in text


def test_case_to_index_text_includes_elicited_physician():
    text = case_to_index_text(
        {
            "patient_id": "P1021",
            "patient_name": "Rohan Gupta",
            "attending_physician": "shashwat",
            "consulting_doctors": ["Dr. Mehta", "Dr. Kapoor"],
            "medications": [],
        }
    )
    assert "Attending Physician: shashwat" in text
    assert "Consulting Doctors: Dr. Mehta, Dr. Kapoor" in text


def test_save_hitl_corrected_case_embeds_elicited_attending(tmp_path, monkeypatch):
    from rag import indexing_agent as idx

    monkeypatch.setattr(idx, "get_path", lambda key: tmp_path if key == "reports" else tmp_path)
    path = save_hitl_corrected_case(
        "P1021",
        {
            "patient_id": "P1021",
            "attending_physician": "shashwat",
            "medications": [],
        },
    )
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "Attending Physician: shashwat" in payload["index_text"]
    assert "shashwat" in path.read_text(encoding="utf-8")


def test_save_hitl_corrected_case_roundtrip(tmp_path, monkeypatch):
    from rag import indexing_agent as idx

    monkeypatch.setattr(idx, "get_path", lambda key: tmp_path if key == "reports" else tmp_path)
    path = save_hitl_corrected_case(
        "P1022",
        {"patient_id": "P1022", "medications": [{"medicine_name": "Paracetamol", "strength": "500 mg"}]},
    )
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    assert "Paracetamol" in raw
    assert "HITL-REVIEWED" in raw
