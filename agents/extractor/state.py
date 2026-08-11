"""Extractor graph state (TypedDict) — SSoT §5.2.

Kept intentionally flat (company style: plain TypedDict, little abstraction).
Works for any patient_id — nothing here is sample-corpus specific.
"""

from __future__ import annotations

from typing import TypedDict


class ExtractorState(TypedDict):
    patient_id: str
    doc_types: list[str]  # which of discharge/lab/bill to look for
    harvested: dict[str, dict]  # doc_type -> Harvester tool result
    # MCP Resources read for this patient (uri -> text). Filled in harvest/load_documents.
    resources: dict[str, str]
    # discharge-extraction-prompt body (fetched once in load_documents)
    prompt_text: str
    extraction: dict | None  # final ExtractionResult, as a plain dict
    errors: list[str]
