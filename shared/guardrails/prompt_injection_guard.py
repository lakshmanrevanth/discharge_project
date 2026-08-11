"""PromptInjectionGuard — sanitize/reject injection attempts (SSoT §8).

Beginner picture: before RAG retrieval, scan the user question for common
injection phrases. If found, reject (caller returns a safe message).
Patterns live here in one short list — keep it obvious and readable.
"""

from __future__ import annotations

import re

from shared.logger import get_logger

logger = get_logger("prompt_injection_guard")

# Obvious prompt-injection phrases (case-insensitive).
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|prompts)",
    r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)",
    r"system\s*:\s*you\s+are",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"<\s*/?\s*system\s*>",
]


def check_prompt_injection(question: str) -> tuple[bool, str]:
    """Return (is_safe, message).

    is_safe=False means the caller must NOT run retrieval/generation.
    """
    text = question or ""
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            logger.warning("Prompt injection detected: %r", pattern)
            return False, "Query rejected: possible prompt injection detected."
    return True, text.strip()
