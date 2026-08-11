"""PIIRedactor — mask PII/PHI before logging or outbound API calls."""

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
_ADDRESS_LABEL_RE = re.compile(
    r"(?im)^(?P<label>\s*(?:residential\s+)?addr(?:ess)?\s*[:\-]\s*)(?P<value>.+)$"
)
_JSON_ADDRESS_VALUE_RE = re.compile(
    r'(?P<label>"(?:[a-z0-9]+[_ -])?address"\s*:\s*)"(?:\\.|[^"\\])*"',
    re.IGNORECASE,
)


def redact_text(
    text: str,
    *,
    names: list[str] | None = None,
    addresses: list[str] | None = None,
) -> str:
    """Mask PII/PHI patterns in a string. Safe for logging / outbound API payloads."""
    if not text:
        return text
    out = str(text)

    out = _AADHAAR_RE.sub("XXXX-XXXX-XXXX", out)
    out = _PAN_RE.sub("XXXXXXXXXX", out)
    out = _PHONE_RE.sub("[PHONE_REDACTED]", out)
    out = _ADDRESS_LABEL_RE.sub(lambda match: f'{match.group("label")}[ADDRESS_REDACTED]', out)
    out = _JSON_ADDRESS_VALUE_RE.sub(
        lambda match: f'{match.group("label")}"[ADDRESS_REDACTED]"', out
    )

    for name in names or []:
        name = (name or "").strip()
        if len(name) < 3:
            continue
        # Whole-word-ish replace (case-insensitive)
        out = re.sub(re.escape(name), "[NAME_REDACTED]", out, flags=re.IGNORECASE)

    for address in addresses or []:
        address = (address or "").strip()
        if len(address) >= 6:
            out = re.sub(re.escape(address), "[ADDRESS_REDACTED]", out, flags=re.IGNORECASE)

    return out


def _is_address_field(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized == "address" or normalized.endswith("_address")


def redact_payload(value: object, *, address_value: bool = False) -> object:
    """Recursively redact PII in a JSON-like API or observability payload."""
    if address_value:
        return "[ADDRESS_REDACTED]" if value is not None else None
    if isinstance(value, dict):
        return {
            str(key): redact_payload(item, address_value=_is_address_field(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_for_log(
    message: object,
    *,
    names: list[str] | None = None,
    addresses: list[str] | None = None,
) -> str:
    """Convenience wrapper for logger formatters / call sites."""
    return redact_text("" if message is None else str(message), names=names, addresses=addresses)


# Module-level alias matching SSoT module name
class PIIRedactor:
    """Thin class wrapper so imports match FA5 Table 12 naming."""

    @staticmethod
    def redact(
        text: str,
        names: list[str] | None = None,
        addresses: list[str] | None = None,
    ) -> str:
        return redact_text(text, names=names, addresses=addresses)
