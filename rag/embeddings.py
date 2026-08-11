"""Embeddings helper — sentence-transformers MiniLM (SSoT §10, model_config.yaml).

Beginner picture: one embedding model for the whole RAG stack.
Name comes from configs/model_config.yaml — never hardcode the model id here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from sentence_transformers import SentenceTransformer

from shared.logger import get_logger
from shared.settings import REPO_ROOT, load_agent_config

logger = get_logger("rag_embeddings")


def _embedding_model_name() -> str:
    """Read embeddings.model_name from model_config.yaml (path from agent_config)."""
    cfg = load_agent_config()
    model_cfg_path = REPO_ROOT / cfg.get("paths", {}).get("model_config", "configs/model_config.yaml")
    with open(model_cfg_path, encoding="utf-8") as f:
        model_cfg = yaml.safe_load(f) or {}
    name = (model_cfg.get("embeddings") or {}).get("model_name")
    if not name:
        raise RuntimeError("embeddings.model_name missing from model_config.yaml")
    return str(name)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load MiniLM once (cached). First call may download weights."""
    name = _embedding_model_name()
    logger.info("Loading embedding model: %s", name)
    return SentenceTransformer(name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed many texts → list of float vectors."""
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """Embed one question string."""
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
