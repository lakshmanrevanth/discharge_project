"""GuardrailManager — HITL Escalation (SSoT §8).

Trigger: risk_level=High OR discharge_blocked=True
Action: Mandatory human review; no auto-approve.
"""

from __future__ import annotations


def evaluate_hitl_escalation(
    risk_level: str | None,
    discharge_blocked: bool,
) -> dict:
    """Decide release-gate action for one case (SSoT §8 HITL Escalation).

    Returns a plain dict so Reporter / Validator / Summary can share one path.
    """
    level = (risk_level or "low").strip().lower() or "low"
    blocked = bool(discharge_blocked)
    mandatory = blocked or level == "high"

    if mandatory:
        action = "mandatory_hitl"
    elif level == "medium":
        action = "standard_hitl"
    else:
        action = "auto_approve"

    result = {
        "risk_level": level,
        "discharge_blocked": blocked,
        "mandatory_hitl": mandatory,
        "auto_approve_allowed": action == "auto_approve",
        "action": action,
    }
    try:
        from shared.tracing.langfuse import record_guardrail

        record_guardrail(
            "HITL Escalation",
            result=action,
            blocked=mandatory,
            detail=f"risk={level} blocked={blocked}",
            reason=action,
        )
    except Exception:
        pass
    return result


def is_auto_approve_allowed(risk_level: str | None, discharge_blocked: bool) -> bool:
    """True only for Low risk with no discharge block (SSoT §8 / §15)."""
    return evaluate_hitl_escalation(risk_level, discharge_blocked)["auto_approve_allowed"]
