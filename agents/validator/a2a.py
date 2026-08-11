"""A2A AgentCard + executor for Clinical Validation Agent (non-streaming, :8101).

Pattern mirrors agents/normalizer/a2a.py (a2a-sdk==0.3.22).
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

from agents.validator.graph import run_validation
from shared.a2a_auth import get_a2a_auth_token
from shared.a2a_call import fetch_normalization_via_a2a
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("validator_a2a")

# Any digit length — FA5 examples use P001; sample corpus uses P1019; new
# patients can be P2001, P99999, etc. Not locked to a fixed sample list.
_PATIENT_ID_RE = re.compile(r"\bP\d+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    match = _PATIENT_ID_RE.search(query or "")
    return match.group(0).upper() if match else None


def _try_parse_normalization_json(query: str) -> dict | None:
    """If the A2A message embeds a NormalizationResult JSON blob, use it."""
    text = (query or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and "normalized_extraction" in data:
        return data
    return None


class ValidatorAgentExecutor(AgentExecutor):
    """Validate one patient's normalized extraction (completeness + EHR + risk + report).

    Not limited to sample patients P1019-P1024 — any patient_id with a
    NormalizationResult (or reachable via Normalizer A2A) works.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("Validator A2A request: %s", (query or "")[:200])

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        patient_id = _extract_patient_id(query)
        normalization = _try_parse_normalization_json(query)

        if not patient_id and normalization:
            raw_id = normalization.get("patient_id")
            if raw_id:
                patient_id = str(raw_id)

        if not patient_id:
            message = (
                "Could not find a patient_id in the request. "
                "Send text like 'Validate P2001' or embed a NormalizationResult JSON "
                "with a patient_id field."
            )
            await updater.add_artifact([Part(root=TextPart(text=message))], name="validation_error")
            await updater.complete()
            return

        try:
            # Prefer embedded NormalizationResult JSON from Host / caller.
            # If missing, ask Normalizer over A2A (:8102) — not a graph import.
            if normalization is None:
                logger.info(
                    "No embedded normalization — A2A call to Normalizer for %s",
                    patient_id,
                )
                normalization = await fetch_normalization_via_a2a(patient_id)

            report = await run_validation(patient_id, normalization)
            await updater.add_artifact(
                [Part(root=TextPart(text=json.dumps(report, indent=2, ensure_ascii=False)))],
                name="clinical_validation_report",
            )
            await updater.complete()
        except Exception as exc:
            logger.error("Validation failed for %s: %s", patient_id, exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"Validator error for {patient_id}: {exc}"))],
                name="validation_error",
            )
            await updater.complete()
            raise

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())


class AgentAuthMiddleware(BaseHTTPMiddleware):
    """Require X-Agent-Auth-Token on A2A endpoints (SSoT §4)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/.well-known/"):
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
    cfg = load_agent_config()
    push_enabled = bool(cfg.get("a2a", {}).get("push_notifications", True))

    skill = AgentSkill(
        id="validate_discharge_case",
        name="Validate Discharge Case",
        description=(
            "Check completeness against rules.yaml (one batched MCP "
            "Elicitation call for non-blocking gaps), cross-validate against "
            "Mock EHR (7 FA5 Table 4 rules), score risk via Secondary MCP, "
            "and write the JSON+HTML audit report. Works for any patient_id."
        ),
        tags=["validator", "rules-engine", "ehr", "risk", "reporter"],
        examples=[
            "Validate P1022",
            "Validate P2001 (new patient, any language)",
        ],
    )

    return AgentCard(
        name="Clinical Validation Agent",
        description=(
            "LangGraph agent that runs completeness, EHR cross-validation, "
            "risk scoring, and reporting for one discharge case."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    svc = get_service("validator")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8101))

    agent_card = build_agent_card(host, port)
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ValidatorAgentExecutor(),
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
