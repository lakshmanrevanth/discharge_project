"""Corrections page — soft elicitation (HITL-1) + critical fixes (HITL-2).

Clinical rules stay in agents/MCP. This page only:
  - shows Critical findings with fix editors
  - edits medications / bill / follow-up / discharge approval
  - batches soft elicitation (accept / decline / cancel)
  - re-runs extract → normalize → validate with overlays applied
"""

from __future__ import annotations

import asyncio
import html
import re
from typing import Any

import pandas as pd
import streamlit as st

from dashboard import bridge
from dashboard.components.common import load_feedback, save_feedback
from dashboard.elicitation_callback import stage_elicitation_response
from dashboard.state import append_feedback
from dashboard.ui_chrome import finding_card_html
from mcp_servers.primary.elicitation import TYPE_HINTS


def _meds_for_patient(pid: str, case: dict[str, Any], feedback: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Meds for THIS patient — live Process case first; never auto-load disk feedback.

    ``feedback`` is accepted for call-site compatibility but ignored for the table.
    """
    del feedback  # disk drafts must not outrank a fresh Process extract
    pid = str(pid or "").strip().upper()
    epoch = st.session_state.get("meds_editor_epoch")
    if (
        st.session_state.get("edited_meds_pid") == pid
        and st.session_state.get("edited_meds") is not None
        and st.session_state.get("edited_meds_epoch") == epoch
    ):
        return list(st.session_state.get("edited_meds") or [])
    case_meds = list(case.get("medications") or [])
    if case_meds:
        return case_meds
    # Last resort for new patients: seed HITL table from Mock EHR
    return bridge.fetch_ehr_medications(pid)


def _store_edited_meds(pid: str, meds: list[dict[str, Any]]) -> None:
    """Persist med edits scoped to the active patient_id + Process epoch."""
    st.session_state["edited_meds"] = meds
    st.session_state["edited_meds_pid"] = str(pid or "").strip().upper()
    st.session_state["edited_meds_epoch"] = st.session_state.get("meds_editor_epoch")


def _med_rows_equal(a: list[Any], b: list[Any]) -> bool:
    """Compare med tables ignoring blank rows and key aliases."""

    def _norm(rows: list[Any]) -> list[tuple[str, str, str, str, str]]:
        out: list[tuple[str, str, str, str, str]] = []
        for m in rows:
            if not isinstance(m, dict):
                continue
            name = (m.get("medicine_name") or m.get("name") or "").strip()
            if not name:
                continue
            out.append(
                (
                    name.lower(),
                    str(m.get("strength") or "").strip().lower(),
                    str(m.get("frequency") or "").strip().lower(),
                    str(m.get("route") or "").strip().lower(),
                    str(m.get("period") or "").strip().lower(),
                )
            )
        return out

    return _norm(a) == _norm(b)


# Extensible Critical → editor map. Unknown rules → panel "other".
CRITICAL_FIX: dict[str, dict[str, str]] = {
    "allergy_contradiction_check": {
        "title": "Allergy contradiction",
        "fix": "Remove the conflicting drug(s) from Medications (keep the allergy). Then Re-run.",
        "panel": "allergy",
    },
    "high_risk_med_missing_in_ehr": {
        "title": "High-risk medication",
        "fix": "Remove the high-risk drug from Medications, or correct the chart so EHR has the order. Then Re-run.",
        "panel": "allergy",
    },
    "bill_settlement_check": {
        "title": "Bill settlement",
        "fix": "Set payment status to PAID after settlement. Then Re-run.",
        "panel": "bill",
    },
    "follow_up_missing_check": {
        "title": "Follow-up missing",
        "fix": "Enter a follow-up appointment. Then Re-run.",
        "panel": "followup",
    },
    "discharge_approval_check": {
        "title": "Discharge approval",
        "fix": "Confirm discharge is approved. Then Re-run.",
        "panel": "approval",
    },
}

# Soft elicit fields already covered by a Critical panel — edit once.
SOFT_COVERED_BY_PANEL: dict[str, str] = {
    "follow_up_appointment": "followup",
    "allergies": "allergy",
}

_MED_IN_MSG_RE = re.compile(
    r"(?:medication|medicine|drug|includes)\s+'([^']+)'",
    re.IGNORECASE,
)


def _esc(text: Any) -> str:
    return html.escape(str(text or ""), quote=True)


def critical_issues(findings: list[Any]) -> list[dict[str, Any]]:
    """Build Critical checklist from live findings (safe for unknown rule_ids)."""
    issues: list[dict[str, Any]] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        rule = str(f.get("rule_id") or "unknown")
        if rule.startswith("elicitation_"):
            continue
        sev = str(f.get("severity") or "").lower()
        # Critical clinical blocks: severity Critical, or any blocking EHR check
        if sev != "critical" and not bool(f.get("blocking")):
            continue
        meta = CRITICAL_FIX.get(rule) or {
            "title": rule.replace("_", " ").title(),
            "fix": "Edit the related fields below, then Re-run validation.",
            "panel": "other",
        }
        flagged: list[str] = []
        raw_flagged = f.get("flagged_medications") or []
        if isinstance(raw_flagged, list):
            flagged = [str(x).strip() for x in raw_flagged if str(x).strip()]
        if not flagged:
            m = _MED_IN_MSG_RE.search(str(f.get("message") or ""))
            if m:
                flagged = [m.group(1)]
        fix = meta["fix"]
        if flagged and rule in {
            "allergy_contradiction_check",
            "high_risk_med_missing_in_ehr",
        }:
            fix = f"Remove or change: {', '.join(flagged)}. Then Re-run validation."
        issues.append(
            {
                "rule_id": rule,
                "title": meta["title"],
                "fix": fix,
                "panel": meta["panel"],
                "message": str(f.get("message") or ""),
                "field": str(f.get("field") or ""),
                "flagged_medications": flagged,
            }
        )
    return issues


def _issue_card_html(issue: dict[str, Any]) -> str:
    return (
        f'<div class="hitl-issue-card critical">'
        f'<div class="hitl-issue-top">'
        f'<div class="hitl-issue-title">{_esc(issue.get("title"))}</div>'
        f'<span class="chip badge-bad">Critical</span>'
        f"</div>"
        f'<div class="hitl-kv">'
        f'<div class="k">Rule</div><div class="v mono">{_esc(issue.get("rule_id"))}</div>'
        f'<div class="k">Finding</div><div class="v">{_esc(issue.get("message"))}</div>'
        f'<div class="k">Fix</div><div class="v">{_esc(issue.get("fix"))}</div>'
        f"</div></div>"
    )


def _normalize_med_rows(default_meds: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for m in default_meds:
        if not isinstance(m, dict):
            continue
        rows.append(
            {
                "medicine_name": m.get("medicine_name") or m.get("name") or "",
                "strength": m.get("strength") or "",
                "frequency": m.get("frequency") or "",
                "route": m.get("route") or "",
                "period": m.get("period") or "",
            }
        )
    if not rows:
        rows = [
            {
                "medicine_name": "",
                "strength": "",
                "frequency": "",
                "route": "",
                "period": "",
            }
        ]
    return rows


def _apply_overlays(
    ext: dict[str, Any],
    *,
    case: dict[str, Any] | None,
    edited_meds: list[dict[str, Any]],
    elicit_values: dict[str, Any],
) -> dict[str, Any]:
    """Merge Corrections edits onto a fresh extraction before normalize/validate."""
    out = dict(ext or {})
    discharge = dict(out.get("discharge") or {})
    bill = dict(out.get("bill") or {}) if isinstance(out.get("bill"), dict) else {}

    meds = [
        {
            "medicine_name": (m.get("medicine_name") or m.get("name") or "").strip(),
            "name": (m.get("medicine_name") or m.get("name") or "").strip(),
            "strength": m.get("strength") or "",
            "frequency": m.get("frequency") or "",
            "route": m.get("route") or "",
            "period": m.get("period") or "",
        }
        for m in edited_meds
        if (m.get("medicine_name") or m.get("name") or "").strip()
    ]
    if meds:
        discharge["medications"] = meds

    case = case or {}
    follow = case.get("follow_up_appointment")
    if follow not in (None, ""):
        discharge["follow_up_appointment"] = follow
        discharge["follow_up_appointments"] = follow

    if "discharge_ok" in case:
        approved = bool(case.get("discharge_ok"))
        discharge["discharge_approved"] = approved

    if case.get("allergies") is not None:
        allergies = case.get("allergies") or []
        if isinstance(allergies, str):
            allergies = [p.strip() for p in allergies.split(",") if p.strip()]
        discharge["allergies"] = list(allergies)
        discharge["adr_allergy_info"] = list(allergies)

    case_bill = case.get("bill") if isinstance(case.get("bill"), dict) else {}
    if case_bill:
        bill = {**bill, **case_bill}
        # Validator compares lowercase "paid"
        if bill.get("payment_status"):
            bill["payment_status"] = str(bill["payment_status"]).strip()

    for key, val_e in (elicit_values or {}).items():
        if val_e in ("", None):
            continue
        if key in {"consulting_doctors", "allergies"} and isinstance(val_e, str):
            discharge[key] = [p.strip() for p in val_e.split(",") if p.strip()]
            if key == "allergies":
                discharge["adr_allergy_info"] = discharge[key]
        else:
            discharge[key] = val_e

    out["discharge"] = discharge
    if bill or "bill" in out:
        out["bill"] = bill
    return out


def page_corrections(
    *,
    page_header,
    sync_pipeline_after_hitl,
) -> None:
    page_header(
        "Corrections",
        "Fix critical blocks and soft gaps, then re-run validation.",
    )

    pid = str(st.session_state.patient_id)
    val = st.session_state.validation
    case = st.session_state.case
    if case is None:
        case = {}
        st.session_state.case = case
    feedback = load_feedback(pid) or {}

    if not val and not case:
        st.info("Process the patient on Document Viewer first.")
        return

    findings = list((val or {}).get("findings") or [])
    issues = critical_issues(findings)
    open_panels = {i["panel"] for i in issues}

    # ---- Gate snapshot ----
    if val:
        risk = (val.get("risk") or {}).get("level") or val.get("risk_level") or "—"
        st.caption(
            f"Current · risk={risk} · blocked={bool(val.get('discharge_blocked'))} · "
            f"needs_hitl={bool(val.get('needs_hitl'))} · "
            f"elicitation={val.get('elicitation_outcome') or '—'} · "
            f"critical={len(issues)}"
        )

    # ---- Critical issues (HITL-2) ----
    st.markdown(
        '<div class="section-label">Critical issues</div>',
        unsafe_allow_html=True,
    )
    if not issues:
        st.markdown(
            '<div class="empty-state empty-ok">'
            '<span class="empty-icon" aria-hidden="true">✓</span>'
            '<span class="empty-text">No critical blocks on the latest validation.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(
            "These block discharge until fixed. Edit the fields below, then Re-run validation."
        )
        for issue in issues:
            st.markdown(_issue_card_html(issue), unsafe_allow_html=True)

        # --- Allergy / high-risk med panel ---
        if "allergy" in open_panels:
            st.markdown("**Medications (allergy / high-risk)**")
            flagged: list[str] = []
            for i in issues:
                for name in i.get("flagged_medications") or []:
                    if name not in flagged:
                        flagged.append(name)
            if flagged:
                st.warning("Flagged: " + ", ".join(flagged))
                st.caption(
                    "Removing allergy-conflict drugs from discharge is intentional; "
                    "Re-run will not treat those EHR orders as med omissions."
                )
                if st.button(
                    "Remove flagged medications",
                    key=f"rm_flagged_{pid}",
                ):
                    current = _meds_for_patient(pid, case, feedback)
                    lower = {n.lower() for n in flagged}
                    kept = [
                        m
                        for m in current
                        if (m.get("medicine_name") or m.get("name") or "").strip().lower()
                        not in lower
                    ]
                    _store_edited_meds(pid, kept)
                    case["medications"] = kept
                    case["_meds_source"] = "hitl"
                    st.success(f"Removed {len(current) - len(kept)} row(s). Re-run validation.")
                    st.rerun()

        # --- Bill panel ---
        if "bill" in open_panels:
            st.markdown("**Bill settlement**")
            bill = case.get("bill") if isinstance(case.get("bill"), dict) else {}
            if not bill and isinstance((val or {}).get("bill"), dict):
                bill = dict(val.get("bill") or {})
            b1, b2 = st.columns(2)
            bill_id = b1.text_input(
                "Bill ID",
                value=str(bill.get("bill_id") or ""),
                key=f"crit_bill_id_{pid}",
            )
            current = str(bill.get("payment_status") or "UNKNOWN").strip().upper() or "UNKNOWN"
            choices = ["PAID", "UNPAID", "PENDING", "PARTIAL", "UNKNOWN"]
            if current not in choices:
                choices = [current, *choices]
            payment_status = b2.selectbox(
                "Payment status",
                choices,
                index=choices.index(current),
                key=f"crit_bill_pay_{pid}",
            )
            amount = bill.get("total_amount")
            currency = str(bill.get("currency") or "")
            if amount is not None:
                st.caption(f"Amount on file: {amount} {currency}".strip())
            case["bill"] = {**bill, "bill_id": bill_id, "payment_status": payment_status}

        # --- Follow-up panel ---
        if "followup" in open_panels:
            st.markdown("**Follow-up appointment**")
            case["follow_up_appointment"] = st.text_input(
                "Follow-up appointment",
                value=str(case.get("follow_up_appointment") or ""),
                key=f"crit_followup_{pid}",
                placeholder="e.g. Cardiology clinic in 2 weeks",
            )

        # --- Discharge approval panel ---
        if "approval" in open_panels:
            st.markdown("**Discharge approval**")
            case["discharge_ok"] = st.checkbox(
                "Discharge approved by treating physician",
                value=bool(case.get("discharge_ok")),
                key=f"crit_discharge_ok_{pid}",
            )

        # --- Unknown critical rules ---
        if "other" in open_panels:
            st.info(
                "Additional critical findings need a field edit above or in the "
                "medication table, then Re-run validation."
            )

    st.session_state.case = case

    # ---- Medication table ----
    st.markdown('<div class="section-label">Medication table</div>', unsafe_allow_html=True)
    default_meds = _meds_for_patient(pid, case, feedback)
    source = str(case.get("_meds_source") or "")
    if default_meds and source == "ehr":
        st.caption(
            "Seeded from Mock EHR (discharge extract had no meds). "
            "Edit to match the discharge chart, then Re-run validation."
        )
    elif default_meds:
        st.caption("Edit rows here (also used to clear allergy / high-risk meds).")
    else:
        st.caption(
            "No medications found yet — add rows manually, or Process the patient "
            "after uploading a discharge note with a prescription table."
        )

    rows = _normalize_med_rows(list(default_meds))
    epoch = st.session_state.get("meds_editor_epoch") or 0
    edited = st.data_editor(
        pd.DataFrame(rows),
        num_rows="dynamic",
        use_container_width=True,
        key=f"meds_editor_{pid}_{epoch}",
        column_config={
            "medicine_name": st.column_config.TextColumn("Medicine", required=False),
            "strength": st.column_config.TextColumn("Strength"),
            "frequency": st.column_config.TextColumn("Frequency"),
            "route": st.column_config.TextColumn("Route"),
            "period": st.column_config.TextColumn("Period"),
        },
    )
    meds_out = edited.to_dict(orient="records")
    # Only persist when the reviewer changed rows — never re-poison case from
    # a stale Streamlit widget or a no-op render after Process.
    if not _med_rows_equal(meds_out, rows):
        _store_edited_meds(pid, meds_out)
        case["medications"] = [
            m for m in meds_out if (m.get("medicine_name") or "").strip()
        ]
        case["_meds_source"] = "hitl"
        st.session_state.case = case
    elif st.session_state.get("edited_meds_pid") == pid and st.session_state.get(
        "edited_meds_epoch"
    ) == epoch:
        # Keep case aligned with in-session edits (e.g. Remove flagged)
        kept = [
            m
            for m in (st.session_state.get("edited_meds") or [])
            if (m.get("medicine_name") or m.get("name") or "").strip()
        ]
        if kept:
            case["medications"] = kept
            case["_meds_source"] = "hitl"
            st.session_state.case = case

    # ---- Soft elicitation (HITL-1) — skip fields covered by Critical panels ----
    st.markdown(
        '<div class="section-label">Elicitation response form</div>',
        unsafe_allow_html=True,
    )
    missing = list(
        (val or {}).get("missing_fields")
        or (val or {}).get("missing_soft")
        or feedback.get("missing_fields")
        or []
    )
    missing = [
        f for f in missing if SOFT_COVERED_BY_PANEL.get(f) not in open_panels
    ]
    extra = st.multiselect(
        "Add fields to the form",
        options=sorted(
            set(TYPE_HINTS)
            | {
                "address",
                "gender",
                "age",
                "ward",
                "bed_no",
                "attending_physician",
                "consulting_doctors",
                "follow_up_appointment",
                "discharge_instructions",
                "allergies",
                "admission_date",
                "discharge_date",
            }
        ),
        default=[],
        key=f"elicit_extra_{pid}",
    )
    fields = [
        f
        for f in dict.fromkeys([*missing, *extra])
        if SOFT_COVERED_BY_PANEL.get(f) not in open_panels
    ]

    if not fields:
        st.info("No soft elicitation fields needed (or they are covered above).")
    else:
        st.caption("One batched form for non-blocking gaps (SSoT §3.7).")

    elicited: dict[str, Any] = {}
    cols = st.columns(2)
    for i, field in enumerate(fields):
        with cols[i % 2]:
            if TYPE_HINTS.get(field) is int:
                elicited[field] = st.number_input(
                    field, value=0, step=1, key=f"elicit_{pid}_{field}"
                )
            else:
                seed = ""
                if case.get(field) not in (None, "", []):
                    raw = case.get(field)
                    seed = (
                        ", ".join(str(x) for x in raw)
                        if isinstance(raw, list)
                        else str(raw)
                    )
                elicited[field] = st.text_input(
                    field, value=seed, key=f"elicit_{pid}_{field}"
                )

    e1, e2, e3 = st.columns(3)
    if e1.button("Accept elicitation", type="primary", key=f"accept_{pid}"):
        clean = {k: v for k, v in elicited.items() if v not in ("", None)}
        # Include critical-panel soft overlaps in the staged accept payload
        if "followup" in open_panels and case.get("follow_up_appointment"):
            clean["follow_up_appointment"] = case["follow_up_appointment"]
        stage_elicitation_response("accept", clean)
        st.session_state["elicitation_values"] = clean
        st.session_state["elicitation_values_pid"] = pid
        save_feedback(
            pid,
            {
                "elicitation_action": "accept",
                "elicited_values": clean,
                "missing_fields": fields,
            },
        )
        append_feedback(
            {
                "patient_id": pid,
                "action": "elicitation_accept",
                "fields": list(clean.keys()),
            }
        )
        st.success(f"Staged ACCEPT with {len(clean)} field(s). Re-run validation to apply.")
    if e2.button("Decline elicitation", key=f"decline_{pid}"):
        stage_elicitation_response("decline")
        save_feedback(
            pid, {"elicitation_action": "decline", "missing_fields": fields}
        )
        append_feedback({"patient_id": pid, "action": "elicitation_decline"})
        st.warning("Staged DECLINE — case stays on mandatory review.")
    if e3.button("Cancel elicitation", key=f"cancel_{pid}"):
        stage_elicitation_response("cancel")
        save_feedback(
            pid, {"elicitation_action": "cancel", "missing_fields": fields}
        )
        append_feedback({"patient_id": pid, "action": "elicitation_cancel"})
        st.warning("Staged CANCEL — case stays on mandatory review.")

    # ---- Risk override & approval note (audit only) ----
    st.markdown(
        '<div class="section-label">Risk override & approval</div>',
        unsafe_allow_html=True,
    )
    current_risk = (
        (val or {}).get("risk", {}) or {}
    ).get("level") or (val or {}).get("risk_level") or "low"
    override = st.selectbox(
        "Risk label override",
        ["(no override)", "low", "medium", "high"],
        index=0,
        key=f"risk_override_box_{pid}",
    )
    approval = st.radio(
        "Approval decision",
        ["Pending", "Approve", "Request changes", "Reject"],
        horizontal=True,
        index=0,
        key=f"approval_{pid}",
    )
    note = st.text_area(
        "Correction note",
        value=st.session_state.get("approval_note") or "",
        height=100,
        key=f"note_{pid}",
    )
    st.session_state.approval_note = note

    if st.button("Save feedback", type="primary", key=f"save_fb_{pid}"):
        payload = {
            "medications": _meds_for_patient(pid, case, feedback),
            "bill": case.get("bill"),
            "follow_up_appointment": case.get("follow_up_appointment"),
            "discharge_ok": case.get("discharge_ok"),
            "risk_override": None if override.startswith("(") else override,
            "approval": approval,
            "approval_note": note,
            "elicited_values": st.session_state.get("elicitation_values") or {},
            "original_risk_level": current_risk,
            "original_discharge_blocked": (val or {}).get("discharge_blocked"),
            "critical_rules": [i["rule_id"] for i in issues],
            "pipeline_trace_id": st.session_state.get("trace_id"),
        }
        path = save_feedback(pid, payload)
        st.session_state["hitl_approval"] = approval
        st.session_state["risk_override"] = payload["risk_override"] or "Keep model"
        append_feedback({"patient_id": pid, "action": "save_feedback", **payload})
        st.success(f"Saved `{path}`")

    # ---- Re-run validation ----
    st.markdown(
        '<div class="section-label">Re-run validation</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Applies critical fixes + staged elicitation, then re-validates and "
        "re-indexes RAG with the corrected discharge facts. "
        "Requires Primary MCP, Secondary MCP, and Mock EHR."
    )

    if st.button("Re-run validation", type="primary", key=f"rerun_{pid}"):
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

            working_case = dict(st.session_state.case or {})
            # Ensure critical widget values are on the case
            if "bill" in open_panels and working_case.get("bill"):
                pass  # already set above
            # Only overlay meds edited for THIS patient (never another case)
            edited_meds = _meds_for_patient(pid, working_case, feedback)
            elicit_values = dict(st.session_state.get("elicitation_values") or {})
            if st.session_state.get("elicitation_values_pid") != pid:
                elicit_values = {}
            # Disk feedback fallback (Accept may have been last session)
            fb_elicit = feedback.get("elicited_values") if isinstance(feedback, dict) else None
            if isinstance(fb_elicit, dict) and feedback.get("elicitation_action") == "accept":
                for k, v in fb_elicit.items():
                    if v not in ("", None) and k not in elicit_values:
                        elicit_values[k] = v
            # Re-run should use the form on this page even if Accept was not clicked
            form_vals = {
                k: v for k, v in (elicited or {}).items() if v not in ("", None)
            }
            if form_vals:
                elicit_values = {**elicit_values, **form_vals}
            if working_case.get("follow_up_appointment"):
                elicit_values.setdefault(
                    "follow_up_appointment", working_case["follow_up_appointment"]
                )
            if "followup" in open_panels and working_case.get("follow_up_appointment"):
                elicit_values.setdefault(
                    "follow_up_appointment", working_case["follow_up_appointment"]
                )
            if elicit_values:
                stage_elicitation_response("accept", elicit_values)
                st.session_state["elicitation_values"] = elicit_values
                st.session_state["elicitation_values_pid"] = pid
            else:
                # Avoid silent auto-decline on Re-run when reviewer already cleared
                # clinical blocks but left soft fields empty — still need Accept
                # or values. Prefer decline only when nothing was staged.
                pass

            async def _run():
                from shared.tracing.langfuse import case_trace

                # Continue the case's LangFuse trace (HITL re-run, SSoT §9) so
                # these spans stay reachable from the same trace URL.
                existing_tid = str(st.session_state.get("trace_id") or "") or None
                with case_trace(pid, existing=existing_tid, host_name="HITL Re-run"):
                    status.write("Extract…")
                    ext = await run_extraction(pid)
                    if not isinstance(ext, dict):
                        ext = {}
                    # Prefer this patient's case meds when HITL table is empty
                    overlay_meds = edited_meds
                    if not overlay_meds:
                        overlay_meds = list(working_case.get("medications") or [])
                    ext = _apply_overlays(
                        ext,
                        case=working_case,
                        edited_meds=overlay_meds,
                        elicit_values=elicit_values,
                    )
                    status.write("Normalize…")
                    norm = await run_normalization(pid, ext)
                    token = set_elicitation_handler(streamlit_elicitation_handler)
                    try:
                        status.write("Validate (with elicitation + critical overlays)…")
                        report = await run_validation(pid, norm)
                    finally:
                        reset_elicitation_handler(token)
                return norm, report

            norm, report = asyncio.run(_run())
            validation = bridge.normalize_validation(report) or {}
            # Prefer post-elicitation extraction (MCP callback fills) for RAG case
            case_out = bridge.case_after_validation(
                norm, report if isinstance(report, dict) else None
            )
            # Keep reviewer edits on the working case (this patient only)
            meds = [
                m
                for m in edited_meds
                if (m.get("medicine_name") or "").strip()
            ]
            if meds:
                case_out["medications"] = meds
                _store_edited_meds(pid, meds)
            if working_case.get("bill"):
                case_out["bill"] = working_case["bill"]
            if working_case.get("follow_up_appointment") not in (None, ""):
                case_out["follow_up_appointment"] = working_case[
                    "follow_up_appointment"
                ]
            if "discharge_ok" in working_case:
                case_out["discharge_ok"] = bool(working_case.get("discharge_ok"))

            # Elicitation answers must land on the case for RAG (not only validate)
            for key, val_e in (elicit_values or {}).items():
                if val_e in ("", None):
                    continue
                if key in {"consulting_doctors", "allergies"} and isinstance(val_e, str):
                    case_out[key] = [
                        p.strip() for p in val_e.split(",") if p.strip()
                    ]
                else:
                    case_out[key] = val_e

            st.session_state.summary = None
            index_out = bridge.reindex_after_hitl(case_out)
            indexed_ok = bool(index_out.get("indexed"))
            sync_pipeline_after_hitl(
                case=case_out,
                validation=validation,
                summary=None,
                indexed=indexed_ok,
            )
            status.update(label="Validation complete", state="complete")
            remaining = critical_issues(list(validation.get("findings") or []))
            st.success(
                f"risk={validation.get('risk', {}).get('level')} "
                f"score={validation.get('risk', {}).get('score')} "
                f"blocked={validation.get('discharge_blocked')} "
                f"critical_left={len(remaining)}"
            )
            if indexed_ok:
                st.caption(f"RAG re-indexed with Corrections · {index_out.get('indexed_chunks')}")
            else:
                st.warning(
                    f"Validation updated but RAG re-index failed: {index_out.get('error')}. "
                    "Use Ensure FAISS index on RAG Q&A."
                )
            append_feedback(
                {
                    "patient_id": pid,
                    "action": "rerun_validation",
                    "risk_level": (validation.get("risk") or {}).get("level"),
                    "discharge_blocked": validation.get("discharge_blocked"),
                    "critical_left": [i["rule_id"] for i in remaining],
                }
            )
            st.rerun()
        except Exception as exc:
            status.update(label="Re-run failed", state="error")
            st.error(str(exc))

    # ---- Generate summary when gate allows ----
    can_summarize = bool(val) and not (
        val.get("discharge_blocked") or val.get("needs_hitl")
    )
    if st.button(
        "Generate summary",
        use_container_width=False,
        disabled=not can_summarize,
        key=f"gen_sum_{pid}",
    ):
        working = st.session_state.case or bridge.load_working_case(pid)
        out = bridge.maybe_summarize(working, st.session_state.validation or {})
        if out.get("error"):
            st.error(out["error"])
        else:
            sync_pipeline_after_hitl(
                case=working,
                validation=st.session_state.validation,
                summary=out.get("summary"),
                indexed=True,
            )
            st.success("Summary ready — open Discharge Summary")
            st.rerun()
    if not can_summarize:
        st.caption(
            "Generate summary unlocks when critical blocks and mandatory review are cleared."
        )

    if feedback:
        with st.expander("Saved feedback on disk"):
            st.json(feedback)
