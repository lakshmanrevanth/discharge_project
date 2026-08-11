"""Page 1 — Document Viewer (SSoT §7).

Patient selector (sidebar) · Discharge/Lab/Bill tabs · language badge ·
structured preview · ingest uploads · process trigger.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from dashboard.components.common import (
    detect_language_badge,
    list_patient_files,
    load_report,
    read_text_preview,
)
from dashboard.components.ingest import save_upload
from dashboard.components.ui import page_header, require_patient

pid = require_patient()
page_header("Document Viewer", "Browse intake files and ingest new documents for any patient.")

if not pid:
    st.stop()

files = list_patient_files(pid)
report = load_report(pid)

with st.expander("Ingest new documents", expanded=not any(files.values())):
    st.caption(
        "Uploads go into `data/input/{doctor_reports,lab_reports,bills}/` with "
        "Watcher-compatible names (`P###_…`). Works for brand-new patient IDs."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        discharge_up = st.file_uploader("Discharge report", key="up_discharge")
    with c2:
        lab_up = st.file_uploader("Lab report", key="up_lab")
    with c3:
        bill_up = st.file_uploader("Hospital bill", key="up_bill")

    if st.button("Save uploads", type="primary"):
        saved = []
        try:
            if discharge_up is not None:
                path = save_upload(pid, "discharge", discharge_up.name, discharge_up.getvalue())
                saved.append(str(path))
            if lab_up is not None:
                path = save_upload(pid, "lab", lab_up.name, lab_up.getvalue())
                saved.append(str(path))
            if bill_up is not None:
                path = save_upload(pid, "bill", bill_up.name, bill_up.getvalue())
                saved.append(str(path))
        except Exception as exc:
            st.error(f"Ingest failed: {exc}")
        else:
            if saved:
                st.success("Saved:\n" + "\n".join(f"- `{p}`" for p in saved))
                st.rerun()
            else:
                st.warning("Choose at least one file to upload.")


def _render_doc_tab(doc_type: str) -> None:
    items = files.get(doc_type) or []
    if not items:
        st.info(f"No {doc_type.replace('_', ' ')} files found for {pid}.")
        return
    names = [i["name"] for i in items]
    choice = st.selectbox(f"File ({doc_type})", names, key=f"file_{doc_type}")
    meta = next(i for i in items if i["name"] == choice)
    preview = read_text_preview(meta["path"])
    lang = detect_language_badge(preview)
    st.markdown(f'<span class="badge neutral">{lang}</span>', unsafe_allow_html=True)
    st.caption(f"`{meta['path']}` · {meta['size']} bytes")
    st.text_area("Preview", preview, height=360, key=f"preview_{doc_type}")


tab_d, tab_l, tab_b, tab_struct = st.tabs(["Discharge", "Lab", "Bill", "Structured preview"])
with tab_d:
    _render_doc_tab("doctor_reports")
with tab_l:
    _render_doc_tab("lab_reports")
with tab_b:
    _render_doc_tab("bills")
with tab_struct:
    if report:
        st.subheader("Latest validation report snapshot")
        st.json(
            {
                "patient_id": report.get("patient_id"),
                "patient_name": report.get("patient_name"),
                "risk_level": report.get("risk_level"),
                "discharge_blocked": report.get("discharge_blocked"),
                "missing_fields": report.get("missing_fields"),
                "bill_payment_status": report.get("bill_payment_status"),
            }
        )
    else:
        st.info("No validation report yet — run Process / Validation first.")

st.divider()
st.subheader("Process trigger")
st.caption(
    "Runs Extract → Normalize → Validate when Primary/Secondary MCP + Mock EHR are up. "
    "If services are offline, you can still browse files and reports."
)

if st.button("Process patient pipeline", type="primary"):
    status = st.status("Running pipeline…", expanded=True)
    try:
        from agents.extractor.graph import run_extraction
        from agents.normalizer.graph import run_normalization
        from agents.validator.graph import run_validation

        async def _run():
            status.write("Extractor…")
            ext = await run_extraction(pid)
            status.write("Normalizer…")
            norm = await run_normalization(pid, ext)
            status.write("Validator…")
            return await run_validation(pid, norm)

        report_out = asyncio.run(_run())
        status.update(label="Pipeline complete", state="complete")
        st.success(
            f"Risk={(report_out or {}).get('risk_level')} · "
            f"blocked={(report_out or {}).get('discharge_blocked')}"
        )
        st.json(
            {
                "risk_level": (report_out or {}).get("risk_level"),
                "risk_score": (report_out or {}).get("risk_score"),
                "recommendation": (report_out or {}).get("recommendation"),
                "discharge_blocked": (report_out or {}).get("discharge_blocked"),
            }
        )
    except Exception as exc:
        status.update(label="Pipeline failed (services may be offline)", state="error")
        st.error(f"{exc}")
        st.info("Tip: start Mock EHR, Primary MCP, Secondary MCP, then retry.")
