"""Page 2 — Validation Report (SSoT §7) + Secondary analytics."""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from dashboard.components.analytics import (
    benchmarks_for,
    heatmap_from_findings,
    try_secondary_benchmarks,
    try_secondary_heatmap,
)
from dashboard.components.common import (
    completeness_score,
    langfuse_link,
    load_report,
    report_html_path,
    risk_tone,
)
from dashboard.components.ui import page_header, require_patient
from shared.settings import get_path

pid = require_patient()
page_header("Validation Report", "Completeness, cross-checks, risk, and secondary analytics.")

if not pid:
    st.stop()

report = load_report(pid)
if not report:
    st.warning(f"No audit report for {pid} yet. Run Process on Document Viewer first.")
    st.stop()

# ---- Top metrics ----
score, score_tone = completeness_score(report)
tone = risk_tone(report.get("risk_level"))
blocked = bool(report.get("discharge_blocked"))

st.markdown(
    f"""
    <div class="metric-row">
      <div class="metric-card"><div class="label">Patient</div>
        <div class="value">{report.get("patient_name") or pid}</div></div>
      <div class="metric-card"><div class="label">Completeness</div>
        <div class="value"><span class="badge {score_tone}">{score}%</span></div></div>
      <div class="metric-card"><div class="label">Risk</div>
        <div class="value"><span class="badge {tone}">{(report.get("risk_level") or "?").upper()}
        ({report.get("risk_score", 0)})</span></div></div>
      <div class="metric-card"><div class="label">Discharge</div>
        <div class="value"><span class="badge {"bad" if blocked else "good"}">
        {"BLOCKED" if blocked else "OK"}</span></div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("#### Recommendation")
st.info(report.get("recommendation") or "—")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Missing fields")
    missing = report.get("missing_fields") or []
    st.write(missing if missing else "None")
with c2:
    st.markdown("#### Elicitation outcome")
    st.write(report.get("elicitation_outcome") or "None")
    st.caption(
        f"Bill: {report.get('bill_payment_status')} · "
        f"amount={report.get('bill_amount')} · "
        f"translation_confidence={report.get('translation_confidence')}"
    )

st.markdown("#### Cross-validation / findings")
findings = report.get("all_findings") or []
if findings:
    df = pd.DataFrame(findings)
    cols = [c for c in ["rule_id", "severity", "weight", "blocking", "field", "message"] if c in df.columns]
    st.dataframe(df[cols], width='stretch', hide_index=True)
else:
    st.success("No findings — clean case.")

# ---- Secondary analytics ----
st.divider()
st.markdown("### Secondary analytics")
st.caption("Uses Secondary MCP when available; otherwise the same local builders so the page never breaks.")

service_line = st.selectbox(
    "Service line (population benchmarks)",
    [
        "General Medicine",
        "Cardiology",
        "Pulmonology",
        "Gastroenterology",
        "General Surgery",
    ],
    index=0,
)

try:
    heatmap, heat_src = asyncio.run(try_secondary_heatmap(findings))
    bench, bench_src = asyncio.run(try_secondary_benchmarks(service_line))
except Exception:
    heatmap, heat_src = heatmap_from_findings(findings), "local"
    bench, bench_src = benchmarks_for(service_line), "local"

a1, a2 = st.columns(2)
with a1:
    st.markdown(f"#### Risk heatmap <span class='badge neutral'>{heat_src}</span>", unsafe_allow_html=True)
    totals = heatmap.get("totals") or {}
    if totals:
        st.bar_chart(pd.DataFrame({"count": totals}).rename_axis("severity"))
    cells = heatmap.get("cells") or {}
    for severity, items in cells.items():
        with st.expander(f"{severity} ({len(items)})", expanded=severity == "critical"):
            st.dataframe(pd.DataFrame(items), width='stretch', hide_index=True)
    if not cells:
        st.write("No findings to plot.")

with a2:
    st.markdown(f"#### Population benchmarks <span class='badge neutral'>{bench_src}</span>", unsafe_allow_html=True)
    st.metric("Service line", bench.get("service_line", service_line))
    st.metric("30-day readmission % (illustrative)", bench.get("readmission_rate_pct"))
    st.metric("Avg risk score (illustrative)", bench.get("avg_risk_score"))
    patient_score = float(report.get("risk_score") or 0)
    cohort_avg = float(bench.get("avg_risk_score") or 0)
    delta = patient_score - cohort_avg
    st.metric(
        "This patient vs cohort avg",
        f"{patient_score:.1f}",
        delta=f"{delta:+.1f} vs avg {cohort_avg:.1f}",
        delta_color="inverse",
    )
    st.caption("Benchmark source is illustrative (FA5 does not ship a real dataset).")

# ---- LangFuse ----
st.divider()
st.markdown("#### LangFuse trace")
link = langfuse_link(report)
if link:
    if str(link).startswith("local-trace:"):
        st.caption(f"Local trace id: `{link.split(':', 1)[1]}` (set LANGFUSE_* for cloud URL)")
        ids = (report.get("audit_trail") or {}).get("trace_ids") or []
        st.write(ids)
    else:
        st.markdown(f"[Open trace]({link})")
else:
    ids = (report.get("audit_trail") or {}).get("trace_ids") or []
    st.caption("Tracing not configured yet." if not ids else f"Trace ids: {ids}")

html_path = report_html_path(pid)
if html_path.is_file():
    st.download_button(
        "Download HTML report",
        data=html_path.read_bytes(),
        file_name=html_path.name,
        mime="text/html",
    )
pdf_path = get_path("reports") / f"{pid}_report.pdf"
if pdf_path.is_file():
    st.download_button(
        "Download PDF report",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
    )
st.download_button(
    "Download JSON report",
    data=__import__("json").dumps(report, indent=2, ensure_ascii=False),
    file_name=f"{pid}_report.json",
    mime="application/json",
)
