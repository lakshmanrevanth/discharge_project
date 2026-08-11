"""Intake coverage: all three of discharge / lab / bill required to Process."""

from __future__ import annotations

from dashboard.components.ingest import (
    all_intake_present,
    intake_doc_coverage,
    missing_intake_labels,
)


def test_missing_intake_labels_lists_absent_kinds():
    assert missing_intake_labels(
        {"discharge": True, "lab": False, "bill": False}
    ) == ["lab report", "hospital bill"]
    assert missing_intake_labels({"discharge": True, "lab": True, "bill": True}) == []
    assert all_intake_present({"discharge": True, "lab": True, "bill": True})
    assert not all_intake_present({"discharge": True, "lab": True, "bill": False})


def test_intake_doc_coverage_maps_folders(monkeypatch):
    import dashboard.components.common as common

    monkeypatch.setattr(
        common,
        "list_patient_files",
        lambda pid: {
            "doctor_reports": [{"name": f"{pid}_note.txt"}],
            "lab_reports": [{"name": f"{pid}_labs.txt"}],
            "bills": [{"name": f"{pid}_bill.json"}],
        },
    )
    cov = intake_doc_coverage("P2001")
    assert cov == {"discharge": True, "lab": True, "bill": True}
    assert missing_intake_labels(cov) == []
    assert all_intake_present(cov)


def test_intake_doc_coverage_partial(monkeypatch):
    import dashboard.components.common as common

    monkeypatch.setattr(
        common,
        "list_patient_files",
        lambda pid: {
            "doctor_reports": [{"name": f"{pid}_note.txt"}],
            "lab_reports": [],
            "bills": [],
        },
    )
    cov = intake_doc_coverage("P2001")
    assert cov == {"discharge": True, "lab": False, "bill": False}
    assert missing_intake_labels(cov) == ["lab report", "hospital bill"]
    assert not all_intake_present(cov)


def test_intake_doc_coverage_invalid_id():
    cov = intake_doc_coverage("not-a-pid")
    assert cov == {"discharge": False, "lab": False, "bill": False}
