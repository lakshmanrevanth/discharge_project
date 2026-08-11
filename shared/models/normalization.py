"""Normalization result model (SSoT §5.3 — must include translation confidence).

Applies to any patient_id / any source language — not limited to sample cases.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizationResult(BaseModel):
    """Output of the Clinical Normalizer Agent for one patient case."""

    patient_id: str
    source_language: str = Field(
        default="auto",
        description="Detected or declared source language (any code, or auto)",
    )
    translation_confidence: float = Field(
        ...,
        description="0.0–1.0 confidence from Medical Lang Bridge Sampling (SSoT §5.3)",
    )
    model_used: str = ""
    # Extraction-shaped dict after English translation + abbreviation expansion
    normalized_extraction: dict = Field(default_factory=dict)
    prompt_used: str = "abbreviation-normalization-prompt"
    notes: list[str] = Field(default_factory=list)
