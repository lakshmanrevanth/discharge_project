"""Discharge Monitor Agent — Google ADK (SSoT §5.1, §3.8).

Framework: Google ADK.
Job: register MCP Root for data/input/, call Clinical Watcher tool.
Watcher logic lives on Primary MCP — this agent must NOT scan the filesystem itself.
"""

from __future__ import annotations

import json
import os

from fastmcp import Client
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from mcp.types import Root

from mcp_servers.primary.roots import path_to_file_uri
from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_path, get_service

logger = get_logger("monitor")


def _primary_mcp_url() -> str:
    """Build Primary MCP streamable-HTTP URL from agent_config.yaml."""
    svc = get_service("primary_mcp")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8200))
    path = svc.get("transport_path", "/clinicaltools")
    return f"http://{host}:{port}{path}"


def get_clinical_root() -> Root:
    """Build the MCP Root the Monitor must register (SSoT §3.8).

    FA5 example shape: file:///data/input
    Runtime: absolute file:// URI for configs paths.input_root.
    """
    input_root = get_path("input_root")
    input_root.mkdir(parents=True, exist_ok=True)
    uri = path_to_file_uri(input_root)
    return Root(uri=uri, name="clinical_input")


async def discover_clinical_intake() -> str:
    """Call Clinical Watcher via MCP with Roots registered — no raw paths.

    This is the Monitor's only way to learn about intake files.
    """
    import time

    from shared.tracing.langfuse import record_mcp_tool

    root = get_clinical_root()
    url = _primary_mcp_url()
    logger.info("Monitor opening MCP with Root %s → %s", root.uri, url)

    t0 = time.perf_counter()
    error: str | None = None
    text = ""
    try:
        async with Client(url, roots=[root]) as client:
            # No path arguments — Watcher uses ctx.list_roots() only
            result = await client.call_tool("clinical_watcher", {})
        text = _tool_result_to_text(result)
        logger.info("Watcher returned %s char(s)", len(text))
        return text
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record_mcp_tool(
            "clinical_watcher",
            params={"roots": [str(root.uri)], "note": "no path args — Roots only"},
            result={"chars": len(text or ""), "preview": (text or "")[:400]},
            duration_ms=(time.perf_counter() - t0) * 1000,
            success=error is None,
            error=error,
        )


def _tool_result_to_text(result: object) -> str:
    """Pull readable text out of a FastMCP / MCP tool result."""
    # Newer clients: result.content is a list of blocks
    content = getattr(result, "content", None)
    if content:
        parts = []
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        if parts:
            return "\n".join(parts)

    data = getattr(result, "data", None)
    if data is not None:
        if isinstance(data, str):
            return data
        return json.dumps(data, indent=2)

    # Fallback
    return str(result)


# ---------------------------------------------------------------------------
# Google ADK agent (framework identity — SSoT §2 row 1)
# ---------------------------------------------------------------------------
# Monitor's job (§5.1) is a deterministic scan — no clinical reasoning needed —
# so the Phase-3 A2A executor calls discover_clinical_intake() directly and
# does not run this LlmAgent through an ADK Runner yet. That avoids requiring
# an LLM API key / LiteLLM (arrives in Phase 5, SSoT §3.6) just to list files.
# monitor_agent is kept as the real ADK object (framework identity, §2 row 1)
# and Host (Phase 12) can run it through a Runner once a model is wired.
# model= is a placeholder only — never invoked in Phase 3.

discover_tool = FunctionTool(discover_clinical_intake)

monitor_agent = LlmAgent(
    name="discharge_monitor",
    model=os.environ.get("MONITOR_MODEL", "gemini-2.0-flash"),  # placeholder, unused in Phase 3
    description=(
        "Discharge Monitor Agent. Discovers new hospital discharge documents "
        "via MCP Roots and the Clinical Watcher tool."
    ),
    instruction=(
        "You monitor the clinical intake folder. "
        "When asked to scan, discover, or list new discharge cases, "
        "call discover_clinical_intake. "
        "Never invent file paths. Never ask for raw filesystem paths. "
        "Return the Watcher JSON result to the caller."
    ),
    tools=[discover_tool],
)


def build_monitor_agent() -> LlmAgent:
    """Return the Google ADK Monitor agent instance."""
    return monitor_agent


# Re-exported so agents/monitor/a2a.py can keep importing it from here.
__all__ = ["discover_clinical_intake", "get_clinical_root", "build_monitor_agent", "get_a2a_auth_token"]
