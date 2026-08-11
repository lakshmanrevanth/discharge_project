"""A2A AgentCard + streaming executor for Discharge Summary Generator (:8104).

SSoT §4: streaming=True — section-by-section artifacts:
patient → meds → labs → bill → instructions.

Pattern mirrors agents/monitor/a2a.py (a2a-sdk==0.3.22) with streaming on.
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

from agents.summary.agent import iter_summary_sections
from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("summary_a2a")

# Any digit length — works for P001, P1019, P2001, etc.
_PATIENT_ID_RE = re.compile(r"\bP\d+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    match = _PATIENT_ID_RE.search(query or "")
    return match.group(0).upper() if match else None


def _try_parse_payload(query: str) -> dict | None:
    """Parse an embedded JSON payload from the A2A message (beginner-simple).

    Expected keys (Host / Validator / test harness can embed these):
      patient_id, risk_level (or risk_tier), discharge_blocked,
      audience (optional), normalized_extraction (or discharge/lab/bill).
    """
    text = (query or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_request(query: str) -> tuple[str | None, dict]:
    """Return (patient_id, fields) from free text and/or embedded JSON."""
    payload = _try_parse_payload(query) or {}
    patient_id = payload.get("patient_id") or _extract_patient_id(query)
    if patient_id:
        patient_id = str(patient_id).upper()

    risk_level = (
        payload.get("risk_level")
        or payload.get("risk_tier")
        or "low"
    )
    discharge_blocked = bool(payload.get("discharge_blocked", False))
    audience = str(payload.get("audience") or "patient")

    extraction = payload.get("normalized_extraction")
    if not isinstance(extraction, dict):
        # Allow a flat {discharge, lab, bill} shape too.
        if any(k in payload for k in ("discharge", "lab", "bill")):
            extraction = {
                "patient_id": patient_id,
                "discharge": payload.get("discharge") or {},
                "lab": payload.get("lab") or {},
                "bill": payload.get("bill"),
            }
        else:
            extraction = {}

    return patient_id, {
        "risk_level": str(risk_level).lower(),
        "discharge_blocked": discharge_blocked,
        "audience": audience,
        "extraction": extraction,
    }


class SummaryAgentExecutor(AgentExecutor):
    """Stream one A2A artifact per summary section (or a single refuse artifact)."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("Summary A2A request: %s", (query or "")[:200])

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        patient_id, fields = _normalize_request(query or "")

        if not patient_id:
            await updater.add_artifact(
                [
                    Part(
                        root=TextPart(
                            text=(
                                "Could not find a patient_id. Send text like "
                                "'Summarize P1019' plus a JSON payload with "
                                "risk_level, discharge_blocked, and normalized_extraction."
                            )
                        )
                    )
                ],
                name="summary_error",
            )
            await updater.complete()
            return

        if not fields["extraction"]:
            await updater.add_artifact(
                [
                    Part(
                        root=TextPart(
                            text=(
                                f"No clinical extraction embedded for {patient_id}. "
                                "Include normalized_extraction (discharge/lab/bill) "
                                "in the A2A JSON payload."
                            )
                        )
                    )
                ],
                name="summary_error",
            )
            await updater.complete()
            return

        await updater.start_work()

        try:
            async for section, text in iter_summary_sections(
                patient_id=patient_id,
                risk_level=fields["risk_level"],
                discharge_blocked=fields["discharge_blocked"],
                extraction=fields["extraction"],
                audience=fields["audience"],
            ):
                artifact_name = (
                    "summary_refused" if section == "refused" else f"summary_{section}"
                )
                await updater.add_artifact(
                    [Part(root=TextPart(text=text))],
                    name=artifact_name,
                )
                if section == "refused":
                    break
            await updater.complete()
        except Exception as exc:
            logger.error("Summary generation failed for %s: %s", patient_id, exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"Summary error for {patient_id}: {exc}"))],
                name="summary_error",
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
        id="generate_discharge_summary",
        name="Generate Discharge Summary",
        description=(
            "Stream a patient-friendly discharge summary section-by-section "
            "(patient → meds → labs → bill → instructions) after the release "
            "gate allows the case."
        ),
        tags=["summary", "streaming", "discharge"],
        examples=[
            "Summarize P1019",
            "Generate patient-friendly summary for an auto-approved case",
        ],
    )

    return AgentCard(
        name="Discharge Summary Generator",
        description=(
            "Google ADK agent that streams a patient-friendly discharge summary "
            "when the Validator release gate allows (not High, not blocked)."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        # Streaming REQUIRED (SSoT §4). Push capability present; behavior NOT SPECIFIED.
        capabilities=AgentCapabilities(streaming=True, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    """Build the Starlette A2A app with auth middleware."""
    svc = get_service("summary")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8104))

    agent_card = build_agent_card(host, port)

    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(180.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=SummaryAgentExecutor(),
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
