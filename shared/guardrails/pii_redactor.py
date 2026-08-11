"""PIIRedactor — mask name/phone/Aadhaar/PAN before logging/API (SSoT §8)."""

from __future__ import annotations

import re

# Indian Aadhaar: 12 digits, often spaced as 4-4-4
_AADHAAR_RE = re.compile(r"\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b")
# PAN: 5 letters + 4 digits + 1 letter
_PAN_RE = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b", re.IGNORECASE)
# Phone: prefer explicit +country / 10-digit mobile patterns (avoid eating dates)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"
    r"|(?<!\d)\+\d{1,3}[\s-]?\d{6,12}(?!\d)"
)


def redact_text(text: str, *, names: list[str] | None = None) -> str:
    """Mask PII/PHI patterns in a string. Safe for logging / outbound API payloads."""
    if not text:
        return text
    out = str(text)

    out = _AADHAAR_RE.sub("XXXX-XXXX-XXXX", out)
    out = _PAN_RE.sub("XXXXXXXXXX", out)
    out = _PHONE_RE.sub("[PHONE_REDACTED]", out)

    for name in names or []:
        name = (name or "").strip()
        if len(name) < 3:
            continue
        # Whole-word-ish replace (case-insensitive)
        out = re.sub(re.escape(name), "[NAME_REDACTED]", out, flags=re.IGNORECASE)

    return out


def redact_for_log(message: object, *, names: list[str] | None = None) -> str:
    """Convenience wrapper for logger formatters / call sites."""
    return redact_text("" if message is None else str(message), names=names)


# Module-level alias matching SSoT module name
class PIIRedactor:
    """Thin class wrapper so imports match FA5 Table 12 naming."""

    @staticmethod
    def redact(text: str, names: list[str] | None = None) -> str:
        return redact_text(text, names=names)
