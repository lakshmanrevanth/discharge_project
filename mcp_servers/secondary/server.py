"""Secondary Analytics MCP Server — port 8201, path /analyticstools (SSoT §2 row 10).

Tools only (no Resources/Prompts/Sampling/Elicitation/Roots — those live on
Primary): calculate_risk_score, get_population_benchmarks, generate_risk_heatmap.

Run from repo root:
    uv run python -m mcp_servers.secondary
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_servers.secondary.tools.calculate_risk_score import register_risk_score_tools
from mcp_servers.secondary.tools.generate_risk_heatmap import register_risk_heatmap_tools
from mcp_servers.secondary.tools.get_population_benchmarks import register_population_benchmark_tools
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("secondary_mcp")

mcp = FastMCP(name="Secondary Analytics Server")

register_risk_score_tools(mcp)
register_population_benchmark_tools(mcp)
register_risk_heatmap_tools(mcp)


def main() -> None:
    svc = get_service("secondary_mcp")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8201))
    path = svc.get("transport_path", "/analyticstools")

    logger.info("Secondary MCP starting on http://%s:%s%s", host, port, path)
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        path=path,
    )


if __name__ == "__main__":
    main()
