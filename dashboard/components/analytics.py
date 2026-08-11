"""Secondary analytics helpers for HITL Page 2 (SSoT §3.5).

Prefer calling Secondary MCP when it is up; fall back to local pure-Python
builders so the dashboard never crashes if :8201 is offline.
"""

from __future__ import annotations

import json

from mcp_servers.secondary.tools.generate_risk_heatmap import build_heatmap
from mcp_servers.secondary.tools.get_population_benchmarks import get_benchmark
from shared.logger import get_logger
from shared.settings import get_service

logger = get_logger("hitl_analytics")


def heatmap_from_findings(findings: list[dict]) -> dict:
    """Always-available local heatmap (same logic as Secondary tool)."""
    return build_heatmap(findings or [])


def benchmarks_for(service_line: str) -> dict:
    """Always-available local population benchmarks."""
    line = (service_line or "General Medicine").strip() or "General Medicine"
    row = get_benchmark(line)
    return {"service_line": line, **row}


async def try_secondary_heatmap(findings: list[dict]) -> tuple[dict, str]:
    """Call Secondary MCP generate_risk_heatmap; fall back locally on error."""
    try:
        from fastmcp import Client

        svc = get_service("secondary_mcp")
        url = (
            f"http://{svc.get('host', '127.0.0.1')}:"
            f"{int(svc.get('port', 8201))}"
            f"{svc.get('transport_path', '/analyticstools')}"
        )
        async with Client(url) as client:
            result = await client.call_tool(
                "generate_risk_heatmap",
                {"findings": findings},
                raise_on_error=False,
            )
        text = ""
        for block in getattr(result, "content", []) or []:
            if getattr(block, "text", None):
                text = block.text
                break
        if text:
            return json.loads(text), "secondary_mcp"
    except Exception as exc:
        logger.info("Secondary heatmap unavailable (%s) — using local builder", exc)
    return heatmap_from_findings(findings), "local"


async def try_secondary_benchmarks(service_line: str) -> tuple[dict, str]:
    """Call Secondary MCP get_population_benchmarks; fall back locally."""
    try:
        from fastmcp import Client

        svc = get_service("secondary_mcp")
        url = (
            f"http://{svc.get('host', '127.0.0.1')}:"
            f"{int(svc.get('port', 8201))}"
            f"{svc.get('transport_path', '/analyticstools')}"
        )
        async with Client(url) as client:
            result = await client.call_tool(
                "get_population_benchmarks",
                {"service_line": service_line or "General Medicine"},
                raise_on_error=False,
            )
        text = ""
        for block in getattr(result, "content", []) or []:
            if getattr(block, "text", None):
                text = block.text
                break
        if text:
            return json.loads(text), "secondary_mcp"
    except Exception as exc:
        logger.info("Secondary benchmarks unavailable (%s) — using local", exc)
    return benchmarks_for(service_line), "local"
