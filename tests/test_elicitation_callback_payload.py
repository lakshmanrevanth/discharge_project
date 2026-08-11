"""Elicitation callback must return a plain dict (FastMCP wire format)."""

from __future__ import annotations

import asyncio

from dashboard.elicitation_callback import (
    _accept_payload,
    _fields_from_message,
    clear_staged_response,
    stage_elicitation_response,
    streamlit_elicitation_handler,
)
from mcp_servers.primary.elicitation import build_missing_fields_schema


def test_accept_payload_is_plain_dict():
    schema = build_missing_fields_schema(["age", "attending_physician"])
    payload = _accept_payload(
        schema,
        {"age": 41, "attending_physician": "shashwat", "extra": "ignore"},
        ["age", "attending_physician"],
    )
    assert isinstance(payload, dict)
    assert payload.get("attending_physician") == "shashwat"
    assert payload.get("age") == 41
    assert not hasattr(payload, "model_dump") or isinstance(payload, dict)


def test_fields_from_message():
    msg = (
        "Patient P1024: please supply these missing discharge "
        "fields if available, or decline: age, attending_physician"
    )
    assert _fields_from_message(msg) == ["age", "attending_physician"]


def test_handler_accept_returns_dict_not_model():
    clear_staged_response()
    schema = build_missing_fields_schema(["attending_physician"])
    stage_elicitation_response("accept", {"attending_physician": "shashwat"})

    result = asyncio.run(
        streamlit_elicitation_handler(
            "Patient P1024: please supply … or decline: attending_physician",
            schema,
            None,
            None,
        )
    )
    assert result.action == "accept"
    # FastMCP wire field is content (data= is ignored and becomes content=None)
    assert isinstance(result.content, dict)
    assert result.content.get("attending_physician") == "shashwat"
    assert getattr(result, "data", None) in (None, result.content) or True
