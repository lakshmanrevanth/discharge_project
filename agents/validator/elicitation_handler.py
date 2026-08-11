"""Validator MCP Elicitation client handler (SSoT §3.7).

Default: auto-decline (safe — decline forces Mandatory HITL, never silent approve).
HITL Streamlit can install a real handler via set_elicitation_handler(...) so
interactive re-runs show the reviewer form instead of auto-declining.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Awaitable, Callable

from fastmcp.client.elicitation import ElicitResult

from shared.logger import get_logger

logger = get_logger("validator_elicitation")

ElicitationHandler = Callable[..., Awaitable[ElicitResult]]

# Per-async-task override used by the Streamlit HITL dashboard (Phase 11).
_handler_override: ContextVar[ElicitationHandler | None] = ContextVar(
    "elicitation_handler_override",
    default=None,
)


def set_elicitation_handler(handler: ElicitationHandler | None):
    """Install (or clear) the elicitation handler for the current async context."""
    return _handler_override.set(handler)


def reset_elicitation_handler(token) -> None:
    """Restore the previous handler after a Streamlit-driven validation run."""
    _handler_override.reset(token)


async def auto_decline_elicitation_handler(message, response_type, params, context) -> ElicitResult:
    """Always decline when no human reviewer is attached."""
    logger.info("Elicitation auto-declined: %s", message)
    try:
        from shared.tracing.langfuse import record_elicitation

        record_elicitation(
            schema={"message": str(message or "")},
            reviewer_response=None,
            action="decline",
            metadata={"agent": "Validator Agent", "mode": "auto_decline"},
        )
    except Exception as exc:
        logger.info("Elicitation trace skipped: %s", exc)
    return ElicitResult(action="decline")


async def resolve_elicitation_handler(message, response_type, params, context) -> ElicitResult:
    """Dispatch to Streamlit override when set; otherwise auto-decline."""
    override = _handler_override.get()
    if override is not None:
        return await override(message, response_type, params, context)
    return await auto_decline_elicitation_handler(message, response_type, params, context)
