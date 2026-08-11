"""Shared A2A auth helper (SSoT §4 — X-Agent-Auth-Token).

One place for every agent's A2A server/middleware to read the shared
secret, instead of each agent re-reading agent_config.yaml + os.environ.
"""

from __future__ import annotations

import os

from shared.settings import load_agent_config


def get_a2a_auth_token() -> str:
    """Shared secret for X-Agent-Auth-Token, read from the env var named in agent_config.yaml."""
    cfg = load_agent_config()
    env_name = cfg.get("a2a", {}).get("auth_token_env", "AGENT_AUTH_TOKEN")
    return os.environ.get(env_name, "change-me-local-dev-token")
