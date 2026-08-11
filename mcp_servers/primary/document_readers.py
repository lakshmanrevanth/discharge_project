"""Simple multi-modal document readers for the Clinical Data Harvester.

SSoT §10 / §13: prefer OCR sidecars when present; Tesseract is optional;
PDF text via PyPDF2 (company pin pypdf2==3.0.1).

Kept beginner-friendly — plain functions, no heavy abstractions.
Works for any new patient file under data/input/, not only the sample set.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from shared.logger import get_logger

logger = get_logger("document_readers")

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def tesseract_enabled() -> bool:
    """OCR is optional (SSoT §10). Opt in with TESSERACT_ENABLED=true."""
    return os.environ.get("TESSERACT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def read_pdf_text(path: Path) -> str:
    """Extract text from a PDF with PyPDF2. Returns empty string if none found."""
    from PyPDF2 import PdfReader  # local import — only when needed

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    logger.info("PDF extract %s -> %s char(s)", path.name, len(text))
    return text


def read_image_ocr(path: Path) -> str | None:
    """Run Tesseract CLI on an image when enabled and installed.

    Returns None when OCR is disabled / unavailable (caller should fall back).
    """
    if not tesseract_enabled():
        return None
    if shutil.which("tesseract") is None:
        logger.warning("TESSERACT_ENABLED but 'tesseract' binary not found on PATH")
        return None

    # tesseract <image> stdout  → prints text to stdout
    completed = subprocess.run(
        ["tesseract", str(path), "stdout"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        logger.warning("tesseract failed for %s: %s", path.name, completed.stderr.strip())
        return None
    text = (completed.stdout or "").strip()
    logger.info("OCR extract %s -> %s char(s)", path.name, len(text))
    return text or None


def read_binary_document(path: Path) -> tuple[str, dict]:
    """Read a PDF/image into text.

    Returns (text, meta) where meta may include:
      ocr_used, pdf_used, error
    """
    suffix = path.suffix.lower()
    meta: dict = {"ocr_used": False, "pdf_used": False}

    if suffix == ".pdf":
        text = read_pdf_text(path)
        meta["pdf_used"] = True
        if text:
            return text, meta
        meta["error"] = "pdf_no_extractable_text"
        return (
            f"[pdf file: {path.name} — no extractable text layer; "
            "add a .ocr.txt sidecar or a searchable PDF]",
            meta,
        )

    if suffix in _IMAGE_SUFFIXES:
        ocr_text = read_image_ocr(path)
        if ocr_text:
            meta["ocr_used"] = True
            return ocr_text, meta
        meta["error"] = "binary_without_ocr"
        hint = (
            "set TESSERACT_ENABLED=true and install tesseract, "
            "or add a .ocr.txt sidecar next to the image"
        )
        return (
            f"[image file: {path.name} — no OCR text available ({hint})]",
            meta,
        )

    meta["error"] = f"unsupported_binary:{suffix}"
    return f"[unsupported binary: {path.name}]", meta
