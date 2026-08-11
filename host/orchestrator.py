"""Google ADK Host Orchestrator (SSoT §5.8).

Coordinates Monitor / Extractor / Normalizer / Validator / Summary / RAG over
A2A. Gradio (:8083) is the UI; this module is the ADK agent + pipeline tools.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from host.a2a_client import get_host_client, try_parse_json
from mcp_servers.primary.sampling import load_model_config
from shared.logger import get_logger

logger = get_logger("host_orchestrator")

APP_NAME = "discharge_host"
USER_ID = "host_user"

_session_service = InMemorySessionService()
_runner: Runner | None = None


def _host_model() -> LiteLlm:
    """Bedrock Nova Lite via ADK LiteLlm (same stack as the rest of the project)."""
    cfg = load_model_config().get("llm", {}).get("primary", {})
    model_id = cfg.get("litellm_model") or os.environ.get(
        "HOST_MODEL",
        "bedrock/amazon.nova-lite-v1:0",
    )
    return LiteLlm(model=model_id)


# ---------------------------------------------------------------------------
# Tools exposed to the ADK Host agent
# ---------------------------------------------------------------------------


async def list_remote_agents() -> str:
    """List A2A agents the Host can delegate to (from AgentCards)."""
    client = get_host_client()
    agents = await client.discover()
    info = client.list_info()
    online = sum(1 for a in agents if not a.error)
    return json.dumps(
        {"online": online, "total": len(agents), "agents": info},
        indent=2,
    )


async def send_to_agent(agent_name: str, message: str) -> str:
    """Send a message to one remote A2A agent by name or service key.

    Streaming agents (summary, rag) use send_message_streaming; others use
    send_message. Examples of agent_name: monitor, extractor, validator,
    'Clinical RAG Q&A Agent', 'Discharge Summary Generator'.
    """
    client = get_host_client()
    if not client.agents_by_key:
        await client.discover()
    logger.info("Host → %s: %s", agent_name, (message or "")[:120])
    return await client.send_auto(agent_name, message)


async def run_case_pipeline(patient_id: str) -> str:
    """Run the full discharge case over A2A for ANY patient_id (P + digits).

    Order (architecture §3): Monitor → Extractor → Normalizer → Validator →
    Summary (only when release gate allows). Returns a JSON status log.
    """
    pid = (patient_id or "").strip().upper()
    if not pid.startswith("P") or not pid[1:].isdigit():
        return json.dumps({"error": "patient_id must look like P001 or P1019"})

    from shared.tracing.langfuse import flush, start_case_trace

    tid = start_case_trace(pid)
    client = get_host_client()
    await client.discover()
    log: list[dict[str, Any]] = [{"trace_id": tid}]

    async def _step(key: str, message: str, *, streaming: bool = False) -> str:
        try:
            if streaming:
                parts: list[str] = []
                async for chunk in client.send_message_streaming(key, message):
                    parts.append(chunk)
                text = "\n".join(parts)
            else:
                text = await client.send_message(key, message)
            log.append({"step": key, "ok": True, "chars": len(text)})
            return text
        except Exception as exc:
            log.append({"step": key, "ok": False, "error": str(exc)})
            raise

    try:
        await _step("monitor", f"Scan clinical intake for new files related to {pid}")
        extract_raw = await _step("extractor", f"Extract clinical data for {pid}")
        norm_raw = await _step("normalizer", f"Normalize clinical data for {pid}")
        report_raw = await _step("validator", f"Validate {pid}")
    except Exception:
        return json.dumps({"patient_id": pid, "pipeline": log, "stopped": True}, indent=2)

    from shared.guardrails.guardrail_manager import evaluate_hitl_escalation

    report = try_parse_json(report_raw) or {}
    norm = try_parse_json(norm_raw) or {}
    risk = str(report.get("risk_level") or "low").lower()
    blocked = bool(report.get("discharge_blocked"))
    gate = report.get("release_gate") or evaluate_hitl_escalation(risk, blocked)
    gate_ok = not gate.get("mandatory_hitl", blocked or risk == "high")


    summary_text = None
    if gate_ok:
        extraction = norm.get("normalized_extraction")
        if not isinstance(extraction, dict):
            extraction = try_parse_json(extract_raw) or {}
        payload = {
            "patient_id": pid,
            "risk_level": risk,
            "discharge_blocked": blocked,
            "audience": "patient",
            "normalized_extraction": extraction,
        }
        try:
            summary_text = await _step(
                "summary",
                json.dumps(payload),
                streaming=True,
            )
        except Exception:
            pass
    else:
        log.append(
            {
                "step": "summary",
                "ok": False,
                "skipped": True,
                "reason": f"release gate: risk={risk} blocked={blocked}",
            }
        )

    return json.dumps(
        {
            "patient_id": pid,
            "trace_id": tid,
            "risk_level": risk,
            "discharge_blocked": blocked,
            "recommendation": report.get("recommendation"),
            "pipeline": log,
            "summary_preview": (summary_text or "")[:800] or None,
        },
        indent=2,
        ensure_ascii=False,
    )


list_tool = FunctionTool(list_remote_agents)
send_tool = FunctionTool(send_to_agent)
pipeline_tool = FunctionTool(run_case_pipeline)

host_agent = LlmAgent(
    name="host_orchestrator",
    model=_host_model(),
    description=(
        "Host Orchestrator for the hospital discharge co-pilot. "
        "Discovers remote A2A agents and coordinates Monitor, Extractor, "
        "Normalizer, Validator, Summary Generator, and Clinical RAG."
    ),
    instruction=(
        "You are the Host Orchestrator for automated discharge summaries.\n"
        "Use tools only — never invent clinical facts.\n"
        "- list_remote_agents: discover which A2A agents are online.\n"
        "- run_case_pipeline: preferred path for a full case (needs patient_id like P1019).\n"
        "- send_to_agent: delegate a single task (monitor / extractor / normalizer / "
        "validator / summary / rag) with a clear message that includes the patient_id.\n"
        "For RAG questions, call send_to_agent with agent_name='rag' and a message "
        "that includes the patient_id and the clinical question.\n"
        "For summaries on gated cases, explain that High risk or discharge_blocked "
        "requires HITL on the Streamlit dashboard (:8501).\n"
        "Be concise. Quote tool results to the user."
    ),
    tools=[list_tool, send_tool, pipeline_tool],
)


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=host_agent,
            app_name=APP_NAME,
            session_service=_session_service,
        )
    return _runner


async def ensure_session(session_id: str) -> str:
    """Create an ADK session if missing; return session_id."""
    sid = session_id or uuid.uuid4().hex
    existing = await _session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=sid,
    )
    if existing is None:
        await _session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=sid,
        )
    return sid


async def run_host_query(query: str, session_id: str | None = None) -> str:
    """Run one user turn through the Google ADK Host agent; return final text."""
    sid = await ensure_session(session_id or uuid.uuid4().hex)
    runner = get_runner()
    content = types.Content(role="user", parts=[types.Part(text=query)])
    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=sid,
        new_message=content,
    ):
        if getattr(event, "is_final_response", lambda: False)():
            parts = getattr(getattr(event, "content", None), "parts", None) or []
            bits = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
            if bits:
                final_text = "\n".join(bits)
    return final_text or "(no response from Host agent)"
