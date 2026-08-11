"""LangFuse observability (SSoT §9) — one Trace, Host Agent root, nested spans.

Beginner picture (Process patient / Host pipeline):
  Trace (discharge_case_id / patient_id)
  └── Host Agent
      ├── Monitor Agent → scan_patients
      ├── Extractor Agent → load_documents / extract_record / …
      ├── Normalizer Agent → normalize_clinical_record / …
      ├── Validator Agent → validate_clinical_record / …
      ├── Final Discharge Summary (Summary Agent)
      └── Workflow Output

HITL Corrections Re-run (validate only — no re-extract):
  Trace
  └── Host Agent
      ├── Validator Agent (mode=hitl_revalidate) → validate_clinical_record / …
      └── Workflow Output

Nested LangFuse observations stay open while children run (no nested traces).
When LANGFUSE_* keys are missing, the same tree is written under
data/reports/traces/{trace_id}.json for local audit.
"""

from __future__ import annotations

import json
import os
import time
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from shared.guardrails.pii_redactor import redact_payload, redact_text
from shared.logger import get_logger
from shared.settings import get_path

logger = get_logger("langfuse")

_current_trace_id: ContextVar[str | None] = ContextVar("case_trace_id", default=None)
# Stack of open local parent names (for JSON tree when cloud client is off).
_local_parent_stack: ContextVar[tuple[str, ...]] = ContextVar(
    "local_parent_stack", default=()
)
_client = None
_client_checked = False

_KIND_AS_TYPE = {
    "agent": "agent",
    "tool": "tool",
    "generation": "generation",
    "guardrail": "guardrail",
    "chain": "chain",
    "retriever": "retriever",
    "span": "span",
    "prompt": "span",
    "sampling": "span",
    "elicitation": "span",
    "error": "span",
    "resource": "span",
}


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def set_current_trace_id(trace_id: str | None):
    """Install (or clear) the case trace id for this async/task context."""
    return _current_trace_id.set(trace_id)


def reset_current_trace_id(token) -> None:
    _current_trace_id.reset(token)


def ensure_trace_id(patient_id: str | None = None, existing: str | None = None) -> str:
    """Return an existing/current/new end-to-end case trace id."""
    if existing:
        return str(existing)
    current = get_current_trace_id()
    if current:
        return current
    return new_trace_id(patient_id)


def new_trace_id(patient_id: str | None = None) -> str:
    """Create a fresh trace id (LangFuse-compatible hex when possible)."""
    client = _get_client()
    if client is not None:
        try:
            tid = client.create_trace_id()
            if tid:
                return str(tid)
        except Exception as exc:
            logger.info("LangFuse create_trace_id failed (%s) — using local uuid", exc)
    suffix = uuid.uuid4().hex
    if patient_id:
        return f"{str(patient_id).upper()}-{suffix}"
    return suffix


def _get_client():
    """Lazy LangFuse client — None when keys are not configured."""
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    public = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not public or not secret:
        logger.info("LangFuse keys not set — using local file traces only")
        _client = None
        return None
    try:
        from langfuse import Langfuse

        host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL")
        kwargs: dict[str, Any] = {"public_key": public, "secret_key": secret}
        if host:
            kwargs["host"] = host
        _client = Langfuse(**kwargs)
        logger.info("LangFuse client ready (host=%s)", host or "default")
    except Exception as exc:
        logger.warning("LangFuse client init failed: %s — local traces only", exc)
        _client = None
    return _client


def _traces_dir() -> Path:
    path = get_path("reports") / "traces"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_payload(value: Any, *, limit: int = 4000) -> Any:
    """Redacted, JSON-friendly, size-capped payload for LangFuse / local file."""
    try:
        text = json.dumps(redact_payload(value), ensure_ascii=False, default=str)
    except Exception:
        text = redact_text(str(value))
    if len(text) > limit:
        return text[:limit] + f"…(+{len(text) - limit} chars)"
    try:
        return json.loads(text)
    except Exception:
        return text


def _append_local(trace_id: str, event: dict) -> None:
    path = _traces_dir() / f"{trace_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"trace_id": trace_id, "events": []}
    else:
        data = {"trace_id": trace_id, "events": []}
    data.setdefault("events", []).append(event)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_type_for(kind: str) -> str:
    return _KIND_AS_TYPE.get(kind, "span")


class SpanHandle:
    """Mutable handle so callers can set output before the context exits."""

    def __init__(self, name: str, trace_id: str):
        self.name = name
        self.trace_id = trace_id
        self.output: Any = None
        self.metadata: dict[str, Any] = {}
        self.error: str | None = None
        self.status: str = "ok"
        self.level: str = "DEFAULT"
        # Optional generation fields
        self.model: str | None = None
        self.usage: dict[str, int] | None = None
        self.cost: dict[str, float] | None = None

    def set_output(self, output: Any) -> None:
        self.output = output

    def fail(self, exc: BaseException, *, fallback: str | None = None) -> None:
        self.status = "error"
        self.level = "ERROR"
        self.error = f"{type(exc).__name__}: {exc}"
        if fallback:
            self.metadata["fallback"] = fallback


@contextmanager
def observation(
    name: str,
    *,
    kind: str = "span",
    input_payload: Any = None,
    metadata: dict | None = None,
    model: str | None = None,
    trace_id: str | None = None,
) -> Iterator[SpanHandle]:
    """Open a nested span under the current Host / agent observation.

    Does NOT create a new Trace — children attach to the active observation.
    """
    tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
    parents = _local_parent_stack.get()
    parent_name = parents[-1] if parents else None
    token = _local_parent_stack.set(parents + (name,))
    handle = SpanHandle(name, tid)
    handle.model = model
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    as_type = _as_type_for(kind)
    meta = {**(metadata or {}), "kind": kind}
    if parent_name:
        meta["parent"] = parent_name
    in_payload = _safe_payload(input_payload)

    client = _get_client()
    obs_cm = None
    obs = None
    try:
        if client is not None:
            kwargs: dict[str, Any] = {
                "as_type": as_type,
                "name": name,
                "input": in_payload,
                "metadata": meta,
            }
            # Only the root Host Agent should set trace_context; children nest
            # via the current OTEL/LangFuse observation context.
            if not parents:
                kwargs["trace_context"] = {"trace_id": tid}
            if kind == "generation" and model:
                kwargs["model"] = model
            obs_cm = client.start_as_current_observation(**kwargs)
            obs = obs_cm.__enter__()

        try:
            yield handle
        except Exception as exc:
            handle.fail(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            out_payload = _safe_payload(handle.output)
            event = {
                "name": name,
                "kind": kind,
                "as_type": as_type,
                "parent": parent_name,
                "level": handle.level,
                "status": handle.status,
                "error": handle.error,
                "duration_ms": round(duration_ms, 2),
                "started_at": started_at,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "input": in_payload,
                "output": out_payload,
                "metadata": {**meta, **handle.metadata},
                "model": handle.model,
                "usage": handle.usage,
                "cost": handle.cost,
            }
            _append_local(tid, event)

            if obs is not None:
                try:
                    update: dict[str, Any] = {
                        "output": out_payload,
                        "metadata": {**meta, **handle.metadata, "duration_ms": duration_ms},
                    }
                    if handle.error:
                        update["level"] = "ERROR"
                        update["status_message"] = handle.error
                    if handle.model:
                        update["model"] = handle.model
                    if handle.usage:
                        update["usage_details"] = handle.usage
                    if handle.cost:
                        update["cost_details"] = handle.cost
                    obs.update(**update)
                except Exception as exc:
                    logger.info("LangFuse update '%s' skipped: %s", name, exc)
    finally:
        if obs_cm is not None:
            try:
                obs_cm.__exit__(None, None, None)
            except Exception as exc:
                logger.info("LangFuse close '%s' skipped: %s", name, exc)
        _local_parent_stack.reset(token)


@contextmanager
def case_trace(
    patient_id: str,
    *,
    existing: str | None = None,
    host_name: str = "Host Agent",
) -> Iterator[str]:
    """One Trace per discharge case with Host Agent as the root parent span."""
    tid = ensure_trace_id(patient_id, existing)
    token = set_current_trace_id(tid)
    # Seed local file header
    _append_local(
        tid,
        {
            "name": "trace.start",
            "kind": "trace",
            "status": "ok",
            "input": {"patient_id": patient_id, "discharge_case_id": tid},
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        with observation(
            host_name,
            kind="agent",
            input_payload={"patient_id": patient_id, "discharge_case_id": tid},
            metadata={"patient_id": patient_id, "role": "host"},
            trace_id=tid,
        ) as host:
            host.set_output({"patient_id": patient_id, "trace_id": tid})
            yield tid
    finally:
        flush()
        reset_current_trace_id(token)


def trace_id_from_metadata(*sources: Any) -> str | None:
    """Pull the propagated case ``trace_id`` out of A2A message metadata.

    Callers pass any mix of dicts / pydantic models / None (message metadata,
    task metadata, …); the first usable ``trace_id`` wins. Without this the
    worker process starts a fresh trace and its spans land in a *different*
    LangFuse trace than the Host — which is what makes a stamped trace URL
    open an empty (perpetually loading) page.
    """
    for source in sources:
        if source is None:
            continue
        meta = source
        if not isinstance(meta, dict):
            meta = getattr(source, "metadata", None)
        if not isinstance(meta, dict):
            continue
        tid = meta.get("trace_id") or meta.get("traceId")
        if tid:
            return str(tid)
    return None


def start_case_trace(patient_id: str, *, existing: str | None = None) -> str:
    """Set the case trace id without opening a lasting Host span.

    Prefer ``case_trace(...)`` for full hierarchy. Kept for callers that only
    need to adopt/propagate an id (A2A workers).
    """
    tid = ensure_trace_id(patient_id, existing)
    set_current_trace_id(tid)
    return tid


def record_span(
    name: str,
    *,
    kind: str = "span",
    input_payload: Any = None,
    output_payload: Any = None,
    metadata: dict | None = None,
    level: str = "DEFAULT",
    status: str = "ok",
    error: str | None = None,
    duration_ms: float | None = None,
    trace_id: str | None = None,
    model: str | None = None,
    usage: dict | None = None,
    cost: dict | None = None,
) -> str:
    """Record one leaf span nested under the current open observation."""
    with observation(
        name,
        kind=kind,
        input_payload=input_payload,
        metadata=metadata,
        model=model,
        trace_id=trace_id,
    ) as handle:
        handle.output = output_payload
        handle.level = level
        handle.status = status
        handle.error = error
        if usage:
            handle.usage = usage
        if cost:
            handle.cost = cost
        if duration_ms is not None:
            handle.metadata["reported_duration_ms"] = duration_ms
    return ensure_trace_id(existing=trace_id or get_current_trace_id())


@contextmanager
def span(
    name: str,
    *,
    kind: str = "span",
    input_payload: Any = None,
    metadata: dict | None = None,
    trace_id: str | None = None,
) -> Iterator[SpanHandle]:
    """Timed nested span (alias of observation)."""
    with observation(
        name,
        kind=kind,
        input_payload=input_payload,
        metadata=metadata,
        trace_id=trace_id,
    ) as handle:
        yield handle


def record_generation(
    name: str,
    *,
    model: str,
    prompt: Any,
    completion: Any,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost: float | None = None,
    duration_ms: float | None = None,
    metadata: dict | None = None,
) -> None:
    """LLM generation leaf under the current agent / extract_record span."""
    usage: dict[str, int] = {}
    if input_tokens is not None:
        usage["input"] = int(input_tokens)
    if output_tokens is not None:
        usage["output"] = int(output_tokens)
    if total_tokens is not None:
        usage["total"] = int(total_tokens)
    elif usage:
        usage["total"] = int(usage.get("input", 0)) + int(usage.get("output", 0))
    cost = {"total": float(estimated_cost)} if estimated_cost is not None else None
    record_span(
        name,
        kind="generation",
        input_payload={"prompt": prompt},
        output_payload={"completion": completion},
        metadata=metadata,
        model=model,
        usage=usage or None,
        cost=cost,
        duration_ms=duration_ms,
    )


def record_guardrail(
    name: str,
    result: str,
    *,
    blocked: bool = False,
    detail: str = "",
    reason: str = "",
) -> None:
    record_span(
        "Guardrail",
        kind="guardrail",
        input_payload={"guardrail": name, "detail": detail, "reason": reason},
        output_payload={
            "guardrail": name,
            "result": result,
            "blocked": blocked,
            "allowed": not blocked,
            "reason": reason or detail,
        },
        metadata={"guardrail": name},
        status="blocked" if blocked else "ok",
    )


def record_sampling(
    *,
    server_preferences: Any,
    client_model: str,
    translation_result: Any = None,
    metadata: dict | None = None,
) -> None:
    record_span(
        "Sampling Events",
        kind="sampling",
        input_payload={"server_model_preferences": server_preferences},
        output_payload={
            "client_selected_model": client_model,
            "translation_result": translation_result,
        },
        metadata=metadata,
    )


def record_translation(
    *,
    source_language: str | None,
    result: Any,
    metadata: dict | None = None,
) -> None:
    record_span(
        "Translation Events",
        kind="sampling",
        input_payload={"source_language": source_language},
        output_payload={"translation_result": result},
        metadata=metadata,
    )


def record_elicitation(
    *,
    schema: Any,
    reviewer_response: Any,
    action: str,
    metadata: dict | None = None,
) -> None:
    record_span(
        "Elicitation",
        kind="elicitation",
        input_payload={"schema": schema},
        output_payload={"reviewer_response": reviewer_response, "action": action},
        metadata={**(metadata or {}), "action": action},
    )


def record_error(
    name: str,
    exc: BaseException,
    *,
    fallback: str | None = None,
) -> None:
    record_span(
        name if name.startswith("Errors") else f"Errors · {name}",
        kind="error",
        input_payload={"exception_type": type(exc).__name__},
        output_payload={
            "error_message": str(exc),
            "stack_trace": traceback.format_exc(),
            "fallback_action": fallback,
        },
        error=f"{type(exc).__name__}: {exc}",
        status="error",
        level="ERROR",
    )


def record_mcp_tool(
    tool_name: str,
    *,
    params: Any,
    result: Any,
    duration_ms: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Record one MCP tool invocation (span name = SSoT tool id)."""
    record_span(
        tool_name,
        kind="tool",
        input_payload={"tool": tool_name, "parameters": params},
        output_payload={"result": result, "success": success},
        metadata={
            "tool_name": tool_name,
            "mcp_tool": True,
            "latency_ms": duration_ms,
        },
        status="ok" if success else "error",
        error=error,
        duration_ms=duration_ms,
    )


def flush() -> None:
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:
            logger.info("LangFuse flush skipped: %s", exc)


def trace_url(trace_id: str | None) -> str | None:
    """Public LangFuse URL when a remote client is configured.

    Returns None for file-only tracing. We never guess a URL shape: LangFuse
    trace pages live under /project/{project_id}/traces/{id}, so a host-only
    guess (/trace/{id}) resolves to a page that just spins forever.
    """
    if not trace_id:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        url = client.get_trace_url(trace_id=trace_id)
    except Exception as exc:
        logger.info("LangFuse trace_url failed for %s: %s", trace_id, exc)
        return None
    return str(url) if url else None
