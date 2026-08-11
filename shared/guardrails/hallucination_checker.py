"""HallucinationChecker — block low-faithfulness RAG answers (SSoT §8).

Conflict §16 row 5: FA5 Table 12 uses faithfulness < 0.7; rules.yaml has
rag_groundedness_min: 0.75. We enforce the stricter rules.yaml floor (0.75).
"""

from __future__ import annotations

from shared.logger import get_logger
from shared.rules_config import load_rules

logger = get_logger("hallucination_checker")


def groundedness_min() -> float:
    """Read rag_groundedness_min from rules.yaml (default 0.75)."""
    quality = load_rules().get("quality_thresholds", {})
    return float(quality.get("rag_groundedness_min", 0.75))


def relevance_min() -> float:
    """Read rag_relevance_min from rules.yaml (default 0.70)."""
    quality = load_rules().get("quality_thresholds", {})
    return float(quality.get("rag_relevance_min", 0.70))


def check_hallucination(triad: dict) -> tuple[bool, str]:
    """Return (ok, reason). ok=False → block / regenerate (SSoT §8)."""
    faith = float(triad.get("faithfulness", 0.0))
    ans_rel = float(triad.get("answer_relevance", 0.0))
    ctx_rel = float(triad.get("context_relevance", 0.0))

    g_min = groundedness_min()
    r_min = relevance_min()

    if faith < g_min:
        msg = f"Faithfulness {faith:.2f} below rag_groundedness_min {g_min}"
        logger.warning(msg)
        try:
            from shared.tracing.langfuse import record_guardrail

            record_guardrail("HallucinationChecker", "blocked", blocked=True, detail=msg)
        except Exception:
            pass
        return False, msg
    if ans_rel < r_min or ctx_rel < r_min:
        msg = (
            f"Relevance answer={ans_rel:.2f} context={ctx_rel:.2f} "
            f"below rag_relevance_min {r_min}"
        )
        logger.warning(msg)
        try:
            from shared.tracing.langfuse import record_guardrail

            record_guardrail("HallucinationChecker", "blocked", blocked=True, detail=msg)
        except Exception:
            pass
        return False, msg
    try:
        from shared.tracing.langfuse import record_guardrail

        record_guardrail("HallucinationChecker", "allowed", blocked=False)
    except Exception:
        pass
    return True, "ok"
