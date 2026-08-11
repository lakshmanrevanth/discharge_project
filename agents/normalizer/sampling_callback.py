"""MCP Sampling callback for the Clinical Normalizer (SSoT §3.6).

Lives on the *client* (Normalizer), not on the MCP server.
Reads ModelPreferences hints from the Medical Lang Bridge:
  - command-r-plus → English (primary)
  - nova-lite → other primary langs + fallback / auto
Routes to LiteLLM and returns CreateMessageResult.
"""

from __future__ import annotations

from mcp.types import CreateMessageResult, SamplingMessage, TextContent

from mcp_servers.primary.sampling import hint_names
from shared.llm import arun_completion
from shared.logger import get_logger

logger = get_logger("sampling_callback")


def _message_to_dict(message: SamplingMessage) -> dict:
    """Turn one MCP SamplingMessage into an OpenAI-style chat message dict."""
    role = message.role or "user"
    content = message.content
    text = getattr(content, "text", None)
    if text is None:
        text = str(content)
    return {"role": role, "content": text}


async def sampling_callback(messages, params, context) -> CreateMessageResult:
    """FastMCP ClientSamplingHandler — called when the server samples.

    Args match fastmcp.client.sampling.ClientSamplingHandler:
      messages: list[SamplingMessage]
      params: CreateMessageRequestParams (systemPrompt, modelPreferences, maxTokens, …)
      context: RequestContext (unused here)
    """
    del context  # not needed for Phase 5
    hints = hint_names(getattr(params, "modelPreferences", None))
    max_tokens = getattr(params, "maxTokens", None) or 1500
    temperature = getattr(params, "temperature", None)
    if temperature is None:
        temperature = 0.0

    chat_messages: list[dict] = []
    system_prompt = getattr(params, "systemPrompt", None)
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    for msg in messages or []:
        chat_messages.append(_message_to_dict(msg))

    logger.info("sampling_callback hints=%s messages=%s", hints, len(chat_messages))
    text, model_used = await arun_completion(
        messages=chat_messages,
        hint_names=hints or ["nova-lite"],
        max_tokens=int(max_tokens),
        temperature=float(temperature),
    )

    try:
        from shared.tracing.langfuse import record_sampling

        prefs = getattr(params, "modelPreferences", None)
        record_sampling(
            server_preferences={
                "hints": hints,
                "raw": str(prefs)[:500] if prefs is not None else None,
            },
            client_model=model_used,
            translation_result={"chars": len(text), "preview": text[:400]},
            metadata={"agent": "Normalizer Agent"},
        )
    except Exception as exc:
        logger.info("Sampling trace skipped: %s", exc)

    return CreateMessageResult(
        role="assistant",
        model=model_used,
        content=TextContent(type="text", text=text),
        stopReason="endTurn",
    )
