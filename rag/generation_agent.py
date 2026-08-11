"""Agno Generation Agent — grounded answer via MCP prompt (SSoT §5.6 agent 4).

MUST:
  - Fetch rag-answer-prompt via MCP get_prompt (never hardcode) — §3.4
  - agno.Agent + MultiMCPTools + SqliteDb + num_history_runs=3 + arun() — §5.6
  - Out-of-context → exact refusal_text from agent_config.yaml
"""

from __future__ import annotations

import re

from agno.agent import Agent
from agno.db.base import SessionType
from agno.db.sqlite import SqliteDb
from agno.tools.mcp import MultiMCPTools
from fastmcp import Client

from rag.model import get_agno_model
from shared.logger import get_logger
from shared.settings import get_path, get_service

logger = get_logger("rag_generation")

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.IGNORECASE | re.DOTALL)


def _clean_answer(text: str) -> str:
    """Drop accidental model scratchpad tags; keep the patient-facing answer."""
    cleaned = _THINKING_RE.sub("", text or "")
    return cleaned.strip()


def _mcp_urls() -> tuple[list[str], list[str]]:
    """Primary + Secondary MCP URLs for MultiMCPTools (SSoT §3.1 dual connect).

    Prompts live on Primary. Secondary is included when reachable so RAG
    demonstrates simultaneous multi-server MCP; if Secondary is down we fall
    back to Primary-only so Generation still works.
    """
    urls: list[str] = []
    transports: list[str] = []
    for key in ("primary_mcp", "secondary_mcp"):
        svc = get_service(key)
        host = svc.get("host", "127.0.0.1")
        port = int(svc.get("port"))
        path = svc.get("transport_path", "")
        urls.append(f"http://{host}:{port}{path}")
        transports.append("streamable-http")
    return urls, transports


async def _connect_multi_mcp() -> MultiMCPTools:
    """Connect to both MCP servers; degrade to Primary-only if Secondary is down."""
    urls, transports = _mcp_urls()
    try:
        multi = MultiMCPTools(urls=urls, urls_transports=transports)
        await multi.connect()
        logger.info("RAG MultiMCP connected to Primary + Secondary")
        return multi
    except Exception as exc:
        logger.info("Dual MCP connect failed (%s) — Primary only", exc)
        primary_only = MultiMCPTools(urls=urls[:1], urls_transports=transports[:1])
        await primary_only.connect()
        return primary_only


def refusal_text() -> str:
    """Exact FA5 refusal string from agent_config (SSoT §5.6 / §18)."""
    return str(get_service("rag").get("refusal_text", "")).strip()


def _prompt_text(get_prompt_result) -> str:
    parts: list[str] = []
    for message in getattr(get_prompt_result, "messages", []) or []:
        content = getattr(message, "content", None)
        text = getattr(content, "text", None) if content is not None else None
        if text:
            parts.append(text)
        elif isinstance(content, str):
            parts.append(content)
    return "\n".join(parts).strip()


async def fetch_rag_answer_prompt(context_length: int) -> str:
    """MCP get_prompt('rag-answer-prompt') — never hardcode (§3.4)."""
    primary = get_service("primary_mcp")
    url = (
        f"http://{primary.get('host', '127.0.0.1')}:"
        f"{int(primary.get('port', 8200))}"
        f"{primary.get('transport_path', '/clinicaltools')}"
    )
    async with Client(url) as client:
        result = await client.get_prompt(
            "rag-answer-prompt",
            {"context_length": str(context_length)},
        )
    text = _prompt_text(result)
    if not text:
        raise RuntimeError("rag-answer-prompt returned empty text from MCP")
    logger.info("Fetched rag-answer-prompt (context_length=%s)", context_length)
    return text


def _session_db() -> SqliteDb:
    """SqliteDb under data/rag_sessions/ (paths from agent_config)."""
    sessions_dir = get_path("rag_sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    cfg = get_service("rag")
    db_name = cfg.get("session_db_file", "rag_sessions.db")
    table = cfg.get("session_table", "agent_sessions")
    db_file = str(sessions_dir / db_name)
    return SqliteDb(db_file=db_file, session_table=table)


def session_has_history(session_id: str | None) -> bool:
    """True when SqliteDb already has at least one prior run for this session."""
    if not session_id:
        return False
    try:
        db = _session_db()
        sess = db.get_session(session_id=session_id, session_type=SessionType.AGENT)
        runs = getattr(sess, "runs", None) if sess is not None else None
        return bool(runs)
    except Exception as exc:
        logger.info("session_has_history check failed (%s)", exc)
        return False


def _build_context_block(chunks: list[dict]) -> str:
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_path") or chunk.get("doc_type") or "unknown"
        parts.append(f"[chunk {i} | {source}]\n{chunk.get('text', '').strip()}")
    return "\n\n".join(parts)


def _history_instructions(refuse: str) -> str:
    return (
        "Clinical facts: use the retrieved patient-record context in the user "
        "message when it is present. "
        "Conversation: the last few chat turns are in history — use them when "
        "the question is about a prior question/answer, or to resolve references "
        "like 'that', 'it', 'previous', or 'last'. "
        "Do not invent clinical facts that are not in the retrieved context or "
        "clearly stated in recent chat history. "
        "Do not call MCP tools for this question — answer directly. "
        "Context may be English, Spanish, Hindi, German, French, or Dutch; "
        "answer from context/history even when the question language differs. "
        f"If neither history nor patient-record context supports the answer, "
        f"respond exactly:\n{refuse}"
    )


async def run_generation(
    *,
    patient_id: str,
    question: str,
    chunks: list[dict],
    session_id: str,
) -> str:
    """Generate a grounded answer with Agno + MultiMCPTools + SqliteDb + arun.

    Empty chunks still call arun so last-3 session history can answer follow-ups.
    """
    refuse = refusal_text()
    context = _build_context_block(chunks) if chunks else ""
    prompt_instructions = await fetch_rag_answer_prompt(context_length=len(context))

    multi_mcp = await _connect_multi_mcp()

    history_runs = int(get_service("rag").get("num_history_runs", 3))
    agent = Agent(
        name="generation_agent",
        model=get_agno_model(),
        description=(
            "Generates grounded clinical answers from retrieved patient-record "
            "context and recent chat history."
        ),
        instructions=[
            prompt_instructions,
            _history_instructions(refuse),
        ],
        tools=[multi_mcp],
        db=_session_db(),
        add_history_to_context=True,
        num_history_runs=history_runs,
        markdown=False,
    )

    if context:
        user_message = (
            f"Patient ID: {patient_id}\n"
            f"Question: {question}\n\n"
            f"Retrieved patient-record context:\n{context}\n\n"
            "Answer using patient-record context for clinical facts. "
            "Use chat history for prior Q&A and reference resolution."
        )
    else:
        user_message = (
            f"Patient ID: {patient_id}\n"
            f"Question: {question}\n\n"
            "No new patient-record context was retrieved for this question. "
            "Answer only from recent chat history if the question is about a "
            "prior turn or can be resolved from it; otherwise refuse exactly."
        )

    try:
        response = await agent.arun(user_message, session_id=session_id)
        content = getattr(response, "content", None)
        if content is None and getattr(response, "messages", None):
            content = response.messages[-1].content
        answer = (content or "").strip()
        if not answer:
            return refuse
        return _clean_answer(answer)
    finally:
        await multi_mcp.close()


# Framework identity — Generation Agent is constructed per-request inside
# run_generation (needs live MultiMCPTools + session). Exported name kept for
# discovery / Host later.
generation_agent = Agent(
    name="generation_agent",
    model=get_agno_model(),
    description="Grounded RAG Generation Agent (MultiMCPTools + SqliteDb + arun).",
    instructions="Answer clinical questions using retrieved patient-record context and recent chat history.",
)
