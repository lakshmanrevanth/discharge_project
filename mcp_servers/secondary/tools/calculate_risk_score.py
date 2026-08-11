"""Tool: calculate_risk_score (SSoT §3.5, §6.3).

Beginner picture: sum each Finding's weight, then map the total to a tier
using rules.yaml risk_scoring_matrix.thresholds. Any hard HITL guardrail
rule_id present forces tier="high" regardless of the numeric score.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from shared.rules_config import load_rules


def _matches_guardrail(rule_id: str, guardrails: set[str]) -> bool:
    """True if this finding's rule_id hits a hard HITL guardrail.

    FA5 Table 4 findings use names like `allergy_contradiction_check`.
    rules.yaml guardrails use the short weight key `allergy_contradiction`.
    Accept either form so scoring stays correct for any patient.
    """
    if not rule_id:
        return False
    if rule_id in guardrails:
        return True
    # Strip the FA5 `_check` suffix: allergy_contradiction_check → allergy_contradiction
    if rule_id.endswith("_check") and rule_id[: -len("_check")] in guardrails:
        return True
    return False


def score_findings(findings: list[dict]) -> dict:
    """Aggregate one case's Finding list into a score + tier (SSoT §6.3)."""
    rules = load_rules()
    matrix = rules.get("risk_scoring_matrix", {})
    thresholds = matrix.get("thresholds", {})
    guardrails = set(matrix.get("hitl_hard_guardrails", []))

    total = sum(int(f.get("weight", 0)) for f in findings)
    triggered_guardrails = sorted(
        {f["rule_id"] for f in findings if _matches_guardrail(f.get("rule_id", ""), guardrails)}
    )

    low_max = thresholds.get("low_max", 2)
    medium_max = thresholds.get("medium_max", 8)
    if triggered_guardrails or total > medium_max:
        tier = "high"
    elif total > low_max:
        tier = "medium"
    else:
        tier = "low"

    return {
        "risk_score": total,
        "risk_tier": tier,
        "triggered_hard_guardrails": triggered_guardrails,
    }


def register_risk_score_tools(mcp: FastMCP) -> None:
    """Attach the Risk Score tool to the Secondary MCP server."""

    @mcp.tool(
        name="calculate_risk_score",
        title="Risk Score Tool",
        description=(
            "Sum a case's Finding weights using rules.yaml risk_scoring_matrix "
            "and map the total to Low/Medium/High (hard guardrails force High)."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def calculate_risk_score(findings: list[dict]) -> str:
        """Score one case's findings; return JSON risk_score/risk_tier."""
        result = score_findings(findings)
        return json.dumps(result, ensure_ascii=False, indent=2)
