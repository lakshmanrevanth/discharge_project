"""LangFuse observability (SSoT §9).

Beginner picture:
  - One end-to-end trace_id per discharge case.
  - Spans for agents, tools, LLM, sampling, elicitation, guardrails, errors.
  - When LANGFUSE_* keys are set, events go to LangFuse cloud/self-host.
  - When keys are missing, we still create a local trace id + JSON file under
    data/reports/traces/ so audit reports always have a real trace_id.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.logger import get_logger
from shared.settings import get_path

logger = get_logger("langfuse")

_current_trace_id: ContextVar[str | None] = ContextVar("case_trace_id", default=None)
_client = None
_client_checked = False


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


def start_case_trace(patient_id: str, *, existing: str | None = None) -> str:
    """Start (or resume) the end-to-end discharge-case trace. Returns trace_id."""
    tid = ensure_trace_id(patient_id, existing)
    set_current_trace_id(tid)
    record_span(
        "case.start",
        kind="agent",
        input_payload={"patient_id": patient_id},
        metadata={"patient_id": patient_id},
        trace_id=tid,
    )
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
) -> str:
    """Record one observability span/event (agent/tool/llm/sampling/…)."""
    tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
    event = {
        "name": name,
        "kind": kind,
        "level": level,
        "status": status,
        "error": error,
        "duration_ms": duration_ms,
        "input": input_payload,
        "output": output_payload,
        "metadata": metadata or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _append_local(tid, event)

    client = _get_client()
    if client is not None:
        try:
            with client.start_as_current_observation(
                as_type="span" if kind != "generation" else "generation",
                name=name,
                trace_context={"trace_id": tid},
                input=input_payload,
                metadata={**(metadata or {}), "kind": kind, "status": status},
            ) as obs:
                if output_payload is not None:
                    obs.update(output=output_payload)
                if error:
                    obs.update(level="ERROR", status_message=error)
        except Exception as exc:
            logger.info("LangFuse span '%s' skipped: %s", name, exc)
    return tid


@contextmanager
def span(
    name: str,
    *,
    kind: str = "span",
    input_payload: Any = None,
    metadata: dict | None = None,
    trace_id: str | None = None,
):
    """Context manager that times a span and records success/error."""
    tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
    started = time.perf_counter()
    try:
        yield tid
    except Exception as exc:
        record_span(
            name,
            kind=kind,
            input_payload=input_payload,
            metadata=metadata,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
            trace_id=tid,
        )
        raise
    else:
        record_span(
            name,
            kind=kind,
            input_payload=input_payload,
            metadata=metadata,
            status="ok",
            duration_ms=(time.perf_counter() - started) * 1000,
            trace_id=tid,
        )


def record_guardrail(name: str, result: str, *, blocked: bool = False, detail: str = "") -> None:
    record_span(
        f"guardrail.{name}",
        kind="guardrail",
        input_payload={"detail": detail},
        output_payload={"result": result, "blocked": blocked},
        metadata={"guardrail": name},
        status="blocked" if blocked else "ok",
    )


def record_error(name: str, exc: BaseException, *, fallback: str | None = None) -> None:
    record_span(
        name,
        kind="error",
        output_payload={"fallback": fallback},
        error=f"{type(exc).__name__}: {exc}",
        status="error",
        level="ERROR",
    )


def flush() -> None:
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:
            logger.info("LangFuse flush skipped: %s", exc)


def trace_url(trace_id: str | None) -> str | None:
    """Public LangFuse URL when a remote client is configured."""
    if not trace_id:
        return None
    client = _get_client()
    if client is None:
        host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
        if host:
            return f"{host}/trace/{trace_id}"
        return None
    try:
        url = client.get_trace_url(trace_id=trace_id)
        return url
    except Exception:
        host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
        return f"{host}/trace/{trace_id}" if host else None
