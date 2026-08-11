"""Deterministic clinical normalization helpers (SSoT §5.3, §6.2, §12.3).

Beginner picture — run these AFTER Sampling (or as a safety net):
  1. Expand abbreviations from rules.yaml (string fields only).
  2. Canonicalize medicine spellings (Metformina → Metformin, …).
  3. Attach ICD-10 codes from rules.yaml when a diagnosis matches.

These do NOT call an LLM. Sampling still does the translation work.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from shared.settings import get_path

# Local / EHR spelling variants → English/generic form used for matching (§12.3).
# Keys are lowercase. Values keep a stable display casing.
# Paracetamol (INN) and Acetaminophen (USAN) are the SAME drug — one shared form.
# Prefer Paracetamol: matches NL/EU discharge notes and Mock EHR seed for P1022/P1024.
MED_NAME_ALIASES: dict[str, str] = {
    "metformina": "Metformin",
    "metformin": "Metformin",
    "atorvastatina": "Atorvastatin",
    "atorvastatin": "Atorvastatin",
    "aspirina": "Aspirin",
    "aspirin": "Aspirin",
    "amoxicilline": "Amoxicillin",
    "amoxicilina": "Amoxicillin",
    "amoxicillin": "Amoxicillin",
    "amoxicillin clavulanate": "Amoxicillin-Clavulanate",
    "amoxicillin-clavulanate": "Amoxicillin-Clavulanate",
    "amoxicilline-clavulanaat": "Amoxicillin-Clavulanate",
    "ampicillin": "Ampicillin",
    "ampicilline": "Ampicillin",
    # Same drug — keep INN "Paracetamol" (not USAN Acetaminophen) as the project form
    "paracetamol": "Paracetamol",
    "acetaminophen": "Paracetamol",
    "acetaminofen": "Paracetamol",
    "acetaminophene": "Paracetamol",
    "paracetemol": "Paracetamol",  # common misspelling
    "panadol": "Paracetamol",
    "tylenol": "Paracetamol",
    "acetylsalicylic acid": "Aspirin",
    "asa": "Aspirin",
    "amlodpine": "Amlodipine",  # OCR / HITL typo seen in corpus
    "amlodipina": "Amlodipine",
    "amlodipine": "Amlodipine",
    "lisinopril": "Lisinopril",
    "loperamida": "Loperamide",
    "loperamide": "Loperamide",
    "warfarina": "Warfarin",
    "warfarin": "Warfarin",
    "sulfamethoxazole": "Sulfamethoxazole",
    "sulfametoxazol": "Sulfamethoxazole",
}

# Strength / quantity glued onto a medicine name (e.g. "Paracetamol 500 mg").
_DOSE_LIKE_REST = re.compile(
    r"^("
    r"[\d.,]+\s*(mg|mcg|µg|ug|g|ml|iu|units?|%|mg/kg)"
    r"|[\d.,]+\s*-\s*[\d.,]+\s*(mg|mcg|µg|ug|g|ml)"
    r")\b",
    re.IGNORECASE,
)

# Field names that usually hold a medicine name
_MED_NAME_KEYS = {
    "name",
    "medication",
    "medication_name",
    "medicine_name",  # FA5 discharge / extractor field
    "drug",
    "drug_name",
    "medicine",
    "med_name",
}

# Field names that usually hold a diagnosis string
_DIAGNOSIS_KEYS = {
    "diagnosis",
    "primary_diagnosis",
    "secondary_diagnosis",
    "diagnoses",
    "discharge_diagnosis",
    "dx",
    "condition",
}

# Allergy (canonical, lowercase) -> medicine names that conflict with it (§12.3
# point 1 — cross-reactivity, not string-equality). Amoxicillin and its
# combinations conflict with a Penicillin allergy (P1004, P1016, P1022, P1024).
ALLERGY_CONFLICT_MAP: dict[str, list[str]] = {
    "penicillin": ["Penicillin", "Amoxicillin", "Amoxicillin-Clavulanate", "Ampicillin"],
    "sulfa": ["Sulfamethoxazole", "Trimethoprim-Sulfamethoxazole", "Sulfasalazine"],
    "latex": [],  # no medicine-name conflict — informational allergy only
}


def load_normalization_standards() -> dict:
    """Read normalization_standards from configs/rules.yaml."""
    path = get_path("rules_yaml")
    with open(path, encoding="utf-8") as f:
        rules = yaml.safe_load(f) or {}
    return rules.get("normalization_standards", {}) or {}


def abbreviation_map_from_yaml_text(abbrev_yaml: str) -> dict[str, str]:
    """Parse the medical-abbreviations resource (YAML) into a dict."""
    if not (abbrev_yaml or "").strip():
        return {}
    try:
        data = yaml.safe_load(abbrev_yaml)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if k and v}
    # Fallback: line "KEY: value" parsing
    mapping: dict[str, str] = {}
    for line in abbrev_yaml.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().strip('"').strip("'")
        val = val.strip().strip('"').strip("'")
        if key and val:
            mapping[key] = val
    return mapping


def expand_abbreviations_in_text(text: str, mapping: dict[str, str]) -> str:
    """Word-boundary expand abbreviations in one string."""
    if not text or not mapping:
        return text
    out = text
    for abbr in sorted(mapping.keys(), key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(abbr)}\b")
        out = pattern.sub(mapping[abbr], out)
    return out


def _walk_strings(value: Any, transform) -> Any:
    """Apply transform(str) to every string in a nested dict/list tree."""
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, list):
        return [_walk_strings(item, transform) for item in value]
    if isinstance(value, dict):
        return {k: _walk_strings(v, transform) for k, v in value.items()}
    return value


def expand_abbreviations_in_extraction(
    extraction: dict,
    mapping: dict[str, str],
) -> dict:
    """Expand abbreviations on string fields only (does not break JSON keys)."""
    if not mapping:
        return extraction
    return _walk_strings(
        extraction,
        lambda s: expand_abbreviations_in_text(s, mapping),
    )


def canonicalize_med_name(name: str) -> str:
    """Map one medicine spelling to the project canonical English/INN form.

    SSoT §12.3: Paracetamol and Acetaminophen must match after normalization
    (same drug). Project form is Paracetamol so NL notes / P1022 EHR stay
    consistent. Dose text stuck on the name ("Acetaminophen 500 mg") is
    stripped so set reconciliation does not break.
    """
    if not name or not str(name).strip():
        return name
    raw = str(name).strip()
    key = re.sub(r"\s+", " ", raw.lower())

    # Longest alias first (handles "amoxicillin clavulanate" before "amoxicillin")
    for alias in sorted(MED_NAME_ALIASES.keys(), key=len, reverse=True):
        if key == alias:
            return MED_NAME_ALIASES[alias]
        if key.startswith(alias + " "):
            rest = key[len(alias) + 1 :].strip()
            canon = MED_NAME_ALIASES[alias]
            # Drop strength/quantity glued onto the name — identity only
            if not rest or _DOSE_LIKE_REST.match(rest):
                return canon
            # Unknown modifier (e.g. "XR") — keep base drug for matching
            if rest.upper() in {"XR", "ER", "SR", "CR", "HCL", "HCL.", "SODIUM"}:
                return canon
            return canon
    return raw


def canonicalize_meds_in_extraction(extraction: dict) -> dict:
    """Walk extraction and canonicalize medicine name fields (§12.3)."""

    def fix_obj(obj: Any) -> Any:
        if isinstance(obj, list):
            return [fix_obj(item) for item in obj]
        if not isinstance(obj, dict):
            return obj
        out: dict[str, Any] = {}
        for key, val in obj.items():
            if key.lower() in _MED_NAME_KEYS and isinstance(val, str):
                out[key] = canonicalize_med_name(val)
            else:
                out[key] = fix_obj(val)
        return out

    return fix_obj(extraction)


def apply_icd10_map(extraction: dict, icd10_map: dict[str, str] | None = None) -> dict:
    """Attach ICD-10 codes when diagnosis text matches rules.yaml map (§6.2)."""
    if icd10_map is None:
        standards = load_normalization_standards()
        icd10_map = standards.get("icd10_map") or {}
    if not icd10_map:
        return extraction

    # Lowercase lookup for soft match
    lookup = {str(k).strip().lower(): str(v) for k, v in icd10_map.items()}

    def code_for(diagnosis: str) -> str | None:
        text = str(diagnosis).strip()
        if not text:
            return None
        direct = lookup.get(text.lower())
        if direct:
            return direct
        for name, code in lookup.items():
            if name in text.lower() or text.lower() in name:
                return code
        return None

    def fix_obj(obj: Any) -> Any:
        if isinstance(obj, list):
            return [fix_obj(item) for item in obj]
        if not isinstance(obj, dict):
            return obj
        out: dict[str, Any] = {}
        for key, val in obj.items():
            out[key] = fix_obj(val)
            if key.lower() in _DIAGNOSIS_KEYS and isinstance(val, str):
                code = code_for(val)
                if code and not out.get("icd10") and not out.get("icd_code"):
                    out["icd10"] = code
            elif key.lower() in _DIAGNOSIS_KEYS and isinstance(val, list):
                # List of diagnosis strings → parallel icd10 list when useful
                codes = []
                for item in val:
                    if isinstance(item, str):
                        codes.append(code_for(item) or "")
                if any(codes) and "icd10_list" not in out:
                    out["icd10_list"] = codes
        return out

    return fix_obj(extraction)


def medication_conflicts_with_allergy(med_name: str, allergies: list[str]) -> str | None:
    """Return the matching allergy (as documented) if med_name conflicts, else None.

    Canonicalizes med_name first, then checks it against each allergy's
    conflict list (ALLERGY_CONFLICT_MAP) plus the allergy name itself —
    catches both "med IS the allergen" and "med is a cross-reactive drug".
    """
    canon = canonicalize_med_name(med_name).strip().lower()
    if not canon:
        return None
    for allergy in allergies or []:
        allergy_key = str(allergy).strip().lower()
        if not allergy_key:
            continue
        conflicts = [allergy_key] + [c.lower() for c in ALLERGY_CONFLICT_MAP.get(allergy_key, [])]
        if any(canon == c or canon.startswith(c) or c in canon for c in conflicts):
            return allergy
    return None


def post_normalize_extraction(
    extraction: dict,
    abbreviations_yaml: str = "",
) -> dict:
    """Full deterministic pass: abbrev → meds → ICD-10 (beginner one-call)."""
    mapping = abbreviation_map_from_yaml_text(abbreviations_yaml)
    if not mapping:
        mapping = load_normalization_standards().get("abbreviation_map") or {}
        mapping = {str(k): str(v) for k, v in mapping.items()}

    result = expand_abbreviations_in_extraction(extraction, mapping)
    result = canonicalize_meds_in_extraction(result)
    result = apply_icd10_map(result)
    return result
