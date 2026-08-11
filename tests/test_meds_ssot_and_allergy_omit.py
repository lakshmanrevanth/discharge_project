"""HITL meds SSOT + allergy withhold vs EHR med_omission."""

from __future__ import annotations

from shared.clinical_normalize import medication_conflicts_with_allergy


def test_allergy_withhold_skips_omission_for_penicillin_family():
    allergies = ["Penicillin"]
    assert medication_conflicts_with_allergy("Amoxicillin", allergies)
    assert medication_conflicts_with_allergy("Ampicillin", allergies)
    assert medication_conflicts_with_allergy("Amoxicillin-Clavulanate", allergies)
    assert medication_conflicts_with_allergy("Metformin", allergies) is None


def test_allergy_withhold_skips_omission_for_sulfa_family():
    allergies = ["Sulfa"]
    assert medication_conflicts_with_allergy("Sulfamethoxazole", allergies)
    assert medication_conflicts_with_allergy("Paracetamol", allergies) is None


def test_med_omission_loop_skips_allergy_conflicts():
    """Mirror ehr_validation med_omission rule without calling Mock EHR."""
    allergies = ["Penicillin"]
    ehr = {"Amoxicillin", "Paracetamol"}
    discharge = {"Paracetamol"}
    omitted = []
    for med_name in sorted(ehr - discharge):
        if medication_conflicts_with_allergy(med_name, allergies):
            continue
        omitted.append(med_name)
    assert omitted == []  # Amoxicillin withheld intentionally


def test_med_omission_still_warns_non_conflict():
    allergies = ["Penicillin"]
    ehr = {"Amoxicillin", "Metformin"}
    discharge: set[str] = set()
    omitted = []
    for med_name in sorted(ehr - discharge):
        if medication_conflicts_with_allergy(med_name, allergies):
            continue
        omitted.append(med_name)
    assert omitted == ["Metformin"]


def test_meds_for_patient_ignores_feedback_disk(monkeypatch):
    import dashboard.corrections as corr

    class FakeState(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    fake = FakeState(
        edited_meds=None,
        edited_meds_pid=None,
        edited_meds_epoch=None,
        meds_editor_epoch=3,
    )

    class FakeSt:
        session_state = fake

    monkeypatch.setattr(corr, "st", FakeSt)
    monkeypatch.setattr(corr.bridge, "fetch_ehr_medications", lambda pid: [{"medicine_name": "EHROnly"}])

    case = {
        "medications": [
            {"medicine_name": "Amoxicillin", "strength": "500 mg"},
            {"medicine_name": "Paracetamol", "strength": "500 mg"},
        ]
    }
    feedback = {
        "medications": [
            {"medicine_name": "Metformin"},
            {"medicine_name": "Amlodpine"},
        ]
    }
    meds = corr._meds_for_patient("P1022", case, feedback)
    names = [m.get("medicine_name") for m in meds]
    assert names == ["Amoxicillin", "Paracetamol"]


def test_meds_for_patient_uses_session_only_same_epoch(monkeypatch):
    import dashboard.corrections as corr

    class FakeState(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    fake = FakeState(
        edited_meds=[{"medicine_name": "Paracetamol"}],
        edited_meds_pid="P1022",
        edited_meds_epoch=5,
        meds_editor_epoch=5,
    )

    class FakeSt:
        session_state = fake

    monkeypatch.setattr(corr, "st", FakeSt)
    case = {"medications": [{"medicine_name": "Amoxicillin"}]}
    meds = corr._meds_for_patient("P1022", case, {"medications": [{"medicine_name": "Metformin"}]})
    assert [m["medicine_name"] for m in meds] == ["Paracetamol"]

    fake["meds_editor_epoch"] = 6  # Process bumped epoch
    meds2 = corr._meds_for_patient("P1022", case, {})
    assert [m["medicine_name"] for m in meds2] == ["Amoxicillin"]


def test_med_rows_equal_ignores_blank_and_alias():
    from dashboard.corrections import _med_rows_equal

    a = [{"medicine_name": "Amoxicillin", "strength": "500 mg", "frequency": "", "route": "", "period": ""}]
    b = [{"name": "Amoxicillin", "strength": "500 mg"}, {"medicine_name": ""}]
    assert _med_rows_equal(a, b)
