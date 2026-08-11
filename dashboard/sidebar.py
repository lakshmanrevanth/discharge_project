"""Clinical sidebar rail — patient context, workflow nav, next-action guidance.

Presentation only. Every number shown here is read from the same session state
the pages render from (``case`` / ``validation`` / ``pipeline_result``) — the
rail never calls an agent and never derives a clinical rule of its own.

Layout, top to bottom:
    brand lockup + collapse control
    active-patient card (who am I charting on, risk, release gate)
    case progress (pipeline stages completed)
    clinical workflow nav (icon + label + live count badge)
    next-action callout (what this clinician should do now)
    footer (trace id / rules version for audit)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from typing import Any

import streamlit as st

from dashboard.state import ADMIN_PAGES, PAGES
from dashboard.styles import nav_label, pipeline_step_states

# ---------------------------------------------------------------- nav metadata

NAV_ICONS: dict[str, str] = {
    "Document Viewer": "≡",
    "Validation Report": "◇",
    "Corrections": "✎",
    "RAG Q&A": "✦",
    "Discharge Summary": "✓",
    "Upload new patients": "↑",
}

# (background, text, border) for count badges on the dark rail.
_BADGE_TONES: dict[str, tuple[str, str, str]] = {
    "ok": ("rgba(16,185,129,0.16)", "#6ee7b7", "rgba(16,185,129,0.32)"),
    "warn": ("rgba(245,158,11,0.18)", "#fcd34d", "rgba(245,158,11,0.34)"),
    "bad": ("rgba(239,68,68,0.20)", "#fca5a5", "rgba(239,68,68,0.36)"),
    "teal": ("rgba(20,184,166,0.18)", "#5eead4", "rgba(20,184,166,0.34)"),
    "mute": ("rgba(148,163,184,0.12)", "#94a3b8", "rgba(148,163,184,0.22)"),
}

# CSS ``content`` has no escaping — drop anything that could close the string
# or the rule. Glyphs such as ✓ / ! stay, so badges can be marks as well as counts.
_BADGE_UNSAFE = re.compile(r'["\\\n\r<>{};]')

PIPELINE_TOTAL = 7


def _badge_text(value: Any) -> str:
    """Short, inert badge text safe to interpolate into a CSS ``content`` string."""
    text = _BADGE_UNSAFE.sub("", str(value if value is not None else "")).strip()
    return text[:8]


# ------------------------------------------------------------------- context


@dataclass
class RailContext:
    """Everything the rail renders, resolved once per script run."""

    patient_id: str = ""
    patient_name: str = ""
    initials: str = "—"
    age: str = ""
    gender: str = ""
    ward: str = ""
    bed: str = ""
    attending: str = ""
    admitted: str = ""

    processed: bool = False
    risk_level: str = ""
    risk_tone: str = "mute"
    gate_label: str = ""
    gate_tone: str = "mute"

    doc_count: int | None = None
    findings_total: int = 0
    critical_count: int = 0
    blocking_count: int = 0
    soft_count: int = 0
    open_corrections: int = 0

    indexed: bool = False
    has_summary: bool = False
    blocked: bool = False
    needs_hitl: bool = False

    stages_done: int = 0
    stage_note: str = ""

    trace_id: str = ""
    trace_url: str = ""
    rules_version: str = ""

    badges: dict[int, tuple[str, str]] = field(default_factory=dict)


def _clean(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text in {"—", "-", "None", "null", "nan"} else text


def _initials(name: str, pid: str) -> str:
    parts = [p for p in name.split() if p and p[0].isalpha()]
    if parts:
        return "".join(p[0].upper() for p in parts[:2])
    return pid[:2].upper() if pid else "—"


def _intake_file_count(pid: str) -> int | None:
    try:
        from dashboard.components.common import list_patient_files

        return sum(len(v) for v in list_patient_files(pid).values())
    except Exception:  # noqa: BLE001 — the rail must never break the app
        return None


def _case_trace_url(val: dict[str, Any] | None, trace_id: str) -> str:
    try:
        from dashboard.components.common import case_trace_url

        return case_trace_url(val, trace_id) or ""
    except Exception:  # noqa: BLE001 — the rail must never break the app
        return ""


def _gate(val: dict[str, Any] | None) -> tuple[str, str]:
    if not val:
        return "Not run", "mute"
    if val.get("discharge_blocked"):
        return "Blocked", "bad"
    if val.get("needs_hitl"):
        return "Needs review", "warn"
    return "Cleared", "ok"


def collect_context() -> RailContext:
    """Read session state into a flat, render-ready struct."""
    from dashboard.components.common import patient_display_name
    from dashboard.ui_chrome import blocking_gaps_for_display

    ctx = RailContext()
    pid = _clean(st.session_state.get("patient_id"))
    case: dict[str, Any] = st.session_state.get("case") or {}
    val: dict[str, Any] = st.session_state.get("validation") or {}
    pipeline: dict[str, Any] = st.session_state.get("pipeline_result") or {}
    same_patient = not case or _clean(case.get("patient_id")).upper() == pid.upper()

    ctx.patient_id = pid
    name = ""
    if pid:
        if same_patient:
            name = _clean(case.get("patient_name"))
        if not name:
            try:
                name = patient_display_name(pid)
            except Exception:  # noqa: BLE001 — rail must never break the app
                name = ""
        if name == "Patient":
            name = ""
    ctx.patient_name = name or ("Unnamed patient" if pid else "")
    ctx.initials = _initials(name, pid)

    if same_patient:
        age = _clean(case.get("age"))
        ctx.age = f"{age}y" if age and age.isdigit() else age
        ctx.gender = _clean(case.get("gender"))[:12]
        ctx.ward = _clean(case.get("ward"))
        ctx.bed = _clean(case.get("bed_no"))
        ctx.attending = _clean(case.get("attending_physician")) or _clean(
            (case.get("doctors") or [None])[0] if case.get("doctors") else ""
        )
        ctx.admitted = _clean(case.get("admission_date"))

    ctx.processed = bool(pipeline or val)
    findings = [f for f in (val.get("findings") or []) if isinstance(f, dict)]
    ctx.findings_total = len(findings)
    ctx.critical_count = sum(
        1 for f in findings if str(f.get("severity") or "").lower() == "critical"
    )
    blocking = blocking_gaps_for_display(val.get("missing_blocking"), findings)
    ctx.blocking_count = len(blocking)
    ctx.soft_count = len([x for x in (val.get("missing_soft") or []) if _clean(x)])
    ctx.open_corrections = ctx.blocking_count + ctx.soft_count

    risk = val.get("risk") or {}
    level = _clean(risk.get("level"))
    ctx.risk_level = level.title() if level else ""
    ctx.risk_tone = {"high": "bad", "medium": "warn", "low": "ok"}.get(level.lower(), "mute")
    ctx.gate_label, ctx.gate_tone = _gate(val or None)
    ctx.blocked = bool(val.get("discharge_blocked"))
    ctx.needs_hitl = bool(val.get("needs_hitl"))

    docs = st.session_state.get("doc_count")
    if isinstance(docs, int):
        ctx.doc_count = docs
    elif pid:
        # Page 1 sets doc_count while rendering — the rail draws first, so on the
        # very first run count intake files directly instead of showing nothing.
        ctx.doc_count = _intake_file_count(pid)
    ctx.indexed = bool(pipeline.get("indexed"))
    ctx.has_summary = st.session_state.get("summary") is not None

    steps = pipeline_step_states(
        pipeline or None,
        validation=st.session_state.get("validation"),
        summary=st.session_state.get("summary"),
    )
    ctx.stages_done = sum(1 for _k, _l, state, _m in steps if state == "done")
    active = [label for _k, label, state, _m in steps if state in {"active", "blocked"}]
    if ctx.has_summary:
        ctx.stage_note = "Summary generated"
    elif ctx.blocked:
        ctx.stage_note = "Held at release gate"
    elif active:
        ctx.stage_note = f"At {active[0]}"
    elif ctx.processed:
        ctx.stage_note = "Pipeline complete"
    else:
        ctx.stage_note = "Not started"

    ctx.trace_id = _clean(st.session_state.get("trace_id"))
    if ctx.trace_id or val:
        ctx.trace_url = _case_trace_url(val or None, ctx.trace_id)
    ctx.rules_version = _clean(val.get("rules_version"))
    ctx.badges = _nav_badges(ctx)
    return ctx


def _nav_badges(ctx: RailContext) -> dict[int, tuple[str, str]]:
    """1-based nav index → (badge text, tone). Admin pages never carry badges."""
    badges: dict[str, tuple[str, str]] = {}

    if ctx.doc_count:
        badges["Document Viewer"] = (str(ctx.doc_count), "mute")

    if ctx.processed:
        if ctx.critical_count:
            badges["Validation Report"] = (str(ctx.critical_count), "bad")
        elif ctx.findings_total:
            badges["Validation Report"] = (str(ctx.findings_total), "warn")
        else:
            badges["Validation Report"] = ("OK", "ok")

        if ctx.open_corrections:
            tone = "bad" if ctx.blocking_count else "warn"
            badges["Corrections"] = (str(ctx.open_corrections), tone)
        elif ctx.needs_hitl or ctx.blocked:
            badges["Corrections"] = ("!", "warn")

    if ctx.indexed:
        badges["RAG Q&A"] = ("ON", "teal")

    if ctx.has_summary:
        badges["Discharge Summary"] = ("✓", "ok")
    elif ctx.processed and (ctx.blocked or ctx.needs_hitl):
        badges["Discharge Summary"] = ("Hold", "mute")

    order = {page: i + 1 for i, page in enumerate(PAGES)}
    return {
        order[page]: (text, tone)
        for page, (text, tone) in badges.items()
        if page in order and page not in ADMIN_PAGES
    }


# ------------------------------------------------------------- dynamic CSS


def nav_decoration_css(badges: dict[int, tuple[str, str]]) -> str:
    """Per-item icons, count badges and the admin group label.

    Streamlit's radio gives no per-option hook, so the rail decorates each row
    positionally from ``PAGES`` — same tuple the widget is built from.
    """
    root = 'section[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label'
    rules: list[str] = []

    for idx, page in enumerate(PAGES, start=1):
        icon = NAV_ICONS.get(page, "•")
        rules.append(f'{root}:nth-child({idx})::before {{ content: "{escape(icon)}"; }}')

    admin_index = next(
        (i for i, page in enumerate(PAGES, start=1) if page in ADMIN_PAGES), None
    )
    if admin_index:
        rules.append(
            f"{root}:nth-child({admin_index}) {{ margin-top: 2.1rem !important; }}"
        )
        rules.append(
            f'{root}:nth-child({admin_index})::after {{'
            '  content: "Administration";'
            "  position: absolute; top: -1.45rem; left: 0.2rem;"
            "  font-size: 0.62rem; font-weight: 800; letter-spacing: 0.15em;"
            "  text-transform: uppercase; color: #5c6b81;"
            "  background: none; border: none; padding: 0; margin: 0;"
            "  pointer-events: none;"
            "}"
        )

    for idx, (text, tone) in sorted(badges.items()):
        label = _badge_text(text)
        if not label or idx == admin_index:
            continue
        bg, fg, border = _BADGE_TONES.get(tone, _BADGE_TONES["mute"])
        rules.append(
            f'{root}:nth-child({idx})::after {{'
            f'  content: "{label}";'
            "  position: static; margin-left: auto; flex: 0 0 auto;"
            "  min-width: 1.35rem; padding: 0.05rem 0.4rem;"
            "  border-radius: 999px; text-align: center;"
            "  font-size: 0.66rem; font-weight: 800; letter-spacing: 0.02em;"
            "  line-height: 1.5;"
            f"  background: {bg}; color: {fg}; border: 1px solid {border};"
            "}"
        )

    return "<style>" + "\n".join(rules) + "</style>"


# ------------------------------------------------------------------- markup


def brand_html() -> str:
    return (
        '<div class="sbx-brand">'
        '<span class="sbx-brand-mark" aria-hidden="true">✚</span>'
        '<span class="sbx-brand-text">'
        '<span class="sbx-brand-title">Discharge AI</span>'
        '<span class="sbx-brand-sub">Clinical handoff</span>'
        "</span></div>"
    )


def _chip(label: str, tone: str) -> str:
    return f'<span class="sbx-chip tone-{escape(tone)}">{escape(label)}</span>'


def patient_html(ctx: RailContext) -> str:
    if not ctx.patient_id:
        return (
            '<div class="sbx-card sbx-patient sbx-patient-empty">'
            '<div class="sbx-empty-title">No patient selected</div>'
            '<div class="sbx-empty-body">Search by ID or name at the top of the '
            "page, or upload a new chart.</div></div>"
        )

    sub_bits = [ctx.patient_id]
    if ctx.age:
        sub_bits.append(ctx.age)
    if ctx.gender:
        sub_bits.append(ctx.gender.title())

    meta_rows: list[tuple[str, str]] = []
    if ctx.ward or ctx.bed:
        location = " · ".join(
            x for x in (f"Ward {ctx.ward}" if ctx.ward else "", f"Bed {ctx.bed}" if ctx.bed else "") if x
        )
        meta_rows.append(("Location", location))
    if ctx.attending:
        meta_rows.append(("Attending", ctx.attending))
    if ctx.admitted:
        meta_rows.append(("Admitted", ctx.admitted))
    if not meta_rows:
        # Pre-pipeline there is no extracted chart yet — show what we do know.
        if ctx.doc_count:
            meta_rows.append(("Intake", f"{ctx.doc_count} file(s) on record"))
        else:
            meta_rows.append(("Intake", "No documents yet"))

    meta_html = "".join(
        f'<div class="sbx-meta-row">'
        f'<span class="sbx-meta-k">{escape(k)}</span>'
        f'<span class="sbx-meta-v" title="{escape(v)}">{escape(v)}</span></div>'
        for k, v in meta_rows
    )

    chips = ""
    if ctx.processed:
        risk = f"{ctx.risk_level} risk" if ctx.risk_level else "Risk —"
        chips = _chip(risk, ctx.risk_tone) + _chip(ctx.gate_label, ctx.gate_tone)
    else:
        chips = _chip("Awaiting pipeline", "mute")

    return (
        '<div class="sbx-card sbx-patient">'
        '<div class="sbx-card-label">Active patient</div>'
        '<div class="sbx-patient-top">'
        f'<span class="sbx-avatar">{escape(ctx.initials)}</span>'
        '<span class="sbx-patient-id">'
        f'<span class="sbx-patient-name" title="{escape(ctx.patient_name)}">'
        f"{escape(ctx.patient_name)}</span>"
        f'<span class="sbx-patient-sub">{escape(" · ".join(sub_bits))}</span>'
        "</span></div>"
        f'<div class="sbx-meta">{meta_html}</div>'
        f'<div class="sbx-chips">{chips}</div>'
        "</div>"
    )


def progress_html(ctx: RailContext) -> str:
    if not ctx.patient_id:
        return ""
    done = max(0, min(PIPELINE_TOTAL, ctx.stages_done))
    pct = round(done / PIPELINE_TOTAL * 100)
    tone = "bad" if ctx.blocked else "warn" if ctx.needs_hitl else "ok" if done else "mute"
    return (
        '<div class="sbx-progress">'
        '<div class="sbx-progress-head">'
        "<span>Case progress</span>"
        f'<span class="sbx-progress-count">{done}<span class="sbx-progress-total">'
        f"/{PIPELINE_TOTAL}</span></span>"
        "</div>"
        f'<div class="sbx-bar"><span class="sbx-bar-fill tone-{tone}" '
        f'style="width:{pct}%"></span></div>'
        f'<div class="sbx-progress-foot">{escape(ctx.stage_note)}</div>'
        "</div>"
    )


def _next_action(ctx: RailContext) -> tuple[str, str, str, str]:
    """(tone, icon, title, body) — the one thing to do next."""
    if not ctx.patient_id:
        return ("info", "◇", "Pick a patient", "Search above or upload a new chart to start.")
    if not ctx.processed:
        return (
            "info",
            "▸",
            "Ready to process",
            "Open Document Viewer and run Process patient.",
        )
    if ctx.blocked:
        detail = (
            f"{ctx.blocking_count} blocking gap(s) to clear"
            if ctx.blocking_count
            else "Clear the critical findings"
        )
        return ("bad", "!", "Discharge blocked", f"{detail} in Corrections.")
    if ctx.needs_hitl:
        detail = (
            f"{ctx.open_corrections} item(s) awaiting your review"
            if ctx.open_corrections
            else "Confirm the chart in Corrections"
        )
        return ("warn", "⚠", "Clinician review needed", f"{detail}.")
    if ctx.has_summary:
        return ("ok", "✓", "Cleared for discharge", "Summary is ready to review and export.")
    return ("ok", "✓", "Gate open", "No blocks — generate the discharge summary.")


def alert_html(ctx: RailContext) -> str:
    tone, icon, title, body = _next_action(ctx)
    return (
        f'<div class="sbx-alert tone-{tone}">'
        f'<span class="sbx-alert-icon" aria-hidden="true">{escape(icon)}</span>'
        '<span class="sbx-alert-text">'
        f'<span class="sbx-alert-title">{escape(title)}</span>'
        f'<span class="sbx-alert-body">{escape(body)}</span>'
        "</span></div>"
    )


def footer_html(ctx: RailContext) -> str:
    """Trace chip — a link into LangFuse when configured, plain text otherwise."""
    trace = ctx.trace_id[-8:] if ctx.trace_id else "—"
    rules = ctx.rules_version[:14] if ctx.rules_version else "—"
    title = f"Trace {ctx.trace_id or '—'}"
    if ctx.trace_url:
        chip = (
            f'<a class="sbx-foot-mono sbx-foot-link" href="{escape(ctx.trace_url)}" '
            f'target="_blank" rel="noopener noreferrer" '
            f'title="{escape(title)} — open in LangFuse">'
            f'{escape(trace)}<span class="sbx-foot-ext" aria-hidden="true">↗</span></a>'
        )
        note = "Rules {} · open trace in LangFuse".format(escape(rules))
    else:
        chip = f'<code class="sbx-foot-mono" title="{escape(title)}">{escape(trace)}</code>'
        note = "Rules {} · audit trail retained".format(escape(rules))
    return (
        '<div class="sbx-foot">'
        '<div class="sbx-foot-row">'
        '<span class="sbx-dot" aria-hidden="true"></span>'
        "<span>Session live</span>"
        f"{chip}"
        "</div>"
        f'<div class="sbx-foot-note">{note}</div>'
        "</div>"
    )


# ------------------------------------------------------------------- render


def render_sidebar(*, on_navigate: Callable[[str], None] | None = None) -> str:
    """Draw the rail and return the selected page key."""
    ctx = collect_context()
    st.markdown(nav_decoration_css(ctx.badges), unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(brand_html(), unsafe_allow_html=True)
        st.markdown(patient_html(ctx), unsafe_allow_html=True)
        progress = progress_html(ctx)
        if progress:
            st.markdown(progress, unsafe_allow_html=True)

        st.markdown(
            '<div class="sbx-group-label">Clinical workflow</div>', unsafe_allow_html=True
        )
        current = st.session_state.get("page")
        page = st.radio(
            "Navigation",
            list(PAGES),
            index=list(PAGES).index(current) if current in PAGES else 0,
            format_func=nav_label,
            label_visibility="collapsed",
            key="nav_radio",
        )
        st.markdown(alert_html(ctx), unsafe_allow_html=True)
        st.markdown(footer_html(ctx), unsafe_allow_html=True)

    if on_navigate is not None:
        on_navigate(page)
    return page
