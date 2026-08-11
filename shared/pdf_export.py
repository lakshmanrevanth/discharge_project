"""PDF helpers for audit reports + discharge summaries (SSoT §5.5 / §7).

Conflict §16 row 6: FA5 asks for PDF; rules.yaml lists json/html.
Stance: emit JSON + HTML + PDF so both sides are satisfied.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from shared.logger import get_logger

logger = get_logger("pdf_export")


def _safe(text: object, max_len: int = 1500) -> str:
    raw = "" if text is None else str(text)
    cleaned = raw.encode("latin-1", errors="replace").decode("latin-1")
    cleaned = cleaned.replace("\t", " ").strip() or " "
    if len(cleaned) > max_len:
        return cleaned[:max_len] + "..."
    return cleaned


def _write_line(pdf: FPDF, text: object, *, bold: bool = False) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", 11 if not bold else 12)
    # Use explicit usable width — avoids fpdf "Not enough horizontal space" errors.
    width = max(pdf.epw, 10)
    pdf.multi_cell(width, 6, _safe(text))


def write_audit_pdf(report: dict, dest: Path) -> Path:
    """Write a simple clinician-friendly PDF for one validation report."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    _write_line(pdf, "Discharge Audit Report", bold=True)
    _write_line(pdf, f"Patient ID: {report.get('patient_id')}")
    _write_line(pdf, f"Patient name: {report.get('patient_name')}")
    _write_line(pdf, f"Generated: {report.get('generated_at')}")
    _write_line(pdf, f"Rules version: {str(report.get('rules_version') or '')[:16]}")
    _write_line(pdf, f"Risk: {report.get('risk_level')} (score={report.get('risk_score')})")
    _write_line(pdf, f"Discharge blocked: {report.get('discharge_blocked')}")
    _write_line(pdf, f"Recommendation: {report.get('recommendation')}")
    _write_line(pdf, f"Translation confidence: {report.get('translation_confidence')}")
    _write_line(pdf, f"Bill: {report.get('bill_amount')} / {report.get('bill_payment_status')}")
    missing = ", ".join(report.get("missing_fields") or []) or "None"
    _write_line(pdf, f"Missing fields: {missing}")
    tids = ", ".join((report.get("audit_trail") or {}).get("trace_ids") or []) or "None"
    _write_line(pdf, f"Trace IDs: {tids}")
    _write_line(pdf, "Findings:", bold=True)

    for finding in report.get("all_findings") or []:
        _write_line(
            pdf,
            f"- [{finding.get('severity')}] {finding.get('rule_id')}: {finding.get('message')}",
        )

    pdf.output(str(dest))
    logger.info("Wrote audit PDF %s", dest)
    return dest


def write_summary_pdf(patient_id: str, sections: dict, dest: Path, *, risk: str = "") -> Path:
    """Write a patient-friendly discharge summary PDF."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    _write_line(pdf, f"Discharge Summary — {patient_id}", bold=True)
    if risk:
        _write_line(pdf, f"Risk: {risk}")
    for name in ["patient", "meds", "labs", "bill", "instructions"]:
        text = (sections or {}).get(name)
        if not text:
            continue
        _write_line(pdf, name.title(), bold=True)
        _write_line(pdf, text)

    pdf.output(str(dest))
    logger.info("Wrote summary PDF %s", dest)
    return dest
