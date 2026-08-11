"""Lightweight patient identity model (optional helper).

Clinical extraction already uses DischargeExtraction / ExtractionResult.
This model is a small shared shape for dashboards and logs — not a second
pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PatientIdentity(BaseModel):
    """Minimal patient identity fields used across HITL / reports."""

    patient_id: str
    patient_name: str | None = None
    age: int | None = None
    gender: str | None = None
    service_line: str | None = Field(
        default=None,
        description="From Mock EHR when available (pediatric/obstetric/oncology HITL).",
    )
