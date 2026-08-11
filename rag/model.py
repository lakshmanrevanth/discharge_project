"""Shared Agno model helper — LiteLLM → Bedrock (SSoT §10).

Beginner picture: every Agno agent in rag/ uses the same model id from
model_config.yaml / .env — never hardcode model names in agent files.
"""

from __future__ import annotations

import yaml
from agno.models.litellm import LiteLLM
import litellm

from shared.settings import REPO_ROOT, get_bedrock_config, load_agent_config

# Agno may send tool_choice; Bedrock Nova rejects it unless dropped.
litellm.drop_params = True


def get_agno_model() -> LiteLLM:
    """Build the Agno LiteLLM model from project config."""
    cfg = load_agent_config()
    model_cfg_path = REPO_ROOT / cfg.get("paths", {}).get("model_config", "configs/model_config.yaml")
    with open(model_cfg_path, encoding="utf-8") as f:
        model_cfg = yaml.safe_load(f) or {}
    litellm_id = (
        (model_cfg.get("llm") or {}).get("primary") or {}
    ).get("litellm_model")
    if not litellm_id:
        bedrock = get_bedrock_config()
        litellm_id = f"bedrock/{bedrock['model_id']}"
    max_tokens = get_bedrock_config()["max_tokens"]
    return LiteLLM(id=litellm_id, temperature=0.0, max_tokens=max_tokens)
