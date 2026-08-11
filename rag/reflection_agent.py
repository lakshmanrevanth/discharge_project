"""Agno Reflection Agent — RAG Triad scores (SSoT §5.6 agent 5).

Scores (0–1): faithfulness, answer_relevance, context_relevance.
No company style sample exists for Triad — keep this a simple LLM-as-judge.
Thresholds come from rules.yaml via HallucinationChecker helpers.
"""

from __future__ import annotations

import json

from agno.agent import Agent

from rag.model import get_agno_model
from shared.llm import arun_completion
from shared.logger import get_logger

logger = get_logger("rag_reflection")


def _extract_json(text: str) -> dict:
    """Pull the first JSON object from an LLM reply (beginner-tolerant)."""
    text = (text or "").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


async def score_rag_triad(question: str, context: str, answer: str) -> dict:
    """LLM-as-judge → triad scores in 0..1."""
    system = (
        "You are a strict clinical RAG evaluator. "
        "Score the answer against the retrieved context. "
        "The question, context, or answer may be in English, Spanish, Hindi, "
        "German, French, or Dutch — judge grounding, not language. "
        "Return ONLY a single JSON object with keys: "
        "faithfulness, answer_relevance, context_relevance "
        "(each a number from 0.0 to 1.0). No markdown, no prose."
    )
    user = (
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Answer:\n{answer}\n\n"
        "JSON scores:"
    )
    text, model = await arun_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        hint_names=["nova-lite"],
        temperature=0.0,
    )
    data = _extract_json(text)
    if not data:
        # One retry — malformed judge output must not zero-out a good answer.
        text, model = await arun_completion(
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user + "\n\nReply with JSON only, e.g. "
                    '{"faithfulness":0.9,"answer_relevance":0.9,"context_relevance":0.9}',
                },
            ],
            hint_names=["nova-lite"],
            temperature=0.0,
        )
        data = _extract_json(text)
    if not data:
        logger.warning("Triad judge returned no JSON — skipping hard fail this turn")
        return {
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "context_relevance": 1.0,
            "judge_model": model,
            "parse_failed": True,
        }
    triad = {
        "faithfulness": float(data.get("faithfulness", 0.0) or 0.0),
        "answer_relevance": float(data.get("answer_relevance", 0.0) or 0.0),
        "context_relevance": float(data.get("context_relevance", 0.0) or 0.0),
        "judge_model": model,
    }
    # Clamp to [0, 1]
    for key in ("faithfulness", "answer_relevance", "context_relevance"):
        triad[key] = max(0.0, min(1.0, float(triad[key])))
    logger.info("RAG Triad scores=%s", triad)
    return triad


reflection_agent = Agent(
    name="reflection_agent",
    model=get_agno_model(),
    description="Scores RAG answers with Faithfulness / Answer Relevance / Context Relevance.",
    instructions=(
        "When asked to score a RAG answer, evaluate faithfulness, answer_relevance, "
        "and context_relevance between 0 and 1. Return JSON only."
    ),
)


async def run_reflection(question: str, chunks: list[dict], answer: str) -> dict:
    """Pipeline entry: build context string and score the triad."""
    context = "\n\n".join((c.get("text") or "") for c in chunks)
    return await score_rag_triad(question, context, answer)
