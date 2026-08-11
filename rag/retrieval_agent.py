"""Agno Retrieval Agent — embed question, FAISS top-k (SSoT §5.6 agent 2).

Always scoped to one patient_id so answers never mix patients.
top_k / retrieve_k come from agent_config.yaml services.rag.

For multilingual questions (ES/NL/HI/…), also retrieve with a short English
clinical bridge query built from aliases, then merge — MiniLM often ranks
same-language filler higher than the actual med table otherwise.
"""

from __future__ import annotations

import json

from agno.agent import Agent

from rag.augmentation_agent import _ALIASES, _question_tokens
from rag.model import get_agno_model
from rag.vectorstore import search_patient
from shared.logger import get_logger
from shared.settings import get_service

logger = get_logger("rag_retrieval")

_BRIDGE_QUERIES = (
    (
        _ALIASES["medications"]
        | _ALIASES["prescribed"]
        | _ALIASES["medicijnen"]
        | _ALIASES["medicamentos"],
        "discharge medications prescriptions medicine list drug names",
    ),
    (
        _ALIASES["allergies"] | _ALIASES["allergy"],
        "allergies allergy NKDA drug allergy",
    ),
    (
        _ALIASES["diagnosis"],
        "discharge diagnosis ICD",
    ),
    (
        _ALIASES["lab"],
        "laboratory lab results values",
    ),
    (
        _ALIASES["bill"],
        "hospital bill payment amount total",
    ),
    (
        _ALIASES["follow"],
        "follow-up appointment clinic",
    ),
)


def _bridge_query(question: str) -> str | None:
    """Optional English retrieval hint when the question hits clinical aliases."""
    tokens = _question_tokens(question)
    for markers, bridge in _BRIDGE_QUERIES:
        if tokens & markers:
            return bridge
    return None


def _merge_hits(primary: list[dict], secondary: list[dict], k: int) -> list[dict]:
    """Merge native + bridge hits.

    Bridge hits (English clinical hint) must not be dropped when the native
    question language scores filler chunks higher — reserve ~half the slots.
    """
    def _key(hit: dict) -> tuple[str, str]:
        return (str(hit.get("source_path") or ""), str(hit.get("text") or ""))

    def _score(hit: dict) -> float:
        return float(hit.get("score") or 0.0)

    best: dict[tuple[str, str], dict] = {}
    for hit in primary + secondary:
        key = _key(hit)
        prev = best.get(key)
        if prev is None or _score(hit) > _score(prev):
            best[key] = dict(hit)

    bridge_keys = {_key(h) for h in secondary}
    ranked = sorted(best.values(), key=_score, reverse=True)
    bridge_n = max(2, k // 2)
    forced = [h for h in ranked if _key(h) in bridge_keys][:bridge_n]
    forced_keys = {_key(h) for h in forced}
    rest = [h for h in ranked if _key(h) not in forced_keys]
    return (forced + rest)[:k]


def retrieve_chunks(patient_id: str, question: str) -> str:
    """Tool: return top-k chunks as JSON for this patient."""
    cfg = get_service("rag")
    k = int(cfg.get("retrieve_k") or cfg.get("top_k", 4))
    hits = search_patient(patient_id, question, k=k)
    bridge = _bridge_query(question)
    if bridge:
        hits = _merge_hits(hits, search_patient(patient_id, bridge, k=k), k=k)
    logger.info("Retrieved %s chunk(s) for %s", len(hits), patient_id)
    return json.dumps(hits, ensure_ascii=False)


retrieval_agent = Agent(
    name="retrieval_agent",
    model=get_agno_model(),
    description="Embeds a clinical question and retrieves top-k FAISS chunks for one patient.",
    instructions=(
        "When asked to retrieve context for a patient question, call retrieve_chunks. "
        "Never invent chunk text."
    ),
    tools=[retrieve_chunks],
)


async def run_retrieval(patient_id: str, question: str) -> list[dict]:
    """Deterministic retrieval used by the RAG pipeline."""
    cfg = get_service("rag")
    k = int(cfg.get("retrieve_k") or cfg.get("top_k", 4))
    hits = search_patient(patient_id, question, k=k)
    bridge = _bridge_query(question)
    if bridge:
        extra = search_patient(patient_id, bridge, k=k)
        hits = _merge_hits(hits, extra, k=k)
        logger.info("Merged bridge retrieval %r → %s chunk(s)", bridge, len(hits))
    return hits
