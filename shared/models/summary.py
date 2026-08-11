"""Discharge summary model (SSoT §5.7).

One section per streaming artifact. Order is fixed:
patient → meds → labs → bill → instructions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DischargeSummary(BaseModel):
    """Patient-friendly discharge summary for one case."""

    patient_id: str
    risk_level: str = "low"
    audience: str = "patient"
    refused: bool = False
    refuse_reason: str | None = None
    # Keys match configs/agent_config.yaml agents.summary.section_order
    sections: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
