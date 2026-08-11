"""Streamlit elicitation callback (SSoT §3.7).

Beginner picture:
  - Rules Engine calls ctx.elicit() once with a dynamic schema.
  - This handler stages the request and, when the reviewer already filled
    Page 3's form (accept / decline / cancel), returns that ElicitResult.
  - If nothing is staged yet, declines safely (Mandatory HITL) so headless
    runs never hang.

Page 3 is the human-facing form; this module is the MCP client bridge.

Important: FastMCP re-validates accept ``data`` on the server. Returning a
Pydantic model instance (or None) can arrive as ``None`` and crash
``clinical_rules_engine`` — always return a plain ``dict``.
"""

from __future__ import annotations

import re
from typing import Any

from fastmcp.client.elicitation import ElicitResult

from shared.logger import get_logger

logger = get_logger("hitl_elicitation")

# Staged reviewer decision for the next Rules Engine elicit() call.
# Shape: {"action": "accept"|"decline"|"cancel", "data": dict|None, "message": str}
_staged_response: dict[str, Any] | None = None
_last_request: dict[str, Any] | None = None


def stage_elicitation_response(
    action: str,
    data: dict | None = None,
    message: str = "",
) -> None:
    """Called from Page 3 when the reviewer clicks Accept / Decline / Cancel."""
    global _staged_response
    if action not in {"accept", "decline", "cancel"}:
        raise ValueError(f"invalid elicitation action: {action}")
    _staged_response = {"action": action, "data": data or {}, "message": message}
    logger.info("Staged elicitation action=%s fields=%s", action, list((data or {}).keys()))


def clear_staged_response() -> None:
    global _staged_response
    _staged_response = None


def last_elicitation_request() -> dict | None:
    """Most recent elicit request seen by the handler (for Page 3 display)."""
    return _last_request


def _schema_field_names(response_type: Any) -> list[str]:
    """Best-effort field list from a Pydantic model / JSON schema / message."""
    if response_type is None:
        return []
    model_fields = getattr(response_type, "model_fields", None)
    if isinstance(model_fields, dict) and model_fields:
        return list(model_fields.keys())
    schema_fn = getattr(response_type, "model_json_schema", None)
    if callable(schema_fn):
        props = (schema_fn() or {}).get("properties") or {}
        if props:
            return list(props.keys())
    if isinstance(response_type, dict):
        props = response_type.get("properties") or {}
        if isinstance(props, dict) and props:
            return list(props.keys())
    return []


def _fields_from_message(message: object) -> list[str]:
    """Parse '… or decline: age, attending_physician' from the Rules Engine text."""
    text = str(message or "")
    match = re.search(r"decline:\s*(.+)$", text, flags=re.IGNORECASE)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def _accept_payload(response_type: Any, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Build a plain dict FastMCP can re-validate (never return a model instance)."""
    raw = {k: v for k, v in (data or {}).items() if v not in ("", None)}
    if fields:
        raw = {k: raw[k] for k in fields if k in raw}
    if response_type is not None and hasattr(response_type, "model_validate"):
        try:
            model = response_type.model_validate(raw)
            dumped = model.model_dump(exclude_none=True)
            if isinstance(dumped, dict):
                return dumped
        except Exception as exc:
            logger.warning("Elicitation schema bind failed (%s) — using raw dict", exc)
    return raw


async def streamlit_elicitation_handler(message, response_type, params, context) -> ElicitResult:
    """FastMCP elicitation_handler used during interactive Validator re-runs."""
    global _last_request, _staged_response
    fields = _schema_field_names(response_type) or _fields_from_message(message)
    _last_request = {
        "message": str(message or ""),
        "fields": fields,
    }
    logger.info("Elicitation request: %s fields=%s", message, fields)

    staged = _staged_response
    _staged_response = None  # one-shot

    if staged is None:
        logger.info("No staged HITL response — declining elicitation")
        return ElicitResult(action="decline")

    action = staged.get("action", "decline")
    if action == "accept":
        payload = _accept_payload(response_type, staged.get("data") or {}, fields)
        logger.info("Accepting elicitation with fields=%s", list(payload.keys()))
        # FastMCP server reads ``content`` (not ``data``) — data= leaves content=None
        # and crashes clinical_rules_engine with ValidationError(input_value=None).
        return ElicitResult(action="accept", content=payload)

    return ElicitResult(action=action)
