"""RAG pipeline — five Agno agents in one clear path (SSoT §5.6).

Beginner order (always the same):
  1. PromptInjectionGuard
  2. Indexing Agent
  3. Retrieval Agent
  4. Augmentation Agent
  5. Generation Agent  (or exact refusal if no useful context)
  6. Reflection Agent + HallucinationChecker
     - fail once → regenerate once
     - fail again → exact refusal (never invent)

Works for ANY patient_id that has intake files under data/input/.
"""

from __future__ import annotations

import uuid

from rag.augmentation_agent import run_augmentation
from rag.generation_agent import refusal_text, run_generation
from rag.indexing_agent import run_indexing
from rag.reflection_agent import run_reflection
from rag.retrieval_agent import run_retrieval
from shared.guardrails.hallucination_checker import check_hallucination
from shared.guardrails.prompt_injection_guard import check_prompt_injection
from shared.logger import get_logger
from shared.settings import get_service

logger = get_logger("rag_pipeline")


def _context_is_useful(chunks: list[dict]) -> bool:
    """True when retrieved context is good enough to answer (any language).

    FAISS always returns *some* neighbors — even for World-Cup style questions —
    so we still gate. Two signals (either is enough):

    1. Keyword overlap after stopword filter (same-language questions).
    2. FAISS similarity >= services.rag.min_similarity — embeddings still
       match clinical meaning across ES/NL/HI vs English questions.

    Generation + RAG Triad remain the final safety net; this only blocks
    clearly empty / clearly unrelated retrieval.
    """
    if not any((c.get("text") or "").strip() for c in chunks):
        return False

    kw_scores = [float(c.get("keyword_score") or 0.0) for c in chunks]
    if max(kw_scores) > 0.0:
        return True

    faiss_scores = [float(c.get("score") or 0.0) for c in chunks]
    min_sim = float(get_service("rag").get("min_similarity", 0.28))
    return max(faiss_scores) >= min_sim


async def ask(
    patient_id: str,
    question: str,
    session_id: str | None = None,
) -> dict:
    """Run the full RAG path for one patient question.

    Returns a plain dict:
      answer, refused, sources, triad, notes, patient_id, session_id
    """
    patient_id = str(patient_id).strip().upper()
    session_id = session_id or str(uuid.uuid4())
    notes: list[str] = []
    refuse = refusal_text()

    # 0) Injection guard
    safe, guarded = check_prompt_injection(question)
    if not safe:
        return {
            "patient_id": patient_id,
            "session_id": session_id,
            "answer": guarded,
            "refused": True,
            "sources": [],
            "triad": {},
            "notes": ["prompt_injection_rejected"],
        }
    question = guarded

    # 1) Index
    index_msg = await run_indexing(patient_id)
    notes.append(index_msg)

    # 2) Retrieve
    chunks = await run_retrieval(patient_id, question)

    # 3) Augment (keyword re-rank)
    chunks = await run_augmentation(question, chunks)

    # Out of context → exact refusal (no LLM invent)
    if not _context_is_useful(chunks):
        logger.info("No useful context for %s — refusing", patient_id)
        return {
            "patient_id": patient_id,
            "session_id": session_id,
            "answer": refuse,
            "refused": True,
            "sources": [],
            "triad": {},
            "notes": notes + ["no_useful_context"],
        }

    # 4) Generate (+ one regenerate on Triad/hallucination failure)
    answer = await run_generation(
        patient_id=patient_id,
        question=question,
        chunks=chunks,
        session_id=session_id,
    )

    # If the model already refused, skip reflection
    if answer.strip() == refuse:
        return {
            "patient_id": patient_id,
            "session_id": session_id,
            "answer": refuse,
            "refused": True,
            "sources": _sources(chunks),
            "triad": {},
            "notes": notes + ["generation_refused"],
        }

    # 5) Reflect
    triad = await run_reflection(question, chunks, answer)
    ok, reason = check_hallucination(triad)
    if not ok:
        notes.append(f"triad_failed:{reason}")
        logger.warning("Regenerating once after Triad failure for %s", patient_id)
        answer = await run_generation(
            patient_id=patient_id,
            question=question,
            chunks=chunks,
            session_id=session_id,
        )
        if answer.strip() == refuse:
            return {
                "patient_id": patient_id,
                "session_id": session_id,
                "answer": refuse,
                "refused": True,
                "sources": _sources(chunks),
                "triad": triad,
                "notes": notes + ["regenerate_refused"],
            }
        triad = await run_reflection(question, chunks, answer)
        ok, reason = check_hallucination(triad)
        if not ok:
            notes.append(f"triad_failed_again:{reason}")
            return {
                "patient_id": patient_id,
                "session_id": session_id,
                "answer": refuse,
                "refused": True,
                "sources": _sources(chunks),
                "triad": triad,
                "notes": notes + ["rag_unsafe_response"],
            }

    return {
        "patient_id": patient_id,
        "session_id": session_id,
        "answer": answer,
        "refused": False,
        "sources": _sources(chunks),
        "triad": triad,
        "notes": notes,
    }


def _sources(chunks: list[dict]) -> list[dict]:
    """Compact source list for the HITL / A2A caller."""
    out: list[dict] = []
    for c in chunks:
        out.append(
            {
                "source_path": c.get("source_path", ""),
                "doc_type": c.get("doc_type", ""),
                "score": c.get("score"),
                "keyword_score": c.get("keyword_score"),
                "preview": (c.get("text") or "")[:160],
            }
        )
    return out
