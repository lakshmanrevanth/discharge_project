"""A2A AgentCard + executor for Clinical Normalizer (non-streaming, :8102).

Pattern mirrors agents/extractor/a2a.py (a2a-sdk==0.3.22).
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

from agents.normalizer.graph import run_normalization
from shared.a2a_auth import get_a2a_auth_token
from shared.a2a_call import fetch_extraction_via_a2a
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config
from shared.tracing.langfuse import case_trace, trace_id_from_metadata

logger = get_logger("normalizer_a2a")

# Any digit length — FA5 examples use P001; sample corpus uses P1019; new
# patients can be P2001, P99999, etc. Not locked to a fixed sample list.
_PATIENT_ID_RE = re.compile(r"\bP\d+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    match = _PATIENT_ID_RE.search(query or "")
    return match.group(0).upper() if match else None


def _try_parse_extraction_json(query: str) -> dict | None:
    """If the A2A message embeds an ExtractionResult JSON blob, use it."""
    text = (query or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and (
        "discharge" in data or "lab" in data or "bill" in data or "patient_id" in data
    ):
        return data
    return None


class NormalizerAgentExecutor(AgentExecutor):
    """Normalize one patient's extraction via Medical Lang Bridge Sampling.

    Not limited to sample patients P1019–P1024 — any patient_id with an
    extraction (or files under data/input/) works; any source language too.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("Normalizer A2A request: %s", (query or "")[:200])

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        patient_id = _extract_patient_id(query)
        extraction = _try_parse_extraction_json(query)

        if not patient_id and extraction:
            # Prefer explicit patient_id inside the JSON (any string id)
            raw_id = extraction.get("patient_id")
            if raw_id:
                patient_id = str(raw_id)

        if not patient_id:
            message = (
                "Could not find a patient_id in the request. "
                "Send text like 'Normalize P2001' or embed an ExtractionResult JSON "
                "with a patient_id field."
            )
            await updater.add_artifact([Part(root=TextPart(text=message))], name="normalization_error")
            await updater.complete()
            return

        try:
            # Adopt the Host's case trace_id so this worker's spans land in the
            # same LangFuse trace instead of starting an orphan one (SSoT §9).
            incoming_tid = trace_id_from_metadata(context.message, task)
            with case_trace(patient_id, existing=incoming_tid, host_name="Normalizer Agent"):
                # Prefer embedded ExtractionResult JSON from Host / caller.
                # If missing, ask Extractor over A2A (:8100) — not a graph import.
                if extraction is None:
                    logger.info(
                        "No embedded extraction — A2A call to Extractor for %s",
                        patient_id,
                    )
                    extraction = await fetch_extraction_via_a2a(patient_id)

                result = await run_normalization(patient_id, extraction)
            await updater.add_artifact(
                [Part(root=TextPart(text=json.dumps(result, indent=2, ensure_ascii=False)))],
                name="clinical_normalization",
            )
            await updater.complete()
        except Exception as exc:
            logger.error("Normalization failed for %s: %s", patient_id, exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"Normalizer error for {patient_id}: {exc}"))],
                name="normalization_error",
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
        id="normalize_clinical_language",
        name="Normalize Clinical Language",
        description=(
            "Translate clinical extraction to English and expand medical "
            "abbreviations via MCP Sampling (Medical Lang Bridge). Works for "
            "any patient_id and any source language (or auto-detect). "
            "Always returns a translation confidence score."
        ),
        tags=["normalizer", "sampling", "translation", "abbreviations"],
        examples=[
            "Normalize clinical data for P1021",
            "Normalize P2001 (new patient, any language)",
            "Translate and expand abbreviations for patient P9999",
        ],
    )

    return AgentCard(
        name="Clinical Normalizer Agent",
        description=(
            "LangGraph agent that translates and normalizes clinical language "
            "using MCP Sampling via the Medical Lang Bridge tool."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    svc = get_service("normalizer")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8102))

    agent_card = build_agent_card(host, port)
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=NormalizerAgentExecutor(),
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
