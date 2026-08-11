"""Roots helpers — URI ↔ Path + path-traversal guards (SSoT §3.8).

Clinical Watcher must only scan inside client-declared Roots.
Use Path.relative_to() so anything outside the root is rejected.

Also: sanitize_patient_id() so Harvester / file lookup reject ../ and
path separators — same safety idea for tool args that are not Roots.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse


# Subfolders under the MCP Root workspace (SSoT §12 / architecture)
INTAKE_SUBFOLDERS = ("doctor_reports", "lab_reports", "bills")

# Matches Watcher + FA5 examples (P001, P1019, P1024, …) — any digit length
_PATIENT_ID_RE = re.compile(r"^P\d+$", re.IGNORECASE)


def sanitize_patient_id(patient_id: str) -> str:
    """Return a safe patient_id (e.g. P001 / P1019) or raise ValueError.

    Rejects empty values, path separators, and '..' so callers cannot escape
    an intake folder via patient_id. Not limited to the sample corpus.
    """
    pid = (patient_id or "").strip()
    if not pid:
        raise ValueError("patient_id is empty")
    if "/" in pid or "\\" in pid or ".." in pid:
        raise ValueError(f"invalid patient_id (path characters not allowed): {patient_id!r}")
    if not _PATIENT_ID_RE.fullmatch(pid):
        raise ValueError(f"invalid patient_id (expected P + digits, e.g. P001): {patient_id!r}")
    return pid.upper()


def file_uri_to_path(uri: str) -> Path:
    """Convert a file:// URI to a local Path.

    Examples:
        file:///data/input  ->  /data/input
        file:///Users/me/proj/data/input  ->  /Users/me/proj/data/input
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Only file:// Roots are supported, got: {uri}")
    # unquote handles spaces / encoded chars in paths
    return Path(unquote(parsed.path)).resolve()


def path_to_file_uri(path: Path) -> str:
    """Convert a local Path to a file:// URI (absolute)."""
    resolved = path.resolve()
    return resolved.as_uri()


def assert_inside_root(candidate: Path, root: Path) -> Path:
    """Return resolved candidate if it is inside root; else raise ValueError.

    This is the SSoT §3.8 path-traversal prevention rule.
    """
    candidate_resolved = candidate.resolve()
    root_resolved = root.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"Path escapes declared Root: {candidate_resolved} not under {root_resolved}"
        ) from exc
    return candidate_resolved


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root and reject traversal (e.g. '../etc')."""
    return assert_inside_root(root.joinpath(*parts), root)
