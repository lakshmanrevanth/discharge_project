"""A2A AgentCard + executor for Clinical Extractor (non-streaming, :8100).

Pattern mirrors agents/monitor/a2a.py (Documentation/coding_style/MCP_A2A.txt
for a2a-sdk==0.3.22): A2AStarletteApplication + DefaultRequestHandler + AgentExecutor.
"""

from __future__ import annotations

import json
import re

import httpx
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
    TaskUpdater,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_task
from a2a.utils.errors import ServerError
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from agents.extractor.graph import run_extraction
from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("extractor_a2a")

# Any digit length — FA5 examples use P001; sample corpus uses P1019.
# Same idea as Watcher / sanitize_patient_id (not locked to 4 digits).
_PATIENT_ID_RE = re.compile(r"\bP\d+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    """Pull a patient_id like P001 or P1019 out of the free-text A2A request."""
    match = _PATIENT_ID_RE.search(query or "")
    return match.group(0).upper() if match else None


class ExtractorAgentExecutor(AgentExecutor):
    """Runs the Extractor graph for one patient_id and returns one A2A artifact."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("Extractor A2A request: %s", query)

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        patient_id = _extract_patient_id(query)

        if not patient_id:
            message = "Could not find a patient_id (e.g. P001 or P1019) in the request."
            await updater.add_artifact([Part(root=TextPart(text=message))], name="extraction_error")
            await updater.complete()
            return

        try:
            extraction = await run_extraction(patient_id)
            await updater.add_artifact(
                [Part(root=TextPart(text=json.dumps(extraction, indent=2)))],
                name="clinical_extraction",
            )
            await updater.complete()
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", patient_id, exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"Extractor error for {patient_id}: {exc}"))],
                name="extraction_error",
            )
            await updater.complete()
            raise

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())


class AgentAuthMiddleware(BaseHTTPMiddleware):
    """Require X-Agent-Auth-Token on A2A endpoints (SSoT §4).

    AgentCard discovery at /.well-known/agent.json stays public.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith("/.well-known/"):
            return await call_next(request)

        expected = get_a2a_auth_token()
        cfg = load_agent_config()
        header_name = cfg.get("a2a", {}).get("auth_header", "X-Agent-Auth-Token")
        got = request.headers.get(header_name)
        if got != expected:
            return JSONResponse(
                {"error": "unauthorized", "detail": f"Missing or invalid {header_name}"},
                status_code=401,
            )
        return await call_next(request)


def build_agent_card(host: str, port: int) -> AgentCard:
    """AgentCard served at GET /.well-known/agent.json."""
    cfg = load_agent_config()
    push_enabled = bool(cfg.get("a2a", {}).get("push_notifications", True))

    skill = AgentSkill(
        id="extract_clinical_data",
        name="Extract Clinical Data",
        description=(
            "Harvest a patient's discharge report, lab report, and bill, then "
            "extract structured clinical fields via the LLM (any source language)."
        ),
        tags=["extractor", "harvester", "llm", "structured-extraction"],
        examples=[
            "Extract clinical data for P001",
            "Extract clinical data for P1019",
            "Structure the discharge, lab, and bill for patient P1021",
        ],
    )

    return AgentCard(
        name="Clinical Extractor Agent",
        description=(
            "LangGraph agent that extracts structured clinical data from "
            "discharge reports, lab reports, and hospital bills."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    """Build the Starlette A2A app with auth middleware."""
    svc = get_service("extractor")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8100))

    agent_card = build_agent_card(host, port)

    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ExtractorAgentExecutor(),
        task_store=InMemoryTaskStore(),
        push_config_store=push_config_store,
        push_sender=push_sender,
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    app = server.build()
    app.add_middleware(AgentAuthMiddleware)
    return app
