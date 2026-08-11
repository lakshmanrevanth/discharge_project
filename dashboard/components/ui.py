"""Shared Streamlit chrome — sidebar patient picker + clinical CSS."""

from __future__ import annotations

import streamlit as st

from dashboard.components.common import discover_patient_ids, load_feedback, load_report, risk_tone
from mcp_servers.primary.roots import sanitize_patient_id


def inject_css() -> None:
    """Professional clinical look — slate + teal, not generic AI purple."""
    st.markdown(
        """
        <style>
          :root {
            --ink: #0f1c2e;
            --muted: #5b6b7c;
            --panel: #f4f7fa;
            --line: #d7e0ea;
            --accent: #0e7c7b;
            --accent-soft: #d8f3f2;
            --good: #1b7f4b;
            --warn: #b86e00;
            --bad: #b42318;
          }
          .block-container { padding-top: 1.2rem; max-width: 1100px; }
          h1, h2, h3 { color: var(--ink); letter-spacing: -0.02em; }
          .hitl-hero {
            background: linear-gradient(135deg, #0f1c2e 0%, #0e7c7b 100%);
            color: white; border-radius: 16px; padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
          }
          .hitl-hero h1 { color: white; margin: 0 0 0.35rem 0; font-size: 1.6rem; }
          .hitl-hero p { margin: 0; opacity: 0.9; }
          .badge {
            display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
            font-size: 0.8rem; font-weight: 600;
          }
          .badge.good { background: #e5f6ec; color: var(--good); }
          .badge.warn { background: #fff4e5; color: var(--warn); }
          .badge.bad { background: #fdecea; color: var(--bad); }
          .badge.neutral { background: var(--accent-soft); color: var(--accent); }
          .panel {
            background: var(--panel); border: 1px solid var(--line);
            border-radius: 12px; padding: 0.9rem 1rem; margin-bottom: 0.75rem;
          }
          .metric-row { display: flex; gap: 0.75rem; flex-wrap: wrap; }
          .metric-card {
            flex: 1; min-width: 140px; background: white; border: 1px solid var(--line);
            border-radius: 12px; padding: 0.85rem 1rem;
          }
          .metric-card .label { color: var(--muted); font-size: 0.78rem; }
          .metric-card .value { color: var(--ink); font-size: 1.35rem; font-weight: 700; }
          div[data-testid="stSidebar"] { background: #f7fafc; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session_defaults() -> None:
    if "patient_id" not in st.session_state:
        ids = discover_patient_ids()
        st.session_state["patient_id"] = ids[0] if ids else ""
    st.session_state.setdefault("hitl_approval", None)
    st.session_state.setdefault("risk_override", None)
    st.session_state.setdefault("edited_meds", None)
    st.session_state.setdefault("edited_meds_pid", None)
    st.session_state.setdefault("edited_meds_epoch", None)
    st.session_state.setdefault("meds_editor_epoch", 0)
    st.session_state.setdefault("elicitation_values", {})
    st.session_state.setdefault("last_rag", None)
    st.session_state.setdefault("last_summary", None)


def render_sidebar() -> str | None:
    """Patient selector + risk glance. Returns selected patient_id or None."""
    ensure_session_defaults()
    inject_css()

    st.sidebar.markdown("### Clinical HITL")
    st.sidebar.caption("Review · correct · approve · ask · summarize")

    ids = discover_patient_ids()
    manual = st.sidebar.text_input(
        "Patient ID (P + digits)",
        value=st.session_state.get("patient_id", ""),
        help="Works for any patient — not limited to the sample corpus.",
    ).strip()

    chosen = None
    if manual:
        try:
            chosen = sanitize_patient_id(manual)
        except ValueError as exc:
            st.sidebar.error(str(exc))

    if ids:
        if chosen in ids:
            picked = st.sidebar.selectbox("Known patients", ids, index=ids.index(chosen))
            chosen = picked
        elif chosen is None:
            chosen = st.sidebar.selectbox("Known patients", ids, index=0)
        else:
            st.sidebar.selectbox(
                "Known patients",
                ids,
                index=0,
                disabled=True,
                help="Clear or change the Patient ID field to pick from this list.",
            )
            st.sidebar.info(f"{chosen} is new — upload documents on Document Viewer.")

    if chosen:
        st.session_state["patient_id"] = chosen
        report = load_report(chosen)
        feedback = load_feedback(chosen)
        if report:
            tone = risk_tone(report.get("risk_level"))
            st.sidebar.markdown(
                f'<span class="badge {tone}">Risk: {(report.get("risk_level") or "?").upper()}</span>',
                unsafe_allow_html=True,
            )
            blocked = report.get("discharge_blocked")
            st.sidebar.markdown(
                f'<span class="badge {"bad" if blocked else "good"}">'
                f'{"Discharge blocked" if blocked else "Not blocked"}</span>',
                unsafe_allow_html=True,
            )
        approval = feedback.get("approval") or st.session_state.get("hitl_approval")
        if approval:
            st.sidebar.markdown(f"**HITL decision:** {approval}")
        st.sidebar.divider()
        st.sidebar.caption("Services optional — pages degrade gracefully if offline.")
    else:
        st.sidebar.warning("Enter a patient ID to begin.")

    return chosen


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hitl-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def require_patient() -> str | None:
    pid = render_sidebar()
    if not pid:
        st.info("Select or enter a patient ID in the sidebar.")
    return pid
