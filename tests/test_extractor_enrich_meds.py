"""Extractor enrich: incomplete LLM meds + empty diagnosis from source text."""

from __future__ import annotations

from pathlib import Path

from agents.extractor.nodes import (
    _enrich_discharge_from_source,
    _ensure_discharge_meds,
    _parse_diagnosis_section,
    _parse_prescription_table,
    _prescription_incomplete,
)
from shared.models.extraction import DischargeExtraction, PrescriptionItem

P1022_OCR = Path("data/input/doctor_reports/P1022_daan_bakker.png.ocr.txt")


def test_p1022_table_parse_has_full_fields():
    text = P1022_OCR.read_text(encoding="utf-8")
    rows = _parse_prescription_table(text)
    assert len(rows) == 2
    assert rows[0].medicine_name == "Amoxicilline"
    assert rows[0].strength == "500 mg"
    assert rows[0].frequency == "TID"
    assert rows[0].route == "ORAAL"
    assert rows[1].medicine_name == "Paracetamol"
    assert not _prescription_incomplete(rows[0])
    assert not _prescription_incomplete(rows[1])


def test_enrich_fills_name_only_llm_meds_from_table():
    """Bug: LLM returned Amoxicillin/Acetaminophen with blank strength/freq/route."""
    text = P1022_OCR.read_text(encoding="utf-8")
    llm = DischargeExtraction(
        patient_id="P1022",
        medications=[
            PrescriptionItem(medicine_name="Amoxicillin"),
            PrescriptionItem(medicine_name="Acetaminophen"),
        ],
    )
    out = _ensure_discharge_meds(llm, raw_text=text, structured=None)
    assert len(out.medications) == 2
    amox = out.medications[0]
    para = out.medications[1]
    assert amox.strength == "500 mg"
    assert amox.frequency == "TID"
    assert amox.route == "ORAAL"
    assert amox.period == "7 dagen"
    assert para.strength == "500 mg"
    assert para.frequency == "q6h PRN"
    assert para.route == "ORAAL"
    assert not _prescription_incomplete(amox)
    assert not _prescription_incomplete(para)


def test_enrich_does_not_wipe_complete_llm_meds():
    text = P1022_OCR.read_text(encoding="utf-8")
    llm = DischargeExtraction(
        medications=[
            PrescriptionItem(
                medicine_name="Amoxicillin",
                strength="250 mg",
                frequency="BID",
                route="ORAL",
                period="10 days",
            )
        ]
    )
    out = _ensure_discharge_meds(llm, raw_text=text, structured=None)
    # Complete LLM fields must win over table (no silent overwrite)
    assert out.medications[0].strength == "250 mg"
    assert out.medications[0].frequency == "BID"


def test_p1022_diagnosis_section_parse():
    text = P1022_OCR.read_text(encoding="utf-8")
    dx = _parse_diagnosis_section(text)
    assert len(dx) == 1
    assert "pneumonie" in dx[0].lower()
    assert "J18.9" in dx[0]


def test_enrich_fills_empty_diagnosis_and_meds():
    text = P1022_OCR.read_text(encoding="utf-8")
    empty = DischargeExtraction(patient_id="P1022")
    out = _enrich_discharge_from_source(empty, raw_text=text, structured=None)
    assert out.discharge_diagnosis
    assert "pneumonie" in out.discharge_diagnosis[0].lower()
    assert len(out.medications) == 2
    assert not any(_prescription_incomplete(m) for m in out.medications)


def test_p1022_demographics_from_labels():
    from agents.extractor.nodes import _parse_labeled_demographics
    from pathlib import Path

    text = Path("data/input/doctor_reports/P1022_daan_bakker.png.ocr.txt").read_text(
        encoding="utf-8"
    )
    found = _parse_labeled_demographics(text)
    assert found.get("ward") == "3B"
    assert found.get("bed_no") == "14"
    assert "age" not in found  # not in the NL note
    assert found.get("address", "").startswith("Kerkstraat")

