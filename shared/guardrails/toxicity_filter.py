"""ToxicityFilter — scrub unsafe phrasing from clinical instructions (SSoT §8).

Beginner picture: before the Summary Generator streams the `instructions`
section, run the LLM text through this filter. It is a small, readable
block-list — not a second LLM path. If a phrase matches, replace it with
a safe placeholder so the summary still streams.
"""

from __future__ import annotations

import re

from shared.logger import get_logger

logger = get_logger("toxicity_filter")

# Plain phrases that must never appear in patient-facing instructions.
# Keep the list short and obvious — extend in one place if needed later.
_BLOCKED_PHRASES = [
    "kill yourself",
    "end your life",
    "commit suicide",
    "hurt yourself",
    "overdose on purpose",
]

_PLACEHOLDER = "[filtered for safety]"


def filter_toxicity(text: str) -> str:
    """Return text with blocked phrases replaced. Empty input stays empty."""
    if not text:
        return text

    cleaned = text
    blocked_any = False
    for phrase in _BLOCKED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(cleaned):
            logger.warning("ToxicityFilter removed phrase: %r", phrase)
            cleaned = pattern.sub(_PLACEHOLDER, cleaned)
            blocked_any = True
    try:
        from shared.tracing.langfuse import record_guardrail

        record_guardrail(
            "ToxicityFilter",
            "blocked" if blocked_any else "allowed",
            blocked=blocked_any,
        )
    except Exception:
        pass
    return cleaned
