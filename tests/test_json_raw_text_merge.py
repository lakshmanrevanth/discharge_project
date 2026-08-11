"""JSON intake: narrative raw_text must not hide structured fields (P1021)."""

from __future__ import annotations

import json
from pathlib import Path

from agents.extractor.nodes import (
    _enrich_discharge_from_source,
    _merge_discharge_from_structured,
)
from mcp_servers.primary.tools.clinical_data_harvester import (
    _STRUCTURED_FIELDS_MARKER,
    json_harvest_raw_text,
)
from shared.models.extraction import DischargeExtraction

P1021 = Path("data/input/doctor_reports/P1021_rohan_gupta.json")


def test_json_harvest_appends_structured_when_raw_text_present():
    data = json.loads(P1021.read_text(encoding="utf-8"))
    text = json_harvest_raw_text(data)
    assert "--- structured fields ---" in text or _STRUCTURED_FIELDS_MARKER in text
    assert '"age": 58' in text or '"age":58' in text.replace(" ", "")
    assert '"ward"' in text
    assert data["raw_text"].strip() in text
    # Nested raw_text must not be duplicated inside the dump
    fields_part = text.split(_STRUCTURED_FIELDS_MARKER, 1)[1]
    assert '"raw_text"' not in fields_part


def test_json_harvest_dumps_whole_object_without_narrative():
    data = {"patient_id": "Px", "age": 30, "address": None}
    text = json_harvest_raw_text(data)
    assert _STRUCTURED_FIELDS_MARKER not in text
    assert '"age": 30' in text
    assert "null" in text


def test_merge_fills_present_json_fields_leaves_planted_nulls():
    data = json.loads(P1021.read_text(encoding="utf-8"))
    empty = DischargeExtraction(patient_id="P1021")
    out = _merge_discharge_from_structured(empty, data)

    assert out.age == 58
    assert out.ward == "4A"
    assert out.bed_no == "12"
    assert out.admission_date == "2026-05-29"
    assert out.discharge_date == "2026-06-02"
    assert out.gender  # gender or sex from JSON
    assert out.discharge_approved is True  # discharge_ok
    assert out.patient_name == "Rohan Gupta"
    assert out.attending_physician
    assert len(out.medications) >= 3

    # Planted traps — must stay blank so validation still HITLs them
    assert out.address is None
    assert out.follow_up_appointment is None
    assert data.get("address") is None
    assert data.get("follow_up_appointment") is None


def test_enrich_merge_does_not_invent_null_fields():
    data = json.loads(P1021.read_text(encoding="utf-8"))
    narrative = data.get("raw_text") or ""
    llm = DischargeExtraction(patient_id="P1021", language="hi")
    out = _enrich_discharge_from_source(llm, raw_text=narrative, structured=data)
    assert out.age == 58
    assert out.address is None
    assert out.follow_up_appointment is None
