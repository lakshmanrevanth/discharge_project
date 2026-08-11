"""Shared HITL helpers — patient discovery, reports, feedback (SSoT §7).

Works for ANY patient_id (P001, P1019, P2001, …) — discovers IDs from
intake files and report stems, never a hard-coded sample list.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from mcp_servers.primary.roots import INTAKE_SUBFOLDERS, sanitize_patient_id
from shared.settings import get_path

_PATIENT_PREFIX_RE = re.compile(r"^(P\d+)", re.IGNORECASE)


def discover_patient_ids() -> list[str]:
    """Union of patient IDs from intake folders + existing audit reports."""
    found: set[str] = set()

    for folder_key, default_name in (
        ("input_doctor_reports", "doctor_reports"),
        ("input_lab_reports", "lab_reports"),
        ("input_bills", "bills"),
    ):
        try:
            folder = get_path(folder_key)
        except KeyError:
            folder = get_path("input_root") / default_name
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file():
                continue
            match = _PATIENT_PREFIX_RE.match(path.name)
            if match:
                found.add(match.group(1).upper())

    reports = get_path("reports")
    if reports.is_dir():
        for path in reports.glob("*_report.json"):
            stem = path.name[: -len("_report.json")]
            if _PATIENT_PREFIX_RE.fullmatch(stem):
                found.add(stem.upper())

    return sorted(found, key=lambda p: (len(p), p))


def patient_display_name(patient_id: str) -> str:
    """Resolve a display name for any patient_id (Mock EHR → report → fallback)."""
    try:
        pid = sanitize_patient_id(patient_id)
    except Exception:
        pid = str(patient_id or "").strip().upper()
    if not pid:
        return "—"
    try:
        from mock_ehr.seed import PATIENTS

        row = PATIENTS.get(pid) or {}
        name = str(row.get("patient_name") or "").strip()
        if name:
            return name
    except Exception:
        pass
    report = load_report(pid)
    if report:
        name = str(report.get("patient_name") or "").strip()
        if name:
            return name
    return "Patient"


def filter_patient_hints(query: str, patient_ids: list[str], *, limit: int = 3) -> list[str]:
    """Return top matching patient IDs (exact ID → ID prefix → name), capped at ``limit``."""
    needle = (query or "").strip().lower()
    if not needle:
        return []
    scored: list[tuple[int, str]] = []
    for pid in patient_ids:
        name = patient_display_name(pid).lower()
        pid_l = pid.lower()
        if needle == pid_l:
            score = 0  # exact patient ID
        elif pid_l.startswith(needle):
            score = 1  # ID prefix
        elif name.startswith(needle):
            score = 2  # name prefix
        elif needle in name:
            score = 3  # name contains
        elif needle in pid_l:
            score = 4  # ID contains
        else:
            continue
        scored.append((score, pid))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [pid for _, pid in scored[: max(0, int(limit))]]


def list_patient_files(patient_id: str) -> dict[str, list[dict]]:
    """Return intake files for one patient, grouped by doc type."""
    patient_id = sanitize_patient_id(patient_id)
    result: dict[str, list[dict]] = {name: [] for name in INTAKE_SUBFOLDERS}
    mapping = {
        "doctor_reports": "input_doctor_reports",
        "lab_reports": "input_lab_reports",
        "bills": "input_bills",
    }
    for doc_type, path_key in mapping.items():
        try:
            folder = get_path(path_key)
        except KeyError:
            folder = get_path("input_root") / doc_type
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            match = _PATIENT_PREFIX_RE.match(path.name)
            if not match or match.group(1).upper() != patient_id:
                continue
            result[doc_type].append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "suffix": path.suffix.lower(),
                }
            )
    return result


def read_text_preview(path: str | Path, max_chars: int = 4000) -> str:
    """Best-effort text preview for txt/json/ocr sidecars."""
    p = Path(path)
    try:
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"} and not str(p).endswith(".ocr.txt"):
            ocr = Path(str(p) + ".ocr.txt")
            if ocr.is_file():
                p = ocr
            else:
                return f"[binary image: {Path(path).name} — no .ocr.txt sidecar]"
        if p.suffix.lower() == ".pdf":
            ocr = Path(str(p) + ".ocr.txt")
            if ocr.is_file():
                p = ocr
            else:
                return f"[PDF: {Path(path).name} — open via Extractor / OCR sidecar]"
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"[could not read file: {exc}]"
    if len(text) > max_chars:
        return text[:max_chars] + "\n… [truncated]"
    return text


def detect_language_badge(text: str) -> str:
    """Tiny heuristic language badge for Document Viewer (not a full detector)."""
    sample = (text or "")[:800]
    if re.search(r"[\u0900-\u097F]", sample):
        return "hi (Hindi script detected)"
    if re.search(r"[äöüßÄÖÜ]", sample) and re.search(r"\b(und|der|die|das)\b", sample, re.I):
        return "de (German cues)"
    if re.search(r"[ñáéíóúü¿¡]", sample, re.I) and re.search(r"\b(el|la|los|paciente)\b", sample, re.I):
        return "es (Spanish cues)"
    if re.search(r"\b(de|het|een|patiënt|ontslag)\b", sample, re.I):
        return "nl (Dutch cues)"
    if re.search(r"[àâçéèêëîïôùûü]", sample, re.I) and re.search(r"\b(le|la|les|patient)\b", sample, re.I):
        return "fr (French cues)"
    return "en / unknown"


def report_json_path(patient_id: str) -> Path:
    return get_path("reports") / f"{sanitize_patient_id(patient_id)}_report.json"


def report_html_path(patient_id: str) -> Path:
    return get_path("reports") / f"{sanitize_patient_id(patient_id)}_report.html"


def load_report(patient_id: str) -> dict | None:
    path = report_json_path(patient_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def feedback_path(patient_id: str) -> Path:
    return get_path("reports") / f"{sanitize_patient_id(patient_id)}_hitl_feedback.json"


def load_feedback(patient_id: str) -> dict:
    path = feedback_path(patient_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_feedback(patient_id: str, payload: dict) -> Path:
    """Persist HITL feedback (storage mechanism NOT SPECIFIED — JSON file)."""
    path = feedback_path(patient_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_feedback(patient_id)
    # Elicitation-only saves must not keep stale med drafts after a fresh Process.
    if "medications" not in payload and existing.get("meds_stale"):
        existing.pop("medications", None)
    existing.update(payload)
    if "medications" in payload:
        existing["meds_stale"] = False
    existing["patient_id"] = sanitize_patient_id(patient_id)
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_feedback_medications(patient_id: str, *, pipeline_trace_id: str | None = None) -> None:
    """Drop med drafts so disk cannot outrank a fresh Process extract."""
    existing = load_feedback(patient_id)
    if not existing:
        return
    existing.pop("medications", None)
    existing["meds_stale"] = True
    existing["patient_id"] = sanitize_patient_id(patient_id)
    if pipeline_trace_id:
        existing["pipeline_trace_id"] = pipeline_trace_id
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = feedback_path(patient_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def completeness_score(report: dict | None) -> tuple[int, str]:
    """Simple completeness % for Page 2 colour badge (formula NOT SPECIFIED)."""
    if not report:
        return 0, "unknown"
    missing = report.get("missing_fields") or []
    findings = report.get("all_findings") or []
    completeness_gaps = [
        f for f in findings if f.get("rule_id") in {"missing_mandatory_field", "missing_address", "missing_gender"}
    ]
    # Start at 100; subtract for gaps (soft + hard)
    score = 100 - 8 * len(missing) - 10 * len(completeness_gaps)
    score = max(0, min(100, score))
    if score >= 90:
        tone = "good"
    elif score >= 70:
        tone = "warn"
    else:
        tone = "bad"
    return score, tone


def risk_tone(level: str | None) -> str:
    level = (level or "low").lower()
    if level == "high":
        return "bad"
    if level == "medium":
        return "warn"
    return "good"


def langfuse_link(report: dict | None) -> str | None:
    """Return a LangFuse URL when available; else None."""
    if not report:
        return None
    trail = report.get("audit_trail") or {}
    if trail.get("langfuse_url"):
        return trail["langfuse_url"]
    ids = trail.get("trace_ids") or []
    if not ids:
        return None
    from shared.tracing.langfuse import trace_url

    return trace_url(ids[0]) or f"local-trace:{ids[0]}"


# Resolving a URL hits LangFuse once per trace to fetch the project id — memoise
# so a rerun-heavy dashboard cannot turn that into a request per script run.
_TRACE_URL_CACHE: dict[str, str | None] = {}
_TRACE_URL_CACHE_MAX = 256


def _resolved_trace_url(trace_id: str) -> str | None:
    if trace_id in _TRACE_URL_CACHE:
        return _TRACE_URL_CACHE[trace_id]
    try:
        from shared.tracing.langfuse import trace_url

        url = trace_url(trace_id)
    except Exception:  # noqa: BLE001 — a dead tracing backend must not break the UI
        url = None
    if len(_TRACE_URL_CACHE) >= _TRACE_URL_CACHE_MAX:
        _TRACE_URL_CACHE.clear()
    _TRACE_URL_CACHE[trace_id] = url
    return url


def case_trace_url(report: dict | None, trace_id: str | None = None) -> str | None:
    """Openable trace URL for a case, or None when tracing is not configured.

    Prefers the URL the Clinical Insight Reporter already stamped into
    ``audit_trail.langfuse_url``; otherwise resolves the live ``trace_id``.
    The ``local-trace:`` sentinel means file-only tracing — not a link.
    """
    try:
        link = langfuse_link(report)
    except Exception:  # noqa: BLE001
        link = None
    if link and not str(link).startswith("local-trace:"):
        return str(link)
    tid = str(trace_id or "").strip()
    return _resolved_trace_url(tid) if tid else None
