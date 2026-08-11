"""Load configs/agent_config.yaml so ports and paths are not hardcoded.

Phase 1: enough for Mock EHR. Later phases can reuse the same helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Repo root = parent of the shared/ package
REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG_PATH = REPO_ROOT / "configs" / "agent_config.yaml"

# Load .env once so every agent/tool sees AWS/LangFuse/auth vars without
# each entrypoint calling load_dotenv() itself.
load_dotenv(REPO_ROOT / ".env")

# Strip CR/whitespace from env values (Windows CRLF .env files otherwise
# poison Bedrock region/model ids and break live LLM calls).
for _k, _v in list(os.environ.items()):
    if _v and ("\r" in _v or _v != _v.strip()):
        os.environ[_k] = _v.replace("\r", "").strip()

# Cache so we do not re-read the YAML on every call
_config: dict | None = None


def load_agent_config() -> dict:
    """Read and return agent_config.yaml as a plain dict."""
    global _config
    if _config is None:
        with open(AGENT_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def get_service(name: str) -> dict:
    """Return one service block, e.g. get_service('mock_ehr').

    Host in YAML is the *client* address (usually 127.0.0.1). Use
    ``listen_host()`` when binding a server socket (NuvePro may set
    BIND_HOST=0.0.0.0).
    """
    services = load_agent_config().get("services", {})
    if name not in services:
        raise KeyError(f"Unknown service in agent_config.yaml: {name}")
    return services[name]


def listen_host(service_host: str | None = None) -> str:
    """Host to bind servers on.

    Prefer BIND_HOST from the environment (NuvePro / cloud labs often need
    ``0.0.0.0``). Otherwise use the YAML service host.
    """
    bind = (os.environ.get("BIND_HOST") or "").strip()
    if bind:
        return bind
    return (service_host or "127.0.0.1").strip() or "127.0.0.1"


def get_path(key: str) -> Path:
    """Return an absolute path from the paths: section (relative to repo root)."""
    paths = load_agent_config().get("paths", {})
    if key not in paths:
        raise KeyError(f"Unknown path key in agent_config.yaml: {key}")
    return REPO_ROOT / paths[key]


def get_bedrock_config() -> dict:
    """AWS Bedrock model settings (SSoT §10 — Nova Lite primary via LiteLLM/langchain-aws).

    Read from environment (.env) — never hardcode keys/model ids elsewhere.
    """
    return {
        "model_id": os.environ.get("BEDROCK_PRIMARY_MODEL_ID", "amazon.nova-lite-v1:0"),
        "region_name": os.environ.get("AWS_REGION_NAME") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        # Discharge structured extraction needs headroom; 500 truncates meds/tables.
        "max_tokens": int(os.environ.get("BEDROCK_MAX_TOKENS", "4096")),
    }
