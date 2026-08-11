"""Helpers to load configs/rules.yaml and configs/prompts.yaml for MCP Resources/Prompts."""

from __future__ import annotations

from pathlib import Path

import aiofiles
import yaml

from mcp_servers.primary.roots import assert_inside_root, sanitize_patient_id
from shared.rules_config import load_rules  # re-exported for existing imports
from shared.settings import get_path

__all__ = ["load_rules", "load_prompts_config", "find_patient_file", "read_text_file"]


def load_prompts_config() -> dict:
    """Load configs/prompts.yaml (prompt bodies for MCP Prompts)."""
    path = get_path("prompts_yaml")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("prompts", {})


def find_patient_file(folder: Path, patient_id: str) -> Path | None:
    """
    Find the best readable file for a patient under an intake folder.

    Preference order (simple, beginner-friendly, any new patient):
    1. .ocr.txt sidecar (best for scanned PNG/PDF)
    2. .json companion (common for bills)
    3. .txt
    4. .pdf (Harvester can extract text with PyPDF2)
    5. images (.png/.jpg) — Harvester may OCR if enabled
    6. otherwise first matching file

    patient_id is sanitized; every match must stay inside folder
    (Path.relative_to guard — same idea as SSoT §3.8 Roots).
    """
    safe_id = sanitize_patient_id(patient_id)
    folder = folder.resolve()
    if not folder.exists():
        return None

    matches = sorted(folder.glob(f"{safe_id}*"))
    if not matches:
        return None

    # Keep only paths that are still under folder (blocks ../ tricks)
    safe_matches = []
    for path in matches:
        try:
            safe_matches.append(assert_inside_root(path, folder))
        except ValueError:
            continue
    if not safe_matches:
        return None

    def _pick(*predicates):
        for pred in predicates:
            for path in safe_matches:
                if pred(path):
                    return path
        return None

    chosen = _pick(
        lambda p: p.name.endswith(".ocr.txt"),
        lambda p: p.suffix.lower() == ".json",
        lambda p: p.suffix.lower() == ".txt",
        lambda p: p.suffix.lower() == ".pdf",
        lambda p: p.suffix.lower() in {".png", ".jpg", ".jpeg"},
    )
    return chosen or safe_matches[0]


async def read_text_file(path: Path) -> str:
    """Read a text-ish file with aiofiles (coding-style pattern).

    For PDF/PNG binaries, try multi-modal extractors (PDF text / optional OCR)
    so MCP Resources and Harvester stay consistent for new patient files.
    """
    suffix = path.suffix.lower()
    if suffix in {".pdf", ".png", ".jpg", ".jpeg"} and not path.name.endswith(".ocr.txt"):
        from mcp_servers.primary.document_readers import read_binary_document

        text, meta = read_binary_document(path)
        if meta.get("error") and not text.strip():
            return (
                f"[binary file: {path.name} — no text extracted "
                f"({meta.get('error')}); prefer a .ocr.txt or .json companion]"
            )
        return text

    async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
        return await f.read()
