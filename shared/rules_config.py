"""Load configs/rules.yaml (SSoT §6 — single source of truth for validation).

Lives in shared/ (not mcp_servers/primary/) so BOTH the Primary MCP tools
and the Secondary MCP tools can read rules.yaml without importing each
other's package. One loader, one file read, used everywhere.
"""

from __future__ import annotations

import hashlib

import yaml

from shared.settings import get_path


def load_rules() -> dict:
    """Load runtime configs/rules.yaml as a plain dict."""
    path = get_path("rules_yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_rules_version() -> str:
    """SHA-256 of rules.yaml's raw bytes (SSoT §6 — every report stamps this)."""
    path = get_path("rules_yaml")
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
