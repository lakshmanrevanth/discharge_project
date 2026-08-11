"""Normalizer graph state (TypedDict) — SSoT §5.3."""

from __future__ import annotations

from typing import TypedDict


class NormalizerState(TypedDict):
    patient_id: str
    # ExtractionResult as a plain dict (from Extractor or A2A caller)
    extraction: dict
    source_language: str
    prompt_text: str
    abbreviations_yaml: str
    bridge_raw: str  # JSON string from medical_lang_bridge
    result: dict | None  # NormalizationResult as dict
    errors: list[str]
