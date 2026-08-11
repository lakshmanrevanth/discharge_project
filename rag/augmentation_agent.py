"""Agno Augmentation Agent — keyword re-rank (SSoT §5.6 agent 3).

Beginner picture: after FAISS returns top-k, boost chunks that share more
words with the question. Pure Python — no second LLM path.
"""

from __future__ import annotations

import json
import re

from agno.agent import Agent

from rag.model import get_agno_model
from shared.logger import get_logger

logger = get_logger("rag_augmentation")

_WORD_RE = re.compile(r"[a-z0-9\u00c0-\u024f]+", re.IGNORECASE)

# Drop filler so "patient" / "what" alone cannot mark unrelated chunks as useful.
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "what",
        "who",
        "when",
        "where",
        "why",
        "how",
        "this",
        "that",
        "with",
        "from",
        "about",
        "please",
        "tell",
        "give",
        "show",
        "list",
        "patient",
        "patients",
        "record",
        "records",
        "information",
        "available",
        "does",
        "did",
        "has",
        "have",
        "had",
        "any",
        "all",
        "his",
        "her",
        "their",
        "our",
        "your",
        "qué",
        "que",
        "cual",
        "cuál",
        "welke",
        "wat",
        "wie",
    }
)

# Light clinical aliases so EN questions match ES/NL wording and stems
# (prescribed ↔ prescriptions / recetas / recepten). One path — still keyword re-rank.
_ALIASES: dict[str, frozenset[str]] = {
    "prescribed": frozenset(
        {
            "prescribed",
            "prescribe",
            "prescription",
            "prescriptions",
            "receta",
            "recetas",
            "recept",
            "recepten",
            "voorgeschreven",
            "medicatie",
        }
    ),
    "medications": frozenset(
        {
            "medications",
            "medication",
            "medicine",
            "medicines",
            "meds",
            "drug",
            "drugs",
            "medicamentos",
            "medicamento",
            "medicijnen",
            "medicijn",
            "geneesmiddel",
            "geneesmiddelen",
        }
    ),
    "medicijnen": frozenset(
        {
            "medicijnen",
            "medicijn",
            "medications",
            "medication",
            "medicine",
            "medicines",
            "medicamentos",
        }
    ),
    "medicamentos": frozenset(
        {
            "medicamentos",
            "medicamento",
            "medications",
            "medication",
            "medicine",
            "medicines",
            "receta",
            "recetas",
        }
    ),
    "allergy": frozenset({"allergy", "allergies", "alergia", "alergias", "allergie", "allergieën"}),
    "allergies": frozenset({"allergy", "allergies", "alergia", "alergias", "allergie", "allergieën"}),
    "diagnosis": frozenset({"diagnosis", "diagnoses", "diagnóstico", "diagnostico", "diagnose", "ontslagdiagnose"}),
    "lab": frozenset({"lab", "labs", "laboratory", "laboratorio", "laboratorium", "labs"}),
    "bill": frozenset({"bill", "billing", "factura", "rekening", "kosten", "payment", "pago"}),
    "follow": frozenset({"follow", "followup", "seguimiento", "opvolging", "cita", "afspraak"}),
}


def _expand(token: str) -> set[str]:
    """Token plus clinical aliases + simple English stems."""
    t = token.lower()
    out = {t}
    out |= set(_ALIASES.get(t, ()))
    # crude stems: prescriptions → prescription; medications → medication
    for suf in ("ations", "ation", "tions", "tion", "ments", "ment", "ies", "es", "ed", "ing", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            stem = t[: -len(suf)]
            out.add(stem)
            out |= set(_ALIASES.get(stem, ()))
            break
    return out


def _raw_tokens(text: str) -> set[str]:
    """Tokens without alias expansion (used for chunk text)."""
    return {
        t.lower()
        for t in _WORD_RE.findall(text or "")
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def _question_tokens(text: str) -> set[str]:
    """Question tokens + clinical aliases/stems (match ES/NL/EN wording)."""
    expanded: set[str] = set()
    for t in _raw_tokens(text):
        expanded |= _expand(t)
    return expanded


def _tokens(text: str) -> set[str]:
    """Back-compat: expanded tokens (tests / tools)."""
    return _question_tokens(text)


def rerank_by_keywords(question: str, chunks_json: str) -> str:
    """Tool: re-rank chunk JSON by keyword overlap with the question."""
    try:
        chunks = json.loads(chunks_json) if isinstance(chunks_json, str) else chunks_json
    except json.JSONDecodeError:
        chunks = []
    ranked = rerank_chunks(question, chunks if isinstance(chunks, list) else [])
    return json.dumps(ranked, ensure_ascii=False)


def rerank_chunks(question: str, chunks: list[dict]) -> list[dict]:
    """Re-rank FAISS hits; keyword boosts same-language overlap without burying semantic hits.

    Question tokens are alias-expanded (prescribed→prescriptions/recetas).
    Chunk tokens stay raw so a single shared word like "medicamentos" in
    discharge instructions cannot outrank the actual prescription table.
    """
    q_tokens = _question_tokens(question)
    scored: list[dict] = []
    for chunk in chunks:
        text = chunk.get("text") or ""
        c_tokens = _raw_tokens(text)
        overlap = len(q_tokens & c_tokens)
        keyword_score = overlap / max(len(q_tokens), 1)
        faiss_score = float(chunk.get("score") or 0.0)
        row = dict(chunk)
        row["keyword_score"] = round(keyword_score, 4)
        # FAISS first; light keyword bump (Augmentation still re-ranks)
        row["rank_score"] = faiss_score + 0.2 * keyword_score
        scored.append(row)

    scored.sort(key=lambda r: r["rank_score"], reverse=True)
    logger.info("Re-ranked %s chunk(s)", len(scored))
    return scored


augmentation_agent = Agent(
    name="augmentation_agent",
    model=get_agno_model(),
    description="Re-ranks retrieved FAISS chunks by keyword relevance to the question.",
    instructions=(
        "When asked to re-rank chunks, call rerank_by_keywords with the question "
        "and the JSON list of chunks. Do not invent new chunks."
    ),
    tools=[rerank_by_keywords],
)


async def run_augmentation(question: str, chunks: list[dict]) -> list[dict]:
    """Deterministic re-rank used by the RAG pipeline."""
    return rerank_chunks(question, chunks)
