"""Validator graph state (TypedDict) — SSoT §5.4."""

from __future__ import annotations

from typing import TypedDict


class ValidatorState(TypedDict):
    patient_id: str
    # NormalizationResult as a plain dict (from Normalizer or A2A caller)
    normalization: dict
    # normalized_extraction (discharge/lab/bill) — updated after elicitation
    extraction: dict
    # Hard-blocking + soft score-only findings from clinical_rules_engine.
    completeness_findings: list[dict]
    missing_fields: list[str]
    elicitation_outcome: str | None
    ehr_findings: list[dict]
    all_findings: list[dict]
    risk_score: int
    risk_tier: str
    discharge_blocked: bool
    release_gate: dict
    report: dict | None
    errors: list[str]
