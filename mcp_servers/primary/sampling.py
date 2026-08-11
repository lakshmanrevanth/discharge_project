"""Sampling helpers for Medical Lang Bridge (SSoT §3.6).

Beginner picture — which model hint to ask for:
  - English (primary) → command-r-plus
  - Other primary langs (es/hi/de/fr/nl) → nova-lite
  - Fallback / auto / unknown / brand-new lang → also nova-lite

The tool calls ctx.session.create_message(); the Normalizer's sampling_callback
runs the actual LiteLLM inference.
"""

from __future__ import annotations

import yaml
from mcp.types import ModelHint, ModelPreferences

from shared.language import needs_multilingual_model
from shared.settings import REPO_ROOT


def load_model_config() -> dict:
    """Load configs/model_config.yaml (sampling hints + litellm model ids)."""
    path = REPO_ROOT / "configs" / "model_config.yaml"
    try:
        from shared.settings import get_path

        path = get_path("model_config")
    except KeyError:
        pass
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_model_preferences(source_language: str) -> ModelPreferences:
    """SSoT §3.6 — nova-lite for multilingual/auto; command-r-plus for English."""
    cfg = load_model_config().get("sampling", {})
    if needs_multilingual_model(source_language):
        hint_name = cfg.get("multilingual_hint", "nova-lite")
    else:
        hint_name = cfg.get("english_hint", "command-r-plus")
    return ModelPreferences(
        hints=[ModelHint(name=hint_name)],
        intelligencePriority=0.8,
        speedPriority=0.4,
        costPriority=0.3,
    )


def hint_names(preferences: ModelPreferences | None) -> list[str]:
    """Extract hint name strings from ModelPreferences (for the client callback)."""
    if preferences is None or not preferences.hints:
        return []
    names = []
    for hint in preferences.hints:
        name = getattr(hint, "name", None)
        if name:
            names.append(str(name))
    return names
