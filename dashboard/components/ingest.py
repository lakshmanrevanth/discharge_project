"""Document ingest helpers — write uploads into data/input/ (SSoT §12 naming).

Generalized for any patient_id. Does not invent a parallel inbox — uses the
same folders the Clinical Watcher scans.
"""

from __future__ import annotations

from pathlib import Path

from mcp_servers.primary.roots import sanitize_patient_id
from shared.settings import get_path

_DOC_FOLDERS = {
    "discharge": ("input_doctor_reports", "doctor_reports"),
    "lab": ("input_lab_reports", "lab_reports"),
    "bill": ("input_bills", "bills"),
}

_COVERAGE_KEYS = ("discharge", "lab", "bill")

_LABELS = {
    "discharge": "discharge report",
    "lab": "lab report",
    "bill": "hospital bill",
}

# list_patient_files folder name → coverage key
_FOLDER_TO_KIND = {
    "doctor_reports": "discharge",
    "lab_reports": "lab",
    "bills": "bill",
}


def _folder_for(doc_kind: str) -> Path:
    path_key, fallback = _DOC_FOLDERS[doc_kind]
    try:
        folder = get_path(path_key)
    except KeyError:
        folder = get_path("input_root") / fallback
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def build_filename(patient_id: str, doc_kind: str, original_name: str) -> str:
    """Build Watcher-compatible filename for any patient_id."""
    pid = sanitize_patient_id(patient_id)
    suffix = Path(original_name).suffix.lower() or ".txt"
    if doc_kind == "discharge":
        # Keep a readable stem; Watcher only needs the P###_ prefix
        stem = Path(original_name).stem.replace(" ", "_")
        if not stem.lower().startswith(pid.lower()):
            stem = f"{pid}_{stem}"
        return f"{stem}{suffix}"
    if doc_kind == "lab":
        return f"{pid}_labs{suffix}"
    if doc_kind == "bill":
        return f"{pid}_bill{suffix}"
    raise ValueError(f"unknown doc_kind: {doc_kind}")


def save_upload(patient_id: str, doc_kind: str, original_name: str, data: bytes) -> Path:
    """Write uploaded bytes into the correct intake folder; return saved path."""
    if doc_kind not in _DOC_FOLDERS:
        raise ValueError(f"doc_kind must be one of {list(_DOC_FOLDERS)}")
    folder = _folder_for(doc_kind)
    filename = build_filename(patient_id, doc_kind, original_name)
    dest = folder / filename
    dest.write_bytes(data)
    return dest


def intake_doc_coverage(patient_id: str) -> dict[str, bool]:
    """True when at least one intake file exists for discharge / lab / bill."""
    from dashboard.components.common import list_patient_files

    try:
        pid = sanitize_patient_id(patient_id)
    except Exception:
        return {k: False for k in _COVERAGE_KEYS}

    files = list_patient_files(pid)
    coverage = {k: False for k in _COVERAGE_KEYS}
    for folder, kind in _FOLDER_TO_KIND.items():
        coverage[kind] = bool(files.get(folder))
    return coverage


def missing_intake_labels(coverage: dict[str, bool] | None) -> list[str]:
    """Human labels for missing discharge / lab / bill kinds."""
    cov = coverage or {}
    return [_LABELS[k] for k in _COVERAGE_KEYS if not cov.get(k)]


def all_intake_present(coverage: dict[str, bool] | None) -> bool:
    """True when discharge, lab, and bill are all present."""
    cov = coverage or {}
    return all(cov.get(k) for k in _COVERAGE_KEYS)
