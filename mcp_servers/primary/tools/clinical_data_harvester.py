"""Clinical Data Harvester Tool (SSoT §3.5, §13 step 3).

Tool only — no Sampling, no Elicitation. Given a patient_id and a document
type, finds the file under data/input/ and returns readable text (+ parsed
JSON when the source is already structured).

Multi-modal (beginner-friendly):
  1. Prefer .ocr.txt / .json / .txt when present (find_patient_file)
  2. PDF → PyPDF2 text extract
  3. PNG/JPG → optional Tesseract (TESSERACT_ENABLED=true)
Works for any new patient files — not hard-coded to the sample corpus.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from mcp_servers.primary.document_readers import read_binary_document
from mcp_servers.primary.roots import sanitize_patient_id
from mcp_servers.primary.rules_loader import find_patient_file, read_text_file
from shared.logger import get_logger
from shared.settings import get_path

logger = get_logger("clinical_data_harvester")

# doc_type (tool param) -> paths.* key in agent_config.yaml
_DOC_TYPE_PATH_KEYS = {
    "discharge": "input_doctor_reports",
    "lab": "input_lab_reports",
    "bill": "input_bills",
}

_BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}

_STRUCTURED_FIELDS_MARKER = "--- structured fields ---"


def json_harvest_raw_text(data: dict) -> str:
    """Build LLM text from a JSON intake: narrative and/or full structured keys.

    If an embedded ``raw_text`` exists, keep it and append the other JSON fields
    so demographics (age/ward/…) are not hidden from the Extractor. Planted
    nulls stay in the dump as null — validation must still surface them.
    """
    narrative = data.get("raw_text")
    if isinstance(narrative, str) and narrative.strip():
        fields_only = {k: v for k, v in data.items() if k != "raw_text"}
        dump = json.dumps(fields_only, ensure_ascii=False, indent=2)
        return f"{narrative.strip()}\n\n{_STRUCTURED_FIELDS_MARKER}\n{dump}"
    return json.dumps(data, ensure_ascii=False, indent=2)


async def _harvest_one(patient_id: str, doc_type: str) -> dict:
    """Locate and read one file for patient_id/doc_type. Returns a plain dict."""
    if doc_type not in _DOC_TYPE_PATH_KEYS:
        return {
            "patient_id": patient_id,
            "doc_type": doc_type,
            "error": f"unknown doc_type '{doc_type}', expected one of {list(_DOC_TYPE_PATH_KEYS)}",
        }

    try:
        safe_id = sanitize_patient_id(patient_id)
    except ValueError as exc:
        return {
            "patient_id": patient_id,
            "doc_type": doc_type,
            "error": str(exc),
            "raw_text": "",
            "structured_data": None,
        }

    folder = get_path(_DOC_TYPE_PATH_KEYS[doc_type])
    path = find_patient_file(folder, safe_id)
    if path is None:
        return {
            "patient_id": safe_id,
            "doc_type": doc_type,
            "error": f"no {doc_type} file found for {safe_id} under {folder}",
            "raw_text": "",
            "structured_data": None,
        }

    suffix = path.suffix.lower()
    is_binary = suffix in _BINARY_SUFFIXES and not path.name.endswith(".ocr.txt")

    result = {
        "patient_id": safe_id,
        "doc_type": doc_type,
        "source_file": path.name,
        "format": suffix.lstrip("."),
        "ocr_used": False,
        "pdf_used": False,
        "structured_data": None,
    }

    if suffix == ".json":
        text = await read_text_file(path)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Bad JSON in %s: %s", path, exc)
            result["raw_text"] = text
            result["error"] = f"invalid JSON: {exc}"
            return result
        result["structured_data"] = data
        # Narrative (if any) plus structured keys — never hide JSON fields from LLM
        result["raw_text"] = json_harvest_raw_text(data)
        return result

    if is_binary:
        text, meta = read_binary_document(path)
        result["raw_text"] = text
        result["ocr_used"] = bool(meta.get("ocr_used"))
        result["pdf_used"] = bool(meta.get("pdf_used"))
        if meta.get("error"):
            result["error"] = meta["error"]
        return result

    # .txt / .ocr.txt sidecar — plain readable text
    result["raw_text"] = await read_text_file(path)
    result["ocr_used"] = path.name.endswith(".ocr.txt")
    return result


def register_harvester_tools(mcp: FastMCP) -> None:
    """Attach the Clinical Data Harvester tool to the Primary MCP server."""

    @mcp.tool(
        name="clinical_data_harvester",
        title="Clinical Data Harvester Tool",
        description=(
            "Extract text/tables from a patient's discharge report, lab report, "
            "or bill under data/input/. Supports txt/json/ocr sidecars, PDF text "
            "(PyPDF2), and optional Tesseract OCR for images. "
            "doc_type must be 'discharge', 'lab', or 'bill'."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def clinical_data_harvester(patient_id: str, doc_type: str) -> str:
        """Harvest one document for one patient. Returns a JSON string."""
        result = await _harvest_one(patient_id, doc_type)
        logger.info(
            "Harvested %s/%s -> %s (error=%s, pdf=%s, ocr=%s)",
            patient_id,
            doc_type,
            result.get("source_file"),
            result.get("error"),
            result.get("pdf_used"),
            result.get("ocr_used"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
