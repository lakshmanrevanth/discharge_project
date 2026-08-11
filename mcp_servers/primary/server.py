"""Primary Clinical Tools MCP Server — port 8200, path /clinicaltools.

Phase 2: Resources + Prompts.
Phase 3: Clinical Watcher (Tools + Roots).
Phase 4: Clinical Data Harvester (Tools).
Phase 5: Medical Lang Bridge (Tools + Sampling).
Phase 6: Clinical Rules Engine (Tools + Elicitation), EHR Validation,
         Clinical Insight Reporter.

Run from repo root:
    uv run python -m mcp_servers.primary
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_servers.primary.prompts import register_prompts
from mcp_servers.primary.resources import register_resources
from mcp_servers.primary.tools.clinical_data_harvester import register_harvester_tools
from mcp_servers.primary.tools.clinical_insight_reporter import register_reporter_tools
from mcp_servers.primary.tools.clinical_rules_engine import register_rules_engine_tools
from mcp_servers.primary.tools.clinical_watcher import register_watcher_tools
from mcp_servers.primary.tools.ehr_validation import register_ehr_validation_tools
from mcp_servers.primary.tools.medical_lang_bridge import register_lang_bridge_tools
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("primary_mcp")

mcp = FastMCP(name="Primary Clinical Tools Server")

register_resources(mcp)
register_prompts(mcp)
register_watcher_tools(mcp)
register_harvester_tools(mcp)
register_lang_bridge_tools(mcp)
register_rules_engine_tools(mcp)
register_ehr_validation_tools(mcp)
register_reporter_tools(mcp)


def main() -> None:
    # Host/port/path from configs/agent_config.yaml (SSoT §2)
    svc = get_service("primary_mcp")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8200))
    path = svc.get("transport_path", "/clinicaltools")

    logger.info("Primary MCP starting on http://%s:%s%s", host, port, path)
    # Company coding style: streamable-http.
    # FastMCP 2.12: pass host/port/path to run() (path == streamable_http_path).
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        path=path,
    )


if __name__ == "__main__":
    main()
