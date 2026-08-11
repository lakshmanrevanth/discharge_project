"""Page 3 — HITL Corrections (SSoT §7).

Editable meds (st.data_editor) · elicitation form · risk override ·
approval · save feedback · re-run validation.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.components.common import load_feedback, load_report, save_feedback
from dashboard.components.ui import page_header, require_patient
from dashboard.elicitation_callback import stage_elicitation_response
from mcp_servers.primary.elicitation import TYPE_HINTS

pid = require_patient()
page_header("HITL Corrections", "Edit medications, fill gaps, approve or escalate, re-run validation.")

if not pid:
    st.stop()

report = load_report(pid)
feedback = load_feedback(pid)

# ---- Medication editor ----
st.markdown("### Medication table")
st.caption("Edit rows with `st.data_editor`, then Save feedback.")

default_meds = feedback.get("medications")
if default_meds is None:
    # Seed from session or empty template — extraction may not be on disk
    default_meds = st.session_state.get("edited_meds") or [
        {
            "medicine_name": "",
            "strength": "",
            "frequency": "",
            "route": "",
            "period": "",
        }
    ]

meds_df = pd.DataFrame(default_meds)
edited = st.data_editor(
    meds_df,
    num_rows="dynamic",
    width='stretch',
    key="meds_editor",
)
st.session_state["edited_meds"] = edited.to_dict(orient="records")

# ---- Elicitation form (dynamic from report missing_fields) ----
st.markdown("### Elicitation response form")
missing = list((report or {}).get("missing_fields") or feedback.get("missing_fields") or [])
# Also allow reviewer to add common soft fields manually
extra = st.multiselect(
    "Add fields to the form",
    options=sorted(set(TYPE_HINTS) | {
        "address", "gender", "age", "ward", "bed_no", "attending_physician",
        "consulting_doctors", "follow_up_appointment", "discharge_instructions",
        "allergies", "admission_date", "discharge_date",
    }),
    default=[],
)
fields = list(dict.fromkeys([*missing, *extra]))

if not fields:
    st.info("No missing fields on the latest report. You can still add fields above.")
else:
    st.caption("One batched form for all non-blocking gaps (SSoT §3.7).")

elicited: dict[str, Any] = {}
cols = st.columns(2)
for i, field in enumerate(fields):
    with cols[i % 2]:
        if TYPE_HINTS.get(field) is int:
            elicited[field] = st.number_input(field, value=0, step=1, key=f"elicit_{field}")
        else:
            elicited[field] = st.text_input(field, value="", key=f"elicit_{field}")

e1, e2, e3 = st.columns(3)
if e1.button("Accept elicitation", type="primary"):
    clean = {k: v for k, v in elicited.items() if v not in ("", None)}
    stage_elicitation_response("accept", clean)
    st.session_state["elicitation_values"] = clean
    save_feedback(pid, {"elicitation_action": "accept", "elicited_values": clean, "missing_fields": fields})
    st.success(f"Staged ACCEPT with {len(clean)} field(s). Re-run validation to apply.")
if e2.button("Decline elicitation"):
    stage_elicitation_response("decline")
    save_feedback(pid, {"elicitation_action": "decline", "missing_fields": fields})
    st.warning("Staged DECLINE — case stays on Mandatory HITL.")
if e3.button("Cancel elicitation"):
    stage_elicitation_response("cancel")
    save_feedback(pid, {"elicitation_action": "cancel", "missing_fields": fields})
    st.warning("Staged CANCEL — case stays on Mandatory HITL.")

# ---- Risk override + approval ----
st.markdown("### Risk override & approval")
current_risk = (report or {}).get("risk_level") or "low"
override = st.selectbox(
    "Risk label override",
    ["(no override)", "low", "medium", "high"],
    index=0,
)
approval = st.radio(
    "Approval decision",
    ["Pending", "Approve", "Request changes", "Reject"],
    horizontal=True,
    index=0,
)

if st.button("Save feedback", type="primary"):
    payload = {
        "medications": st.session_state.get("edited_meds"),
        "risk_override": None if override.startswith("(") else override,
        "approval": approval,
        "elicited_values": st.session_state.get("elicitation_values") or {},
        "original_risk_level": current_risk,
        "original_discharge_blocked": (report or {}).get("discharge_blocked"),
    }
    path = save_feedback(pid, payload)
    st.session_state["hitl_approval"] = approval
    st.session_state["risk_override"] = payload["risk_override"]
    st.success(f"Saved `{path}`")

# ---- Re-run validation ----
st.divider()
st.markdown("### Re-run validation")
st.caption(
    "Uses staged elicitation (accept/decline/cancel) when the Rules Engine elicits. "
    "Requires Primary MCP, Secondary MCP, and Mock EHR."
)

if st.button("Re-run validation"):
    status = st.status("Re-running validation…", expanded=True)
    try:
        from agents.extractor.graph import run_extraction
        from agents.normalizer.graph import run_normalization
        from agents.validator.elicitation_handler import (
            reset_elicitation_handler,
            set_elicitation_handler,
        )
        from agents.validator.graph import run_validation
        from dashboard.elicitation_callback import streamlit_elicitation_handler

        async def _run():
            status.write("Extract…")
            ext = await run_extraction(pid)
            if not isinstance(ext, dict):
                ext = {}
            discharge = dict(ext.get("discharge") or {})
            meds = st.session_state.get("edited_meds") or []
            meds = [m for m in meds if (m.get("medicine_name") or "").strip()]
            if meds:
                discharge["medications"] = meds
            for key, val in (st.session_state.get("elicitation_values") or {}).items():
                if val in ("", None):
                    continue
                if key in {"consulting_doctors", "allergies"} and isinstance(val, str):
                    discharge[key] = [p.strip() for p in val.split(",") if p.strip()]
                else:
                    discharge[key] = val
            ext = dict(ext)
            ext["discharge"] = discharge

            status.write("Normalize…")
            norm = await run_normalization(pid, ext)
            token = set_elicitation_handler(streamlit_elicitation_handler)
            try:
                status.write("Validate (with HITL elicitation handler)…")
                return await run_validation(pid, norm)
            finally:
                reset_elicitation_handler(token)

        out = asyncio.run(_run())
        status.update(label="Validation complete", state="complete")
        st.success(
            f"risk={out.get('risk_level')} score={out.get('risk_score')} "
            f"blocked={out.get('discharge_blocked')}"
        )
        st.json(
            {
                "risk_level": out.get("risk_level"),
                "risk_score": out.get("risk_score"),
                "recommendation": out.get("recommendation"),
                "discharge_blocked": out.get("discharge_blocked"),
                "elicitation_outcome": out.get("elicitation_outcome"),
                "missing_fields": out.get("missing_fields"),
            }
        )
    except Exception as exc:
        status.update(label="Re-run failed", state="error")
        st.error(str(exc))

if feedback:
    with st.expander("Saved feedback on disk"):
        st.json(feedback)
