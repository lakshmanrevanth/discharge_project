"""Tool: generate_risk_heatmap (SSoT §3.5 — exact shape NOT SPECIFIED).

Beginner picture: turn one case's Finding list into a small severity ->
rule_id grid the HITL dashboard can render as a heatmap table.
"""

from __future__ import annotations

import json
from collections import defaultdict

from fastmcp import FastMCP


def build_heatmap(findings: list[dict]) -> dict:
    """Group findings by severity for a simple heatmap view."""
    grid: dict[str, list[dict]] = defaultdict(list)
    for finding in findings:
        severity = finding.get("severity", "info")
        grid[severity].append(
            {
                "rule_id": finding.get("rule_id"),
                "weight": finding.get("weight", 0),
                "blocking": finding.get("blocking", False),
            }
        )
    return {
        "cells": dict(grid),
        "totals": {severity: len(items) for severity, items in grid.items()},
    }


def register_risk_heatmap_tools(mcp: FastMCP) -> None:
    """Attach the Risk Heatmap tool to the Secondary MCP server."""

    @mcp.tool(
        name="generate_risk_heatmap",
        title="Risk Heatmap Tool",
        description="Group one case's Finding list by severity for a simple HITL heatmap view.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def generate_risk_heatmap(findings: list[dict]) -> str:
        """Build the heatmap grid; return it as a JSON string."""
        return json.dumps(build_heatmap(findings), ensure_ascii=False, indent=2)
