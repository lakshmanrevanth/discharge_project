"""Streaming-capable A2A client for the Host Orchestrator (SSoT §5.8, §4).

Discovers AgentCards from configs/agent_config.yaml service URLs, then sends
messages with send_message (non-streaming) or send_message_streaming when the
card advertises streaming=True (Summary :8104, RAG :8105).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)

from shared.a2a_auth import get_a2a_auth_token
from shared.logger import get_logger
from shared.settings import get_service, load_agent_config

logger = get_logger("host_a2a")

# A2A agent services the Host may coordinate (SSoT §2 / architecture).
A2A_SERVICE_KEYS: tuple[str, ...] = (
    "monitor",
    "extractor",
    "normalizer",
    "validator",
    "summary",
    "rag",
)


@dataclass
class RemoteAgent:
    """One discovered remote A2A agent."""

    service_key: str
    name: str
    url: str
    description: str = ""
    streaming: bool = False
    card: AgentCard | None = None
    error: str | None = None


@dataclass
class HostA2AClient:
    """Caches AgentCards and sends A2A messages (streaming-capable)."""

    agents_by_key: dict[str, RemoteAgent] = field(default_factory=dict)
    agents_by_name: dict[str, RemoteAgent] = field(default_factory=dict)

    def _headers(self) -> dict[str, str]:
        cfg = load_agent_config()
        header_name = cfg.get("a2a", {}).get("auth_header", "X-Agent-Auth-Token")
        return {header_name: get_a2a_auth_token()}

    def _base_url(self, service_key: str) -> str:
        svc = get_service(service_key)
        return f"http://{svc.get('host', '127.0.0.1')}:{int(svc.get('port'))}"

    async def discover(self) -> list[RemoteAgent]:
        """Fetch AgentCards for every A2A service. Offline agents get an error note."""
        self.agents_by_key.clear()
        self.agents_by_name.clear()
        found: list[RemoteAgent] = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers=self._headers(),
        ) as httpx_client:
            for key in A2A_SERVICE_KEYS:
                url = self._base_url(key)
                remote = RemoteAgent(service_key=key, name=key, url=url)
                try:
                    resolver = A2ACardResolver(
                        httpx_client=httpx_client,
                        base_url=url,
                        agent_card_path="/.well-known/agent.json",
                    )
                    card = await resolver.get_agent_card()
                    remote.card = card
                    remote.name = card.name
                    remote.description = card.description or ""
                    caps = card.capabilities
                    remote.streaming = bool(getattr(caps, "streaming", False))
                    logger.info("Discovered %s at %s (streaming=%s)", remote.name, url, remote.streaming)
                except Exception as exc:
                    remote.error = str(exc)
                    logger.info("Agent %s unavailable at %s: %s", key, url, exc)

                self.agents_by_key[key] = remote
                self.agents_by_name[remote.name.lower()] = remote
                # Also index by service key for tools
                self.agents_by_name[key.lower()] = remote
                found.append(remote)

        return found

    def resolve(self, agent_name: str) -> RemoteAgent:
        """Look up by AgentCard name or service key (case-insensitive)."""
        key = (agent_name or "").strip().lower()
        if key in self.agents_by_name:
            return self.agents_by_name[key]
        # Fuzzy: substring match on card name
        for name, remote in self.agents_by_name.items():
            if key and key in name:
                return remote
        raise ValueError(
            f"Unknown agent '{agent_name}'. Call list_remote_agents / discover first. "
            f"Known: {sorted(set(self.agents_by_key))}"
        )

    def list_info(self) -> list[dict[str, Any]]:
        """JSON-serializable agent list for the ADK tool / Gradio panel."""
        rows = []
        for key in A2A_SERVICE_KEYS:
            remote = self.agents_by_key.get(key)
            if not remote:
                rows.append({"service_key": key, "status": "not_discovered"})
                continue
            rows.append(
                {
                    "service_key": remote.service_key,
                    "name": remote.name,
                    "url": remote.url,
                    "streaming": remote.streaming,
                    "description": remote.description[:200],
                    "status": "error" if remote.error else "ok",
                    "error": remote.error,
                }
            )
        return rows

    @staticmethod
    def _artifact_text(task: Task) -> str:
        artifacts = task.artifacts or []
        chunks: list[str] = []
        for art in artifacts:
            for part in art.parts or []:
                root = getattr(part, "root", part)
                text = getattr(root, "text", None)
                if text:
                    chunks.append(text)
        return "\n".join(chunks)

    @staticmethod
    def _event_text(event: Any) -> str | None:
        """Pull text from a streaming SSE event (artifact or status message)."""
        root = getattr(event, "root", event)
        result = getattr(root, "result", root)

        if isinstance(result, TaskArtifactUpdateEvent):
            art = result.artifact
            parts = getattr(art, "parts", None) or []
            bits = []
            for part in parts:
                r = getattr(part, "root", part)
                t = getattr(r, "text", None)
                if t:
                    bits.append(t)
            return "\n".join(bits) if bits else None

        if isinstance(result, TaskStatusUpdateEvent):
            msg = getattr(result.status, "message", None)
            if msg and getattr(msg, "parts", None):
                bits = []
                for part in msg.parts:
                    r = getattr(part, "root", part)
                    t = getattr(r, "text", None)
                    if t:
                        bits.append(t)
                return "\n".join(bits) if bits else None
            return None

        if isinstance(result, Task):
            return HostA2AClient._artifact_text(result)

        return None

    async def send_message(
        self,
        agent_name: str,
        message_text: str,
        timeout: float = 300.0,
        *,
        trace_id: str | None = None,
    ) -> str:
        """Non-streaming A2A send_message → concatenated artifact text."""
        from shared.tracing.langfuse import ensure_trace_id, get_current_trace_id, record_span

        tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
        if not self.agents_by_key:
            await self.discover()
        remote = self.resolve(agent_name)
        if remote.error and remote.card is None:
            raise RuntimeError(f"Agent '{agent_name}' is offline: {remote.error}")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._headers(),
        ) as httpx_client:
            client = A2AClient(httpx_client, remote.card, url=remote.url)
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
            logger.info("A2A send_message → %s (%s) trace=%s", remote.name, remote.url, tid)
            response = await client.send_message(request)

        root = response.root
        if not isinstance(root, SendMessageSuccessResponse):
            raise RuntimeError(f"A2A {remote.name} non-success: {response}")
        result = root.result
        if not isinstance(result, Task):
            raise RuntimeError(f"A2A {remote.name} expected Task, got {type(result)}")
        text = self._artifact_text(result)
        record_span(
            f"a2a.{remote.service_key}",
            kind="agent",
            input_payload={"preview": (message_text or "")[:200]},
            output_payload={"chars": len(text or "")},
            metadata={"agent": remote.name, "trace_id": tid},
            trace_id=tid,
        )
        return text or "(empty artifact)"

    async def send_message_streaming(
        self,
        agent_name: str,
        message_text: str,
        timeout: float = 300.0,
        *,
        trace_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Streaming A2A send_message_streaming — yields text chunks as they arrive."""
        from shared.tracing.langfuse import ensure_trace_id, get_current_trace_id

        tid = ensure_trace_id(existing=trace_id or get_current_trace_id())
        if not self.agents_by_key:
            await self.discover()
        remote = self.resolve(agent_name)
        if remote.error and remote.card is None:
            raise RuntimeError(f"Agent '{agent_name}' is offline: {remote.error}")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._headers(),
        ) as httpx_client:
            client = A2AClient(httpx_client, remote.card, url=remote.url)
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
            request = SendStreamingMessageRequest(
                id=message_id,
                params=MessageSendParams.model_validate(payload),
            )
            logger.info(
                "A2A send_message_streaming → %s (%s) trace=%s",
                remote.name,
                remote.url,
                tid,
            )
            async for event in client.send_message_streaming(request):
                text = self._event_text(event)
                if text:
                    yield text

    async def send_auto(self, agent_name: str, message_text: str) -> str:
        """Use streaming when the AgentCard supports it; else non-streaming."""
        if not self.agents_by_key:
            await self.discover()
        remote = self.resolve(agent_name)
        if remote.streaming:
            parts: list[str] = []
            async for chunk in self.send_message_streaming(agent_name, message_text):
                parts.append(chunk)
            return "\n".join(parts) if parts else "(empty stream)"
        return await self.send_message(agent_name, message_text)


# Module-level singleton used by ADK tools + Gradio.
_client: HostA2AClient | None = None


def get_host_client() -> HostA2AClient:
    global _client
    if _client is None:
        _client = HostA2AClient()
    return _client


def try_parse_json(text: str) -> dict | None:
    """Best-effort JSON object extract from an A2A artifact."""
    raw = (text or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
