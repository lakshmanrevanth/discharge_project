"""LiteLLM wrapper for Nova Lite / Command R+ (Normalizer sampling_callback).

SSoT §3.6 / §10: client owns LLM calls. Routes by ModelPreferences hints
from the Medical Lang Bridge Sampling request.
"""

from __future__ import annotations

import os

import litellm

from mcp_servers.primary.sampling import load_model_config
from shared.logger import get_logger
from shared.settings import get_bedrock_config

logger = get_logger("llm")

# LiteLLM needs AWS creds from the environment (.env already loaded in settings).
litellm.drop_params = True


def resolve_litellm_model(hint_names: list[str]) -> str:
    """Pick a LiteLLM model id from Sampling ModelPreferences hints.

    nova-lite (multilingual) → Bedrock Nova Lite
    command-r-plus (English) → Bedrock Cohere Command R+ when AWS is configured,
      else direct Cohere if COHERE_API_KEY is set.
    """
    cfg = load_model_config().get("llm", {})
    names = [h.lower() for h in hint_names]

    wants_command_r = any("command-r" in n or "command_r" in n for n in names)
    if wants_command_r:
        # Prefer Bedrock-hosted Command R+ (matches lab .env BEDROCK_FALLBACK_MODEL_ID)
        bedrock_id = os.environ.get("BEDROCK_FALLBACK_MODEL_ID", "").strip()
        if bedrock_id:
            return bedrock_id if "/" in bedrock_id else f"bedrock/{bedrock_id}"
        fallback = cfg.get("fallback", {})
        litellm_id = fallback.get("litellm_model")
        if litellm_id and litellm_id.startswith("bedrock/"):
            return litellm_id
        # Direct Cohere only when an API key is present
        if os.environ.get("COHERE_API_KEY") and litellm_id:
            return litellm_id
        if os.environ.get("COHERE_API_KEY"):
            return "cohere/command-r-plus"
        # Last resort: Bedrock Cohere id from company docs
        return "bedrock/cohere.command-r-plus-v1:0"

    primary = cfg.get("primary", {})
    litellm_id = primary.get("litellm_model")
    if litellm_id:
        return litellm_id
    bedrock = get_bedrock_config()
    return f"bedrock/{bedrock['model_id']}"


def run_completion(
    *,
    messages: list[dict],
    hint_names: list[str],
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> tuple[str, str]:
    """Call LiteLLM. Returns (reply_text, model_id_used)."""
    model = resolve_litellm_model(hint_names)
    tokens = max_tokens or get_bedrock_config()["max_tokens"]
    logger.info("LiteLLM completion model=%s hints=%s", model, hint_names)

    response = litellm.completion(
        model=model,
        messages=messages,
        max_tokens=tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content or ""
    return text, model


async def arun_completion(
    *,
    messages: list[dict],
    hint_names: list[str],
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> tuple[str, str]:
    """Async LiteLLM completion. Returns (reply_text, model_id_used)."""
    model = resolve_litellm_model(hint_names)
    tokens = max_tokens or get_bedrock_config()["max_tokens"]
    logger.info("LiteLLM acompletion model=%s hints=%s", model, hint_names)

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        max_tokens=tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content or ""
    return text, model
