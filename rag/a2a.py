"""A2A AgentCard + streaming executor for Clinical RAG Q&A (:8105).

SSoT §4: streaming=True — token-like progressive answer chunks.
Pattern mirrors agents/summary/a2a.py (a2a-sdk==0.3.22).
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

from rag.pipeline import ask
from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("rag_a2a")

_PATIENT_ID_RE = re.compile(r"\bP\d+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    match = _PATIENT_ID_RE.search(query or "")
    return match.group(0).upper() if match else None


def _try_parse_json(query: str) -> dict | None:
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


def _parse_request(query: str) -> tuple[str | None, str, str | None]:
    """Return (patient_id, question, session_id) from free text and/or JSON."""
    payload = _try_parse_json(query) or {}
    patient_id = payload.get("patient_id") or _extract_patient_id(query)
    if patient_id:
        patient_id = str(patient_id).upper()

    question = (
        payload.get("question")
        or payload.get("query")
        or ""
    ).strip()
    if not question:
        # Strip JSON blob / patient id from free text → leftover is the question
        text = query or ""
        if payload:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = (text[:start] + text[end + 1 :]).strip()
        text = _PATIENT_ID_RE.sub(" ", text)
        for noise in ("ask", "question", "about", "for", "patient", "rag"):
            text = re.sub(rf"\b{noise}\b", " ", text, flags=re.IGNORECASE)
        question = " ".join(text.split()).strip()

    session_id = payload.get("session_id")
    return patient_id, question, str(session_id) if session_id else None


def _chunk_text(text: str, size: int = 48) -> list[str]:
    """Split answer into small pieces for progressive A2A streaming."""
    text = text or ""
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


class RagAgentExecutor(AgentExecutor):
    """Stream the RAG answer (+ sources / triad artifacts)."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        logger.info("RAG A2A request: %s", (query or "")[:200])

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        patient_id, question, session_id = _parse_request(query or "")

        if not patient_id:
            await updater.add_artifact(
                [
                    Part(
                        root=TextPart(
                            text=(
                                "Could not find a patient_id. Send text like "
                                "'Ask about P1019 medications' or JSON with "
                                "patient_id and question."
                            )
                        )
                    )
                ],
                name="rag_error",
            )
            await updater.complete()
            return

        if not question:
            await updater.add_artifact(
                [
                    Part(
                        root=TextPart(
                            text="Could not find a question. Include a clinical question for this patient."
                        )
                    )
                ],
                name="rag_error",
            )
            await updater.complete()
            return

        await updater.start_work()
        try:
            result = await ask(patient_id, question, session_id=session_id)

            # Progressive answer stream (token-like chunks)
            for piece in _chunk_text(result.get("answer") or ""):
                await updater.add_artifact(
                    [Part(root=TextPart(text=piece))],
                    name="rag_answer_chunk",
                    append=True,
                    last_chunk=False,
                )
            # Final full answer artifact (easy for non-streaming clients too)
            await updater.add_artifact(
                [Part(root=TextPart(text=result.get("answer") or ""))],
                name="rag_answer",
                last_chunk=True,
            )
            await updater.add_artifact(
                [
                    Part(
                        root=TextPart(
                            text=json.dumps(
                                {
                                    "sources": result.get("sources", []),
                                    "triad": result.get("triad", {}),
                                    "refused": result.get("refused", False),
                                    "notes": result.get("notes", []),
                                    "patient_id": result.get("patient_id"),
                                    "session_id": result.get("session_id"),
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    )
                ],
                name="rag_meta",
            )
            await updater.complete()
        except Exception as exc:
            logger.error("RAG failed for %s: %s", patient_id, exc)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"RAG error for {patient_id}: {exc}"))],
                name="rag_error",
            )
            await updater.complete()
            raise

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())


class AgentAuthMiddleware(BaseHTTPMiddleware):
    """Require X-Agent-Auth-Token (SSoT §4). /.well-known/ stays public."""

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
        id="clinical_rag_qa",
        name="Clinical RAG Q&A",
        description=(
            "Ask grounded clinical questions about one patient's discharge "
            "records. Out-of-context questions receive the exact FA5 refusal."
        ),
        tags=["rag", "faiss", "streaming", "agno"],
        examples=[
            "Ask about P1019 medications",
            '{"patient_id":"P1019","question":"What is the discharge diagnosis?"}',
        ],
    )

    return AgentCard(
        name="Clinical RAG Q&A Agent",
        description=(
            "Agno multi-agent RAG (Indexing → Retrieval → Augmentation → "
            "Generation → Reflection) exposed over A2A streaming."
        ),
        url=f"http://{host}:{port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=push_enabled),
        skills=[skill],
    )


def build_a2a_app() -> Starlette:
    svc = get_service("rag")
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port", 8105))

    agent_card = build_agent_card(host, port)
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    push_config_store = InMemoryPushNotificationConfigStore()
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=RagAgentExecutor(),
        task_store=InMemoryTaskStore(),
        push_config_store=push_config_store,
        push_sender=push_sender,
    )
    server = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)
    app = server.build()
    app.add_middleware(AgentAuthMiddleware)
    return app
