"""Agno Indexing Agent — parse intake docs into FAISS (SSoT §5.6 agent 1).

Beginner picture:
  1. Find this patient_id's files under data/input/ (any patient, any digit length).
  2. Read text (txt/json/ocr; PDF via PyPDF2; optional Tesseract for images).
  3. Split with RecursiveCharacterTextSplitter (sizes from agent_config.yaml).
  4. Save into FAISS at data/vector_db/{patient_id}/.
  5. Re-index when the intake file set changes (new uploads must not stay stale).
  6. After HITL Corrections, a reviewed case snapshot replaces the raw discharge
     note in the index so RAG answers match the corrected medications / fields.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agno.agent import Agent
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.model import get_agno_model
from rag.vectorstore import (
    clear_patient_index,
    indexed_source_paths,
    patient_is_indexed,
    save_patient_index,
)
from shared.logger import get_logger
from shared.settings import get_path, get_service

logger = get_logger("rag_indexing")

_PATIENT_PREFIX_RE = re.compile(r"^(P\d+)", re.IGNORECASE)

# Text-like suffixes we can index directly. Prefer .ocr.txt when present for scans.
_TEXT_SUFFIXES = {".txt", ".json", ".md", ".csv"}
_BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}


def _rag_cfg() -> dict:
    return get_service("rag")


def hitl_corrected_path(patient_id: str) -> Path:
    """Where HITL Re-run stores the reviewed case for RAG re-index."""
    return get_path("reports") / f"{str(patient_id).strip().upper()}_hitl_corrected.json"


def case_to_index_text(case: dict[str, Any]) -> str:
    """Turn a reviewed case dict into plain text for FAISS (beginner-simple)."""
    lines: list[str] = [
        "HITL-REVIEWED DISCHARGE FACTS (authoritative after Corrections)",
        "Use these medications / allergies / diagnosis for discharge questions.",
        "Do not treat hospital bill pharmacy line-items as the current discharge prescription list.",
        f"Patient ID: {case.get('patient_id') or ''}",
        f"Patient Name: {case.get('patient_name') or ''}",
    ]
    if case.get("age") is not None:
        lines.append(f"Age: {case.get('age')}")
    if case.get("gender"):
        lines.append(f"Gender: {case.get('gender')}")
    if case.get("address"):
        lines.append(f"Address: {case.get('address')}")
    if case.get("admission_date"):
        lines.append(f"Admission Date: {case.get('admission_date')}")
    if case.get("discharge_date"):
        lines.append(f"Discharge Date: {case.get('discharge_date')}")
    if case.get("ward") or case.get("bed_no"):
        lines.append(f"Ward/Bed: {case.get('ward') or ''} / {case.get('bed_no') or ''}")

    attending = case.get("attending_physician")
    if attending not in (None, ""):
        lines.append(f"Attending Physician: {attending}")
    consulting = case.get("consulting_doctors") or []
    if isinstance(consulting, str):
        consulting = [p.strip() for p in consulting.split(",") if p.strip()]
    if not consulting and case.get("doctors") and not attending:
        doctors = case.get("doctors") or []
        if isinstance(doctors, str):
            doctors = [p.strip() for p in doctors.split(",") if p.strip()]
        consulting = list(doctors)
    if consulting:
        lines.append(
            "Consulting Doctors: "
            + ", ".join(str(d).strip() for d in consulting if str(d).strip())
        )

    dx = case.get("discharge_diagnosis") or []
    if isinstance(dx, str):
        dx = [dx]
    if dx:
        lines.append("Discharge Diagnosis:")
        for item in dx:
            lines.append(f"- {item}")

    allergies = case.get("allergies") or case.get("adr_allergy_info") or []
    if isinstance(allergies, str):
        allergies = [allergies]
    if allergies:
        lines.append("Allergies:")
        for item in allergies:
            lines.append(f"- {item}")

    meds = case.get("medications") or []
    lines.append("Discharge Medications (reviewed):")
    if not meds:
        lines.append("- (none — reviewer removed all rows or none on file)")
    for m in meds:
        if not isinstance(m, dict):
            continue
        name = (m.get("medicine_name") or m.get("name") or "").strip()
        if not name:
            continue
        parts = [
            name,
            str(m.get("strength") or "").strip(),
            str(m.get("frequency") or "").strip(),
            str(m.get("route") or "").strip(),
            str(m.get("period") or "").strip(),
        ]
        lines.append("- " + " | ".join(p for p in parts if p))

    follow = case.get("follow_up_appointment") or case.get("follow_up_appointments")
    if follow:
        lines.append(f"Follow-up Appointment: {follow}")
    if case.get("discharge_instructions"):
        lines.append(f"Discharge Instructions: {case.get('discharge_instructions')}")
    if "discharge_ok" in case or "discharge_approved" in case:
        approved = case.get("discharge_ok", case.get("discharge_approved"))
        lines.append(f"Discharge Approved: {approved}")

    bill = case.get("bill") if isinstance(case.get("bill"), dict) else {}
    if bill:
        lines.append(
            f"Bill: id={bill.get('bill_id') or ''} status={bill.get('payment_status') or ''} "
            f"total={bill.get('total_amount') or ''}"
        )
    return "\n".join(lines).strip() + "\n"


def save_hitl_corrected_case(patient_id: str, case: dict[str, Any]) -> Path:
    """Persist reviewed case so RAG re-index and later Ensure Index use it."""
    pid = str(patient_id).strip().upper()
    path = hitl_corrected_path(pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "patient_id": pid,
        "case": case,
        "index_text": case_to_index_text({**case, "patient_id": pid}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved HITL-corrected case for RAG at %s", path)
    return path


def clear_hitl_corrected_case(patient_id: str) -> None:
    """Drop reviewed snapshot after a fresh Process (intake is source of truth again)."""
    path = hitl_corrected_path(patient_id)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not clear HITL corrected file %s: %s", path, exc)


def load_hitl_corrected_case(patient_id: str) -> dict[str, Any] | None:
    path = hitl_corrected_path(patient_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    case = data.get("case")
    return case if isinstance(case, dict) else None


def _patient_id_from_filename(name: str) -> str | None:
    """Extract P### from filenames like P1019_thomas_wright.txt / P1021_labs.json."""
    stem = name
    # Strip multi-part suffixes like .pdf.ocr.txt
    while True:
        lowered = stem.lower()
        if lowered.endswith(".ocr.txt"):
            stem = stem[: -len(".ocr.txt")]
            continue
        p = Path(stem)
        if p.suffix:
            stem = p.stem
            continue
        break
    match = _PATIENT_PREFIX_RE.match(stem)
    return match.group(1).upper() if match else None


def _read_file_text(path: Path) -> str:
    """Read text/json/ocr, or extract PDF/image text for new uploads without sidecars."""
    suffix = path.suffix.lower()
    name = path.name.lower()

    if name.endswith(".ocr.txt") or suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return ""

    if suffix == ".json":
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return ""
        try:
            data = json.loads(raw)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw

    if suffix in _BINARY_SUFFIXES:
        try:
            from mcp_servers.primary.document_readers import read_binary_document

            text, meta = read_binary_document(path)
            if meta.get("error"):
                logger.warning("Binary read %s: %s", path.name, meta["error"])
            return text or ""
        except Exception as exc:
            logger.warning("Could not extract text from %s: %s", path, exc)
            return ""

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _logical_stem(path: Path) -> str:
    """Stable stem so .pdf, .pdf.ocr.txt, and .json siblings share one key."""
    name = path.name
    if name.lower().endswith(".ocr.txt"):
        name = name[: -len(".ocr.txt")]
    return Path(name).stem


def _file_priority(path: Path) -> int:
    """Higher wins: OCR sidecar > text/json > raw PDF/image."""
    name = path.name.lower()
    if name.endswith(".ocr.txt"):
        return 3
    if path.suffix.lower() in _TEXT_SUFFIXES:
        return 2
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return 1
    return 0


def _collect_patient_files(patient_id: str) -> list[tuple[Path, str]]:
    """Return [(path, doc_type), ...] for this patient under intake folders.

    Prefers .ocr.txt / .json / .txt over raw binary siblings. Falls back to PDF
    (PyPDF2) or image OCR when no text sidecar exists — needed for new uploads.
    """
    patient_id = patient_id.strip().upper()
    input_root = get_path("input_root")
    folders = {
        "doctor_reports": get_path("input_doctor_reports"),
        "lab_reports": get_path("input_lab_reports"),
        "bills": get_path("input_bills"),
    }
    for key, folder in list(folders.items()):
        if not folder.is_dir():
            alt = input_root / key
            folders[key] = alt if alt.is_dir() else folder

    # key -> (path, doc_type, priority)
    chosen: dict[str, tuple[Path, str, int]] = {}
    for doc_type, folder in folders.items():
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            if _patient_id_from_filename(path.name) != patient_id:
                continue
            priority = _file_priority(path)
            if priority <= 0:
                continue
            key = f"{doc_type}:{_logical_stem(path)}"
            prev = chosen.get(key)
            if prev is None or priority > prev[2]:
                chosen[key] = (path, doc_type, priority)

    return [(path, doc_type) for path, doc_type, _ in chosen.values()]


def _indexed_source_paths(patient_id: str) -> set[str]:
    """Paths currently stored in meta.json (empty if not indexed)."""
    return indexed_source_paths(patient_id)

def index_patient_documents(
    patient_id: str,
    force: bool = False,
    corrected_case: dict | None = None,
) -> str:
    """Index one patient's intake files into FAISS. Safe for any patient_id.

    When a HITL-corrected case is provided (or saved on disk), the raw doctor
    report is replaced by the reviewed facts so RAG does not keep stale meds.
    """
    patient_id = str(patient_id).strip().upper()
    if corrected_case is not None:
        save_hitl_corrected_case(patient_id, corrected_case)
        force = True

    hitl_case = corrected_case if corrected_case is not None else load_hitl_corrected_case(patient_id)
    files = _collect_patient_files(patient_id)

    if hitl_case:
        # Reviewed discharge replaces raw doctor note (avoids Amoxicillin still in RAG).
        files = [(path, doc_type) for path, doc_type in files if doc_type != "doctor_reports"]

    if not files and not hitl_case:
        clear_patient_index(patient_id)
        msg = f"No intake files found for patient {patient_id} under data/input/."
        logger.warning(msg)
        return msg

    current_paths = {str(path) for path, _ in files}
    if hitl_case:
        current_paths.add(str(hitl_corrected_path(patient_id)))

    if (
        not force
        and patient_is_indexed(patient_id)
        and _indexed_source_paths(patient_id) == current_paths
    ):
        msg = f"Patient {patient_id} already indexed — skipped."
        logger.info(msg)
        return msg

    cfg = _rag_cfg()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(cfg.get("chunk_size", 500)),
        chunk_overlap=int(cfg.get("chunk_overlap", 50)),
    )

    chunks: list[dict] = []
    if hitl_case:
        hitl_text = case_to_index_text({**hitl_case, "patient_id": patient_id})
        for piece in splitter.split_text(hitl_text):
            chunks.append(
                {
                    "text": piece,
                    "source_path": str(hitl_corrected_path(patient_id)),
                    "doc_type": "hitl_corrected",
                }
            )

    for path, doc_type in files:
        text = _read_file_text(path)
        if not text.strip():
            logger.warning("Empty text for %s — skipped (need OCR sidecar or readable PDF)", path.name)
            continue
        for piece in splitter.split_text(text):
            chunks.append(
                {
                    "text": piece,
                    "source_path": str(path),
                    "doc_type": doc_type,
                }
            )

    if not chunks:
        clear_patient_index(patient_id)
        msg = (
            f"Found {len(files)} file(s) for {patient_id} but extracted no readable text "
            "(add .txt/.json/.ocr.txt or a text PDF)."
        )
        logger.warning(msg)
        return msg

    count = save_patient_index(patient_id, chunks)
    src_note = f"{len(files)} file(s)"
    if hitl_case:
        src_note += " + HITL-corrected discharge"
    return f"Indexed {count} chunk(s) from {src_note} for {patient_id}."


indexing_agent = Agent(
    name="indexing_agent",
    model=get_agno_model(),
    description="Indexes discharge / lab / bill intake documents into FAISS for any patient_id.",
    instructions=(
        "When asked to index a patient, call index_patient_documents with that patient_id. "
        "Never invent file paths. Never invent clinical content."
    ),
    tools=[index_patient_documents],
)


async def run_indexing(
    patient_id: str,
    force: bool = False,
    corrected_case: dict | None = None,
) -> str:
    """Deterministic indexing path used by the RAG pipeline (beginner-simple)."""
    return index_patient_documents(
        patient_id, force=force, corrected_case=corrected_case
    )
