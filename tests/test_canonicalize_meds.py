"""Medicine canonicalization (§12.3) — Paracetamol/Acetaminophen and corpus aliases."""

from __future__ import annotations

import pytest

from shared.clinical_normalize import (
    MED_NAME_ALIASES,
    canonicalize_med_name,
    canonicalize_meds_in_extraction,
    medication_conflicts_with_allergy,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Paracetamol", "Paracetamol"),
        ("paracetamol", "Paracetamol"),
        ("Acetaminophen", "Paracetamol"),
        ("acetaminophen", "Paracetamol"),
        ("Paracetamol 500 mg", "Paracetamol"),
        ("paracetamol 500mg", "Paracetamol"),
        ("Acetaminophen 500 mg", "Paracetamol"),
        ("Panadol", "Paracetamol"),
        ("Tylenol", "Paracetamol"),
        ("Paracetemol", "Paracetamol"),
        ("acetaminofen", "Paracetamol"),
        ("Amoxicilline", "Amoxicillin"),
        ("Amoxicilline 500 mg", "Amoxicillin"),
        ("Amoxicillin-Clavulanate", "Amoxicillin-Clavulanate"),
        ("amoxicillin clavulanate", "Amoxicillin-Clavulanate"),
        ("Metformina", "Metformin"),
        ("Aspirina", "Aspirin"),
        ("ASA", "Aspirin"),
        ("Amlodpine", "Amlodipine"),
        ("Ampicilline", "Ampicillin"),
        ("Sulfametoxazol", "Sulfamethoxazole"),
    ],
)
def test_canonicalize_med_name_cases(raw: str, expected: str):
    assert canonicalize_med_name(raw) == expected


def test_paracetamol_matches_acetaminophen_for_set_reconcile():
    """Same drug: US EHR Acetaminophen must match NL discharge Paracetamol."""
    ehr = {canonicalize_med_name("Acetaminophen")}
    discharge = {canonicalize_med_name("Paracetamol 500 mg")}
    assert ehr == discharge == {"Paracetamol"}


def test_paracetamol_and_acetaminophen_never_diverge():
    forms = [
        "Paracetamol",
        "Acetaminophen",
        "paracetamol",
        "acetaminophen",
        "Paracetamol 500 mg",
        "Acetaminophen 500 mg",
        "Panadol",
        "Tylenol",
    ]
    canon = {canonicalize_med_name(x) for x in forms}
    assert canon == {"Paracetamol"}


def test_canonicalize_meds_in_extraction_medicine_name_key():
    ext = {
        "discharge": {
            "medications": [
                {"medicine_name": "Acetaminophen 500 mg", "strength": "500 mg"},
                {"medicine_name": "Amoxicilline", "strength": "500 mg"},
            ]
        }
    }
    out = canonicalize_meds_in_extraction(ext)
    names = [m["medicine_name"] for m in out["discharge"]["medications"]]
    assert names == ["Paracetamol", "Amoxicillin"]


def test_allergy_conflicts_use_canonical_names():
    assert medication_conflicts_with_allergy("Amoxicilline", ["Penicillin"])
    assert medication_conflicts_with_allergy("Ampicillin", ["Penicillin"])
    assert medication_conflicts_with_allergy("Sulfamethoxazole", ["Sulfa"])
    assert medication_conflicts_with_allergy("Paracetamol", ["Penicillin"]) is None


def test_alias_table_paracetamol_family_one_target():
    """Paracetamol family must all map to Paracetamol (one identity)."""
    para_keys = [
        k
        for k in MED_NAME_ALIASES
        if k
        in {
            "paracetamol",
            "acetaminophen",
            "acetaminofen",
            "acetaminophene",
            "paracetemol",
            "panadol",
            "tylenol",
        }
    ]
    targets = {MED_NAME_ALIASES[k] for k in para_keys}
    assert targets == {"Paracetamol"}
