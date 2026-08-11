"""Tiny A2A client helper (a2a-sdk==0.3.22 coding-style pattern).

Beginner picture:
  1. Look up the agent URL + auth token from agent_config.yaml.
  2. Fetch AgentCard from /.well-known/agent.json.
  3. send_message(...) and return the first artifact text.

Used by Normalizer to call Extractor over A2A (not a direct graph import).
"""

from __future__ import annotations

import json
import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)

from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("a2a_call")


def _service_base_url(service_key: str) -> str:
    svc = get_service(service_key)
    host = svc.get("host", "127.0.0.1")
    port = int(svc.get("port"))
    return f"http://{host}:{port}"


def _artifact_text(task: Task) -> str:
    """Pull plain text out of the first A2A artifact (beginner-simple)."""
    artifacts = task.artifacts or []
    if not artifacts:
        return ""
    parts = artifacts[0].parts or []
    chunks: list[str] = []
    for part in parts:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


async def send_a2a_text(
    service_key: str,
    message_text: str,
    timeout: float = 180.0,
    *,
    trace_id: str | None = None,
) -> str:
    """Send one non-streaming A2A user message; return artifact text.

    Propagates end-to-end case trace_id in message metadata (SSoT §9).
    Raises RuntimeError when the remote agent is down or returns an error.
    """
    from shared.tracing.langfuse import ensure_trace_id, get_current_trace_id, record_span

    tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
    base_url = _service_base_url(service_key)
    cfg = load_agent_config()
    header_name = cfg.get("a2a", {}).get("auth_header", "X-Agent-Auth-Token")
    headers = {header_name: get_a2a_auth_token()}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), headers=headers) as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
            agent_card_path="/.well-known/agent.json",
        )
        card = await resolver.get_agent_card()
        client = A2AClient(httpx_client, card, url=base_url)

        message_id = str(uuid.uuid4())
        payload = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": message_text}],
                "messageId": message_id,
                "metadata": {"trace_id": tid},
            },
            "metadata": {"trace_id": tid},
        }
        request = SendMessageRequest(
            id=message_id,
            params=MessageSendParams.model_validate(payload),
        )
        logger.info("A2A send → %s (%s) trace=%s", service_key, base_url, tid)
        response = await client.send_message(request)

    root = response.root
    if not isinstance(root, SendMessageSuccessResponse):
        raise RuntimeError(f"A2A {service_key} non-success: {response}")
    result = root.result
    if not isinstance(result, Task):
        raise RuntimeError(f"A2A {service_key} expected Task, got {type(result)}")

    text = _artifact_text(result)
    record_span(
        f"a2a.{service_key}",
        kind="agent",
        input_payload={"preview": (message_text or "")[:200]},
        output_payload={"chars": len(text or "")},
        metadata={"service_key": service_key, "trace_id": tid},
        trace_id=tid,
    )
    if not text:
        raise RuntimeError(f"A2A {service_key} returned empty artifact")
    return text


async def fetch_extraction_via_a2a(patient_id: str) -> dict:
    """Ask the Extractor agent (:8100) for one patient's ExtractionResult JSON."""
    raw = await send_a2a_text("extractor", f"Extract clinical data for {patient_id}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Sometimes the artifact has a short prefix — find the JSON object
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(raw[start : end + 1])
        else:
            raise RuntimeError(f"Extractor A2A did not return JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Extractor A2A JSON was not an object")
    if data.get("error") or (
        "discharge" not in data and "lab" not in data and "bill" not in data
        and "patient_id" not in data
    ):
        # Error artifacts are plain text; if we parsed a non-extraction dict, surface it
        if "clinical_extraction" not in str(data).lower() and not any(
            k in data for k in ("discharge", "lab", "bill", "patient_id", "source_files")
        ):
            raise RuntimeError(f"Extractor A2A unexpected payload: {raw[:500]}")
    return data


async def fetch_normalization_via_a2a(patient_id: str) -> dict:
    """Ask the Normalizer agent (:8102) for one patient's NormalizationResult JSON."""
    raw = await send_a2a_text("normalizer", f"Normalize clinical data for {patient_id}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(raw[start : end + 1])
        else:
            raise RuntimeError(f"Normalizer A2A did not return JSON: {exc}") from exc
    if not isinstance(data, dict) or "normalized_extraction" not in data:
        raise RuntimeError(f"Normalizer A2A unexpected payload: {raw[:500]}")
    return data
