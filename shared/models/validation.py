"""Validation / risk result model (SSoT §5.4, §6.3).

Works for any patient_id — completeness gaps, EHR cross-validation issues,
and the aggregated risk score/tier all live on one Finding list.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """One completeness gap or cross-validation issue for a patient case.

    rule_id matches FA5 Table 4 (e.g. allergy_contradiction_check) or a
    completeness rule (missing_mandatory_field, incomplete_prescription_fields).
    blocking=True means an absolute block — ignores the risk score entirely
    (SSoT §5.4 Critical rules + hard guardrails).
    """

    rule_id: str
    severity: str = Field(description="'critical' | 'warning' | 'info'")
    message: str
    field: str | None = None
    weight: int = 0
    blocking: bool = False


class ValidationResult(BaseModel):
    """Output of the Clinical Validation Agent for one patient case (SSoT §5.4)."""

    patient_id: str
    findings: list[Finding] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    elicitation_outcome: str | None = Field(
        default=None,
        description="'accept' | 'decline' | 'cancel' | None (no non-blocking gaps)",
    )
    risk_score: int = 0
    risk_tier: str = Field(default="low", description="'low' | 'medium' | 'high'")
    discharge_blocked: bool = Field(
        default=False,
        description="Any Critical/blocking finding present — never auto-approve (SSoT §15)",
    )
    recommendation: str = ""
    notes: list[str] = Field(default_factory=list)
