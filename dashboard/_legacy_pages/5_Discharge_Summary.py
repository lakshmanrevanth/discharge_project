"""Page 5 — Discharge Summary (SSoT §7)."""

from __future__ import annotations

import asyncio
import json

import pandas as pd
import streamlit as st

from dashboard.components.common import (
    langfuse_link,
    load_feedback,
    load_report,
    report_html_path,
    risk_tone,
)
from dashboard.components.ui import page_header, require_patient
from agents.summary.agent import is_summary_allowed

pid = require_patient()
page_header("Discharge Summary", "Patient-friendly summary for cases allowed by the release gate.")

if not pid:
    st.stop()

report = load_report(pid)
feedback = load_feedback(pid)

risk = (feedback.get("risk_override") or (report or {}).get("risk_level") or "low")
blocked = bool((report or {}).get("discharge_blocked"))
approval = feedback.get("approval") or st.session_state.get("hitl_approval")

tone = risk_tone(risk)
st.markdown(
    f'<span class="badge {tone}">Risk: {str(risk).upper()}</span> '
    f'<span class="badge {"bad" if blocked else "good"}">'
    f'{"blocked" if blocked else "not blocked"}</span> '
    f'<span class="badge neutral">HITL: {approval or "Pending"}</span>',
    unsafe_allow_html=True,
)

allowed = is_summary_allowed(str(risk), blocked)
if approval == "Approve":
    allowed = True
    st.info("HITL approval overrides the auto-gate for summary generation.")
elif not allowed:
    st.error(
        "Release gate: High risk or discharge_blocked — summary is withheld until "
        "a clinician Approves on HITL Corrections (SSoT §5.7 / §8)."
    )

st.markdown("### Generate summary")
st.caption("Needs Primary MCP + Bedrock. Embeds clinical data from the latest extraction/normalization when possible.")

if st.button("Generate patient-friendly summary", type="primary", disabled=not allowed and approval != "Approve"):
    status = st.status("Generating sections…", expanded=True)
    try:
        from agents.extractor.graph import run_extraction
        from agents.normalizer.graph import run_normalization
        from agents.summary.agent import run_summary

        async def _run():
            status.write("Loading clinical extraction…")
            try:
                ext = await run_extraction(pid)
                norm = await run_normalization(pid, ext)
                extraction = norm.get("normalized_extraction") or ext
            except Exception as exc:
                status.write(f"Live extract unavailable ({exc}) — using minimal stub from report.")
                extraction = {
                    "patient_id": pid,
                    "discharge": {
                        "patient_id": pid,
                        "patient_name": (report or {}).get("patient_name") or pid,
                        "medications": feedback.get("medications") or [],
                        "discharge_diagnosis": [],
                        "discharge_instructions": "",
                        "follow_up_appointment": "",
                        "allergies": [],
                    },
                    "lab": {},
                    "bill": {
                        "payment_status": (report or {}).get("bill_payment_status"),
                        "total_amount": (report or {}).get("bill_amount"),
                    },
                }

            status.write("Streaming sections patient → meds → labs → bill → instructions…")
            return await run_summary(
                patient_id=pid,
                risk_level=str(risk),
                discharge_blocked=False if approval == "Approve" else blocked,
                extraction=extraction,
                audience="patient",
            )

        summary = asyncio.run(_run())
        st.session_state["last_summary"] = summary.model_dump()
        status.update(label="Summary ready", state="complete")
    except Exception as exc:
        status.update(label="Summary failed", state="error")
        st.error(str(exc))

summary = st.session_state.get("last_summary")
if summary:
    if summary.get("refused"):
        st.error(summary.get("refuse_reason") or "Summary refused by release gate.")
    else:
        sections = summary.get("sections") or {}
        for name in ["patient", "meds", "labs", "bill", "instructions"]:
            if name not in sections:
                continue
            st.markdown(f"#### {name.title()}")
            st.write(sections[name])

        # Plain-English prescription table from feedback/edited meds
        meds = feedback.get("medications") or []
        meds = [m for m in meds if (m.get("medicine_name") or "").strip()]
        if meds:
            st.markdown("#### Prescription table")
            st.dataframe(pd.DataFrame(meds), width='stretch', hide_index=True)

        st.markdown("#### Colour-coded labs")
        st.caption("Lab flags come from the summary labs section / report when available.")
        st.write(sections.get("labs") or "No lab narrative.")

        # Exports
        st.divider()
        st.markdown("### Export")
        st.download_button(
            "Export JSON",
            data=json.dumps(summary, indent=2, ensure_ascii=False),
            file_name=f"{pid}_summary.json",
            mime="application/json",
        )
        html_bits = [
            f"<h1>Discharge Summary — {pid}</h1>",
            f"<p>Risk: {risk}</p>",
        ]
        for name, text in sections.items():
            html_bits.append(f"<h2>{name.title()}</h2><p>{text}</p>")
        html_doc = "\n".join(html_bits)
        st.download_button(
            "Export HTML",
            data=html_doc,
            file_name=f"{pid}_summary.html",
            mime="text/html",
        )
        # Real PDF export (SSoT §7 page 5 / §5.5)
        try:
            from pathlib import Path
            import tempfile

            from shared.pdf_export import write_summary_pdf

            tmp = Path(tempfile.gettempdir()) / f"{pid}_summary.pdf"
            write_summary_pdf(pid, sections, tmp, risk=str(risk))
            st.download_button(
                "Export PDF",
                data=tmp.read_bytes(),
                file_name=f"{pid}_summary.pdf",
                mime="application/pdf",
            )
        except Exception as exc:
            st.caption(f"PDF export unavailable: {exc}")
            st.download_button(
                "Export plain text (fallback)",
                data="\n\n".join(f"{k.upper()}\n{v}" for k, v in sections.items()),
                file_name=f"{pid}_summary.txt",
                mime="text/plain",
            )
        # Also offer audit HTML if present
        audit_html = report_html_path(pid)
        if audit_html.is_file():
            st.download_button(
                "Download audit HTML report",
                data=audit_html.read_bytes(),
                file_name=audit_html.name,
                mime="text/html",
            )

link = langfuse_link(report)
st.markdown("#### LangFuse trace")
if link:
    if str(link).startswith("local-trace:"):
        st.caption(f"Local trace id: `{link.split(':', 1)[1]}` (set LANGFUSE_* for cloud URL)")
    else:
        st.markdown(f"[Open trace]({link})")
else:
    st.caption("No trace id on the latest report yet — run validation first.")
