"""A2A AgentCard + executor for Discharge Monitor (non-streaming, :8103).

Pattern mirrors Documentation/coding_style/MCP_A2A.txt for a2a-sdk==0.3.22:
A2AStarletteApplication + DefaultRequestHandler + AgentExecutor.
Push notification store is wired (capability required; behavior NOT SPECIFIED).
"""

from __future__ import annotations

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

from agents.monitor.agent import discover_clinical_intake, get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("monitor_a2a")


class MonitorAgentExecutor(AgentExecutor):
    """Runs the Monitor scan and returns one A2A artifact (non-streaming)."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("Monitor A2A request: %s", query)

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            # Deterministic Phase-3 path: call Watcher via Roots (no LLM required)
            result_text = await discover_clinical_intake()
            await updater.add_artifact(
                [Part(root=TextPart(text=result_text))],
                name="clinical_intake_discovery",
            )
            await updater.complete()
        except Exception as exc:
            logger.error("Monitor scan failed: %s", exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"Monitor error: {exc}"))],
                name="clinical_intake_error",
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
        id="discover_clinical_intake",
        name="Discover Clinical Intake",
        description=(
            "Scan the MCP Roots-scoped intake folder for new discharge reports, "
            "lab reports, and hospital bills via the Clinical Watcher tool."
        ),
        tags=["monitor", "intake", "roots", "watcher"],
        examples=[
            "Scan for new discharge cases",
            "List files under the clinical input Root",
        ],
    )

    return AgentCard(
        name="Discharge Monitor Agent",
        description=(
            "Google ADK agent that discovers new clinical intake files "
            "using MCP Roots and the Clinical Watcher tool."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        # Non-streaming (SSoT §4). Push capability present; behavior NOT SPECIFIED.
        capabilities=AgentCapabilities(streaming=False, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    """Build the Starlette A2A app with auth middleware."""
    svc = get_service("monitor")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8103))

    agent_card = build_agent_card(host, port)

    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=MonitorAgentExecutor(),
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
