"""FAISS vector store helpers (SSoT §5.6).

Beginner picture:
  - One FAISS folder per patient_id under data/vector_db/{patient_id}/
  - Works for ANY patient (P001, P1019, P2001, …) — not locked to the sample corpus
  - meta.json holds chunk text + source paths alongside the FAISS index

Paths and top_k come from agent_config.yaml — nothing hardcoded.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from rag.embeddings import embed_query, embed_texts
from shared.logger import get_logger
from shared.settings import get_path, get_service

logger = get_logger("rag_vectorstore")


def _rag_cfg() -> dict:
    return get_service("rag")


def _patient_dir(patient_id: str) -> Path:
    """Absolute folder for one patient's FAISS index."""
    base = get_path("vector_db")
    safe_id = str(patient_id).strip().upper()
    folder = base / safe_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _index_path(patient_id: str) -> Path:
    return _patient_dir(patient_id) / "index.faiss"


def _meta_path(patient_id: str) -> Path:
    return _patient_dir(patient_id) / "meta.json"


def patient_is_indexed(patient_id: str) -> bool:
    """True when this patient already has a FAISS index on disk."""
    return _index_path(patient_id).is_file() and _meta_path(patient_id).is_file()


def clear_patient_index(patient_id: str) -> None:
    """Remove FAISS + meta for one patient (stale or empty intake)."""
    for path in (_index_path(patient_id), _meta_path(patient_id)):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", path, exc)


def indexed_source_paths(patient_id: str) -> set[str]:
    """Source paths recorded in meta.json (empty if missing/corrupt)."""
    path = _meta_path(patient_id)
    if not path.is_file():
        return set()
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(row.get("source_path") or "") for row in meta if isinstance(row, dict)}


def save_patient_index(patient_id: str, chunks: list[dict]) -> int:
    """Build + save a FAISS index for one patient from chunk dicts.

    Each chunk: {"text": str, "source_path": str, "doc_type": str}
    Returns number of chunks indexed.
    """
    texts = [c["text"] for c in chunks if (c.get("text") or "").strip()]
    if not texts:
        logger.warning("No text chunks to index for %s", patient_id)
        return 0

    vectors = embed_texts(texts)
    matrix = np.array(vectors, dtype=np.float32)
    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)  # cosine-like (vectors are normalized)
    index.add(matrix)

    faiss.write_index(index, str(_index_path(patient_id)))
    meta = [
        {
            "text": c["text"],
            "source_path": c.get("source_path", ""),
            "doc_type": c.get("doc_type", ""),
            "patient_id": str(patient_id).upper(),
        }
        for c in chunks
        if (c.get("text") or "").strip()
    ]
    _meta_path(patient_id).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Indexed %s chunk(s) for patient %s", len(meta), patient_id)
    return len(meta)


def search_patient(patient_id: str, question: str, k: int | None = None) -> list[dict]:
    """Return top-k chunks for this patient_id (empty list if not indexed)."""
    if not patient_is_indexed(patient_id):
        return []

    top_k = int(k if k is not None else _rag_cfg().get("top_k", 4))
    index = faiss.read_index(str(_index_path(patient_id)))
    meta = json.loads(_meta_path(patient_id).read_text(encoding="utf-8"))
    if not meta:
        return []

    query_vec = np.array([embed_query(question)], dtype=np.float32)
    scores, idxs = index.search(query_vec, min(top_k, len(meta)))

    hits: list[dict] = []
    for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
        if idx < 0 or idx >= len(meta):
            continue
        row = dict(meta[idx])
        row["score"] = float(score)
        hits.append(row)
    return hits
