"""Tool: get_population_benchmarks (SSoT §3.5 — exact data source NOT SPECIFIED).

FA5 does not provide a real readmission dataset for this tool, so these are
simple, static, illustrative reference numbers by hospital service_line —
an implementer decision, documented here rather than hidden.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

# service_line -> illustrative 30-day readmission rate % + average risk score
_BENCHMARKS: dict[str, dict] = {
    "General Medicine": {"readmission_rate_pct": 12.5, "avg_risk_score": 3.0},
    "Cardiology": {"readmission_rate_pct": 18.2, "avg_risk_score": 4.5},
    "Pulmonology": {"readmission_rate_pct": 16.0, "avg_risk_score": 4.0},
    "Gastroenterology": {"readmission_rate_pct": 10.0, "avg_risk_score": 3.0},
    "General Surgery": {"readmission_rate_pct": 8.0, "avg_risk_score": 2.5},
}
_DEFAULT_BENCHMARK = {"readmission_rate_pct": 12.0, "avg_risk_score": 3.0}


def get_benchmark(service_line: str) -> dict:
    """Return the benchmark row for one service_line (default when unknown)."""
    return _BENCHMARKS.get(service_line, _DEFAULT_BENCHMARK)


def register_population_benchmark_tools(mcp: FastMCP) -> None:
    """Attach the Population Benchmarks tool to the Secondary MCP server."""

    @mcp.tool(
        name="get_population_benchmarks",
        title="Population Benchmarks Tool",
        description=(
            "Illustrative readmission-rate benchmark for a hospital "
            "service_line (e.g. 'Cardiology', 'General Medicine')."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def get_population_benchmarks(service_line: str) -> str:
        """Return JSON benchmark for one service_line."""
        benchmark = get_benchmark(service_line)
        return json.dumps({"service_line": service_line, **benchmark}, ensure_ascii=False, indent=2)
