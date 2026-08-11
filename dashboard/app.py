"""Discharge AI — HITL Streamlit Dashboard (:8501).

Five FA5 Table 13 pages. Agents own business rules; this UI only calls them.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from dashboard import bridge
from dashboard.bridge import SECTION_TITLES
from dashboard.components.common import (
    case_trace_url,
    discover_patient_ids,
    filter_patient_hints,
    patient_display_name,
)
from dashboard.corrections import page_corrections as _page_corrections_impl
from dashboard.sidebar import render_sidebar
from dashboard.state import (
    ADMIN_PAGES,
    ensure_session_defaults,
    risk_badge_class,
)
from dashboard.styles import (
    inject_styles,
    navbar_html,
    pipeline_step_states,
)
from dashboard.ui_chrome import (
    blocking_gaps_for_display,
    esc as _esc,
    finding_card_html,
    gaps_panel_html,
    page_header_html,
    pipeline_track_html,
    status_strip_html,
    summary_document_html,
    trace_link_row_html,
    validation_status_card_html,
)


def _cfg() -> None:
    st.set_page_config(
        page_title="Discharge AI · HITL",
        page_icon="DA",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _page_header(title: str, lede: str) -> None:
    st.markdown(page_header_html(title, lede), unsafe_allow_html=True)


def _bump_meds_editor_epoch() -> None:
    """Invalidate Streamlit data_editor state so Process/switch cannot keep stale rows."""
    st.session_state.meds_editor_epoch = int(st.session_state.get("meds_editor_epoch") or 0) + 1
    for key in list(st.session_state.keys()):
        k = str(key)
        # Widget keys only — do not delete the epoch counter itself.
        if k.startswith("meds_editor_") and k != "meds_editor_epoch":
            del st.session_state[key]


def _clear_case_state() -> None:
    st.session_state.pipeline_result = None
    st.session_state.case = None
    st.session_state.validation = None
    st.session_state.summary = None
    st.session_state.rag_history = []
    st.session_state.doc_count = None
    st.session_state.last_error = None
    # HITL med/elicitation edits are per-patient — never carry across switches
    st.session_state.edited_meds = None
    st.session_state.edited_meds_pid = None
    st.session_state.edited_meds_epoch = None
    st.session_state.elicitation_values = {}
    st.session_state.elicitation_values_pid = None
    _bump_meds_editor_epoch()


def _select_patient(pid: str) -> None:
    """Switch active patient and drop prior pipeline snapshot."""
    if not pid:
        return
    changed = pid != st.session_state.patient_id
    st.session_state.patient_id = pid
    # Cannot touch widget-bound keys after instantiate — clear on next run instead.
    st.session_state["_pending_clear_patient_query"] = True
    if changed:
        _clear_case_state()
    st.rerun()


def _navbar() -> None:
    """Top navbar — branding, search hint, and current patient avatar."""
    current = str(st.session_state.patient_id or "")
    case = st.session_state.case or {}
    name = patient_display_name(current) if current else ""
    if case.get("patient_name") and str(case.get("patient_id") or "") == current:
        name = str(case.get("patient_name")).strip() or name
    st.markdown(navbar_html(current, name), unsafe_allow_html=True)


def _search_bar() -> None:
    """Inline search bar in the main content area (below navbar)."""
    from dashboard.components.live_search import live_patient_search

    live_ids = discover_patient_ids()
    current = str(st.session_state.patient_id or "")

    # Clear search BEFORE the search widget mounts (Streamlit rule).
    reset_search = bool(st.session_state.pop("_pending_clear_patient_query", False))
    if reset_search:
        st.session_state.patient_query = ""
        st.session_state.patient_search_nonce = (
            int(st.session_state.get("patient_search_nonce") or 0) + 1
        )

    nonce = int(st.session_state.get("patient_search_nonce") or 0)
    prior = str(st.session_state.get("patient_query") or "")
    query = live_patient_search(
        placeholder="Search patient by ID or name...",
        value=prior,
        debounce_ms=120,
        reset=reset_search,
        key=f"patient_query_live_{nonce}",
    )
    st.session_state.patient_query = query

    needle = (query or "").strip()
    if needle:
        hints = filter_patient_hints(needle, live_ids, limit=3)
        if hints:
            st.markdown(
                '<div class="sb-suggest-label" style="color:var(--muted)!important;'
                '-webkit-text-fill-color:var(--muted)!important;font-size:0.72rem;'
                'font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
                'margin:0.35rem 0 0.4rem;">Suggestions</div>',
                unsafe_allow_html=True,
            )
            for pid in hints:
                label = f"{pid} — {patient_display_name(pid)}"
                if st.button(
                    label,
                    key=f"hint_{nonce}_{pid}",
                    use_container_width=True,
                    type="primary" if pid == current else "secondary",
                ):
                    _select_patient(pid)
        else:
            st.info("No matching patients found.")
            from mcp_servers.primary.roots import sanitize_patient_id

            try:
                candidate = sanitize_patient_id(needle)
            except Exception:
                candidate = ""
            if candidate and candidate not in live_ids:
                if st.button(
                    f"Use new ID · {candidate}",
                    use_container_width=True,
                    key=f"apply_typed_pid_{nonce}",
                ):
                    _select_patient(candidate)


def _sidebar() -> str:
    """Clinical rail — patient context, workflow nav, next action. Collapsible."""

    def _remember(page: str) -> None:
        st.session_state.page = page
        if page not in ADMIN_PAGES:
            st.session_state.last_clinical_page = page

    return render_sidebar(on_navigate=_remember)


def _gate_status(val: dict[str, Any] | None) -> tuple[str, str]:
    if not val:
        return "Idle", "teal"
    if val.get("discharge_blocked"):
        return "Blocked", "bad"
    if val.get("needs_hitl"):
        return "Needs Review", "warn"
    return "Clear", "ok"


def _status_strip() -> None:
    pid = st.session_state.patient_id
    case = st.session_state.case or {}
    name = str(case.get("patient_name") or "").strip() or patient_display_name(pid)
    val = st.session_state.validation or {}
    risk = val.get("risk") or {}
    level = str(risk.get("level") or "—")
    gate_label, gate_cls = _gate_status(val if val else None)
    risk_badge = {
        "low": "badge-ok",
        "medium": "badge-warn",
        "high": "badge-bad",
    }.get(level.lower(), "badge-mute")
    indexed = (st.session_state.pipeline_result or {}).get("indexed")
    indexed_label = "Yes" if indexed else ("—" if not st.session_state.pipeline_result else "No")
    indexed_tone = "ok" if indexed else ("teal" if not st.session_state.pipeline_result else "warn")
    docs = st.session_state.get("doc_count")
    docs_label = str(docs) if docs is not None else "—"

    cells = [
        ("Patient ID", pid, "teal"),
        ("Patient", name, ""),
        ("Risk", level.title() if level != "—" else "—", risk_badge),
        ("Gate", gate_label, gate_cls),
        ("Indexed", indexed_label, indexed_tone),
        ("Documents", docs_label, "teal"),
    ]
    st.markdown(status_strip_html(cells), unsafe_allow_html=True)


def _pipeline_line() -> None:
    steps = pipeline_step_states(
        st.session_state.pipeline_result,
        validation=st.session_state.validation,
        summary=st.session_state.summary,
    )
    st.markdown(pipeline_track_html(steps), unsafe_allow_html=True)


def _sync_from_pipeline(out: dict[str, Any]) -> None:
    st.session_state.pipeline_result = out
    st.session_state.trace_id = out.get("trace_id")
    st.session_state.case = out.get("case")
    st.session_state.validation = out.get("validation")
    st.session_state.summary = out.get("summary")
    st.session_state.last_error = out.get("error")
    # Fresh Process owns meds — drop stale HITL overlays from another patient
    st.session_state.edited_meds = None
    st.session_state.edited_meds_pid = None
    st.session_state.edited_meds_epoch = None
    st.session_state.elicitation_values = {}
    st.session_state.elicitation_values_pid = None
    _bump_meds_editor_epoch()
    # Disk drafts must not outrank this extract on Corrections
    pid = str(out.get("patient_id") or st.session_state.get("patient_id") or "")
    if pid and not out.get("error"):
        from dashboard.components.common import clear_feedback_medications

        clear_feedback_medications(pid, pipeline_trace_id=out.get("trace_id"))
        # Fresh Process owns RAG again — drop prior HITL-corrected snapshot
        from dashboard import bridge as _bridge

        _bridge.clear_hitl_rag_snapshot(pid)


def _sync_pipeline_after_hitl(
    *,
    case: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    indexed: bool | None = None,
) -> None:
    """Keep Host snapshot in sync after Corrections re-validate / summarize."""
    if case is not None:
        st.session_state.case = case
    if validation is not None:
        st.session_state.validation = validation
    if summary is not None:
        st.session_state.summary = summary

    pr = dict(st.session_state.pipeline_result or {})
    val = st.session_state.validation or {}
    blocked = bool(val.get("discharge_blocked"))
    needs = bool(val.get("needs_hitl"))
    allow = not (blocked or needs)
    pr["validation"] = val
    pr["discharge_blocked"] = blocked
    pr["needs_hitl"] = needs
    pr["gate"] = {
        "allow_summary": allow,
        "reason": None if allow else "hitl_remediation_pending",
    }
    if st.session_state.summary is not None:
        pr["summary"] = st.session_state.summary
    elif allow:
        pr["summary"] = None
    if case is not None:
        pr["case"] = case
    if indexed is not None:
        pr["indexed"] = indexed
    stages = list(pr.get("stages_run") or [])
    for stage in ("validate", "index", "gate", "summary_or_hitl"):
        if stage not in stages:
            stages.append(stage)
    pr["stages_run"] = stages
    st.session_state.pipeline_result = pr


def _list_files() -> list[dict[str, Any]]:
    discovered = bridge.list_patient_documents(st.session_state.patient_id)
    files = [f for f in (discovered.get("files") or []) if isinstance(f, dict)]
    st.session_state.doc_count = len(files)
    return files


def page_upload() -> None:
    from dashboard.components.ingest import save_upload
    from mcp_servers.primary.roots import sanitize_patient_id

    _kinds = {
        "discharge": "Discharge Report",
        "lab": "Lab Report",
        "bill": "Hospital Bill",
    }
    _types = ["txt", "pdf", "png", "jpg", "jpeg", "json"]

    st.markdown(
        '<div class="upload-page">'
        '<div class="upload-page-title">Upload New Patients</div>'
        '<p class="upload-page-lede">'
        "Add discharge, lab, and bill documents for a new or existing patient. "
        "All three are required — after upload the same Process pipeline runs."
        "</p></div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="upload-card-mark"></div>', unsafe_allow_html=True)
        up_pid = st.text_input(
            "Patient ID",
            value=st.session_state.patient_id or "",
            placeholder="e.g. P1018 or P2001",
            key="upload_patient_id",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                '<div class="upload-field-title">Discharge Report</div>',
                unsafe_allow_html=True,
            )
            discharge_up = st.file_uploader(
                "Discharge Report",
                type=_types,
                key="up_discharge",
                label_visibility="collapsed",
            )
            if discharge_up is None:
                st.markdown(
                    '<div class="upload-slot-hint">PDF · TXT · PNG · JPG</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="upload-selected">✓ {_esc(discharge_up.name)}</div>',
                    unsafe_allow_html=True,
                )
        with c2:
            st.markdown(
                '<div class="upload-field-title">Lab Report</div>',
                unsafe_allow_html=True,
            )
            lab_up = st.file_uploader(
                "Lab Report",
                type=_types,
                key="up_lab",
                label_visibility="collapsed",
            )
            if lab_up is None:
                st.markdown(
                    '<div class="upload-slot-hint">PDF · TXT · PNG · JPG</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="upload-selected">✓ {_esc(lab_up.name)}</div>',
                    unsafe_allow_html=True,
                )
        with c3:
            st.markdown(
                '<div class="upload-field-title">Hospital Bill</div>',
                unsafe_allow_html=True,
            )
            bill_up = st.file_uploader(
                "Hospital Bill",
                type=_types,
                key="up_bill",
                label_visibility="collapsed",
            )
            if bill_up is None:
                st.markdown(
                    '<div class="upload-slot-hint">PDF · TXT · PNG · JPG</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="upload-selected">✓ {_esc(bill_up.name)}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<p class="upload-formats-note">Supported: PDF, TXT, PNG, JPG, JPEG, JSON</p>',
            unsafe_allow_html=True,
        )

        all_three = all(f is not None for f in (discharge_up, lab_up, bill_up))
        if not all_three:
            st.warning(
                "Upload all three documents (discharge report, lab report, and "
                "hospital bill) to proceed."
            )

        st.markdown('<div class="upload-cta-mark"></div>', unsafe_allow_html=True)
        clicked = st.button(
            "Upload Documents",
            type="primary",
            key="save_uploads",
            disabled=not all_three,
            use_container_width=True,
        )

        if clicked:
            results: list[dict[str, Any]] = []
            pipeline_out: dict[str, Any] | None = None
            try:
                pid = sanitize_patient_id(up_pid)
            except Exception as exc:
                st.session_state.upload_results = [
                    {
                        "kind": "patient_id",
                        "ok": False,
                        "path": "",
                        "error": str(exc),
                        "name": "",
                        "patient_id": up_pid,
                    }
                ]
                st.session_state.upload_pipeline = None
                st.error(f"Invalid patient ID — {exc}")
                pid = ""

            if pid and not all_three:
                st.warning(
                    "Upload all three documents (discharge report, lab report, and "
                    "hospital bill) to proceed."
                )
                pid = ""

            if pid:
                uploads = [
                    ("discharge", discharge_up),
                    ("lab", lab_up),
                    ("bill", bill_up),
                ]
                with st.spinner("Uploading documents…"):
                    for kind, file in uploads:
                        if file is None:
                            continue
                        try:
                            path = save_upload(pid, kind, file.name, file.getvalue())
                            results.append(
                                {
                                    "kind": kind,
                                    "ok": True,
                                    "path": str(path),
                                    "error": None,
                                    "name": file.name,
                                    "patient_id": pid,
                                }
                            )
                        except Exception as exc:  # noqa: BLE001
                            results.append(
                                {
                                    "kind": kind,
                                    "ok": False,
                                    "path": "",
                                    "error": str(exc),
                                    "name": file.name,
                                    "patient_id": pid,
                                }
                            )
                st.session_state.upload_results = results
                ok_kinds = {r["kind"] for r in results if r.get("ok")}
                full_ok = ok_kinds >= {"discharge", "lab", "bill"} and not any(
                    not r.get("ok") for r in results
                )
                if any(r["ok"] for r in results):
                    st.session_state.patient_id = pid
                    _clear_case_state()
                if full_ok:
                    with st.spinner("Running Process pipeline…"):
                        try:
                            pipeline_out = bridge.run_host_pipeline(pid)
                            _sync_from_pipeline(pipeline_out)
                        except Exception as exc:  # noqa: BLE001
                            pipeline_out = {"error": str(exc), "patient_id": pid}
                            st.session_state.last_error = str(exc)
                    st.session_state.upload_pipeline = pipeline_out
                else:
                    st.session_state.upload_pipeline = None
                st.rerun()

    results = st.session_state.get("upload_results")
    if not results:
        return

    ok_rows = [r for r in results if r.get("ok")]
    fail_rows = [r for r in results if not r.get("ok")]
    pid_shown = (
        (ok_rows[0].get("patient_id") if ok_rows else None)
        or (fail_rows[0].get("patient_id") if fail_rows else None)
        or st.session_state.patient_id
        or "—"
    )

    if ok_rows and not fail_rows:
        names = ", ".join(_esc(str(r.get("name") or "—")) for r in ok_rows)
        st.markdown(
            '<div class="upload-success-banner">'
            '<span class="upload-success-check" aria-hidden="true">✓</span>'
            "<div>"
            "<strong>Documents uploaded successfully.</strong>"
            f'<span class="upload-success-meta">Patient {_esc(pid_shown)}'
            f" · {len(ok_rows)} file(s) · {names}</span>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        pipe = st.session_state.get("upload_pipeline")
        if isinstance(pipe, dict):
            if pipe.get("error"):
                st.error(f"Pipeline error — {pipe['error']}")
            else:
                st.success(
                    f"Process complete · status={pipe.get('status')} · "
                    f"indexed={pipe.get('indexed')}"
                )
    elif ok_rows and fail_rows:
        st.warning(
            f"Partial upload — {len(ok_rows)} succeeded, {len(fail_rows)} failed. "
            "Upload all three documents to proceed with Process."
        )
        for r in fail_rows:
            label = _kinds.get(str(r.get("kind")), r.get("kind") or "Document")
            st.error(
                f"{label} failed"
                + (f" ({r.get('name')})" if r.get("name") else "")
                + f" — {r.get('error') or 'unknown error'}"
            )
    else:
        for r in fail_rows:
            label = _kinds.get(str(r.get("kind")), r.get("kind") or "Document")
            if r.get("kind") == "patient_id":
                st.error(f"Patient ID invalid — {r.get('error') or 'unknown error'}")
            else:
                st.error(
                    f"{label} failed"
                    + (f" ({r.get('name')})" if r.get("name") else "")
                    + f" — {r.get('error') or 'unknown error'}"
                )


def page_documents() -> None:
    from dashboard.components.ingest import (
        all_intake_present,
        intake_doc_coverage,
        missing_intake_labels,
    )

    _page_header(
        "Document Viewer",
        "Browse intake files for the selected patient, then run the pipeline.",
    )

    if not st.session_state.patient_id:
        st.info("Search or upload a patient first (sidebar or Upload new patients).")
        return

    files = _list_files()
    coverage = intake_doc_coverage(st.session_state.patient_id)
    missing = missing_intake_labels(coverage)
    ready = all_intake_present(coverage)

    st.caption("Pipeline always reads live intake under `data/input/` for this patient.")
    if missing:
        st.warning(
            "Upload all three documents (discharge report, lab report, and "
            "hospital bill) to proceed. "
            f"Missing: {', '.join(missing)}."
        )

    if st.button("Process patient", type="primary", disabled=not ready):
        if not ready:
            st.warning(
                "Upload all three documents (discharge report, lab report, and "
                "hospital bill) to proceed."
            )
        else:
            progress = st.progress(0, text="Starting pipeline…")
            with st.spinner("Running pipeline…"):
                try:
                    progress.progress(15, text="Monitor → Extract → Normalize…")
                    out = bridge.run_host_pipeline(st.session_state.patient_id)
                    progress.progress(85, text="Gate → Summary…")
                    _sync_from_pipeline(out)
                    progress.progress(100, text="Done")
                    if out.get("error"):
                        st.error(out["error"])
                    else:
                        st.success(
                            f"Done · status={out.get('status')} · indexed={out.get('indexed')}"
                        )
                        st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.session_state.last_error = str(exc)
                    st.error(str(exc))

    st.caption(f"{len(files)} file(s) under Roots for {st.session_state.patient_id}")
    if not files:
        st.info(
            "No files for this patient. Use **Upload new patients**, then return here "
            "to Process patient."
        )
        return

    by_type: dict[str, list[dict[str, Any]]] = {"discharge": [], "lab": [], "bill": []}
    for f in files:
        dt = str(f.get("doc_type") or "discharge").lower()
        by_type.setdefault(dt if dt in by_type else "discharge", []).append(f)

    tabs = st.tabs(["Discharge", "Lab", "Bill"])
    for tab, key in zip(tabs, ("discharge", "lab", "bill"), strict=True):
        with tab:
            items = by_type.get(key) or []
            if not items:
                st.write("None for this type.")
                continue
            labels = [str(i.get("path") or i.get("uri") or i) for i in items]
            pick = st.selectbox(f"{key} file", labels, key=f"doc_{key}")
            case = st.session_state.case
            if case and key == "discharge":
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Name:** {case.get('patient_name')}")
                c2.write(f"**Ward:** {case.get('ward')} / {case.get('bed_no')}")
                c3.write(f"**Age:** {case.get('age') if case.get('age') is not None else '—'}")
            preview = bridge.read_doc_preview(pick)
            st.markdown(
                f'<div class="doc-preview">{_esc(preview).replace(chr(10), "<br/>")}</div>',
                unsafe_allow_html=True,
            )


def page_validation() -> None:
    _page_header(
        "Validation Report",
        "Findings and risk from the Validator agent.",
    )
    val = st.session_state.validation
    if not val:
        st.warning("Run **Process patient** on Document Viewer first.")
        return

    risk = val.get("risk") or {}
    level = str(risk.get("level") or "—")
    gate_label, _ = _gate_status(val)
    findings = val.get("findings") or []

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk", level)
    c2.metric("Score", str(risk.get("score", "—")))
    c3.metric("Gate", gate_label)
    c4.metric("Findings", len(findings))

    st.markdown(
        validation_status_card_html(
            level=level,
            score=risk.get("score", "—"),
            blocked=bool(val.get("discharge_blocked")),
            needs_hitl=bool(val.get("needs_hitl")),
            rules_version=val.get("rules_version"),
            risk_badge=risk_badge_class(level),
        ),
        unsafe_allow_html=True,
    )

    uris = {k: v for k, v in (val.get("report_uris") or {}).items() if v}
    trace = case_trace_url(val, st.session_state.get("trace_id"))
    if uris or trace:
        with st.expander("Audit artifacts", expanded=False):
            for kind, uri in uris.items():
                st.markdown(
                    f'<div class="artifact-row">'
                    f'<span class="artifact-kind">{_esc(kind)}</span>'
                    f'<code class="artifact-uri">{_esc(uri)}</code></div>',
                    unsafe_allow_html=True,
                )
            if trace:
                st.markdown(trace_link_row_html(trace), unsafe_allow_html=True)

    st.markdown('<div class="section-label">Findings</div>', unsafe_allow_html=True)
    score = (val.get("risk") or {}).get("score")
    level = (val.get("risk") or {}).get("level") or val.get("risk_level")
    outcome = str(val.get("elicitation_outcome") or "").lower()
    if (
        str(level).lower() == "high"
        and (score == 0 or score == "0")
        and outcome in {"decline", "cancel", "declined", "cancelled"}
    ):
        st.info(
            "Risk is **High** because missing-field elicitation was declined/cancelled "
            "(Mandatory HITL per SSoT §3.7). The numeric score can stay **0** when there "
            "are no weighted clinical findings. On Corrections: fill soft fields "
            "(age / ward / bed / attending), then Re-run validation "
            "(Accept is applied automatically from the form on Re-run)."
        )
    if not findings:
        st.markdown(
            '<div class="empty-state empty-ok">'
            '<span class="empty-icon" aria-hidden="true">✓</span>'
            '<span class="empty-text">No findings — chart looks clean.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        for f in findings:
            st.markdown(finding_card_html(f), unsafe_allow_html=True)

    soft = val.get("missing_soft")
    blocking = blocking_gaps_for_display(val.get("missing_blocking"), findings)
    st.markdown('<div class="section-label">Completeness gaps</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown(
            gaps_panel_html(
                "Soft gaps",
                soft,
                empty_message="No soft gaps detected",
            ),
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            gaps_panel_html(
                "Blocking gaps",
                blocking,
                empty_message="No blocking gaps detected",
            ),
            unsafe_allow_html=True,
        )


def page_corrections() -> None:
    _page_corrections_impl(
        page_header=_page_header,
        sync_pipeline_after_hitl=_sync_pipeline_after_hitl,
    )


def page_rag() -> None:
    _page_header(
        "RAG Assistant",
        "Grounded answers after indexing (works while a case is under review).",
    )
    case = st.session_state.case
    if st.button("Ensure FAISS index"):
        if not case:
            case = bridge.load_working_case(st.session_state.patient_id)
            st.session_state.case = case
        out = bridge.ensure_indexed(case, st.session_state.validation)
        if out.get("error"):
            st.error(out["error"])
        else:
            st.success(f"Indexed — {out.get('indexed_chunks')}")
            pr = dict(st.session_state.pipeline_result or {})
            pr["indexed"] = True
            st.session_state.pipeline_result = pr

    for turn in st.session_state.rag_history:
        with st.chat_message("user"):
            st.write(turn["q"])
        with st.chat_message("assistant"):
            st.write(turn.get("a") or "—")
            raw = turn.get("raw") or {}
            triad = raw.get("triad")
            if triad:
                st.caption(f"Triad · {triad}")

    q = st.chat_input("Ask about this patient's chart")
    if q:
        with st.spinner("RAG…"):
            if not st.session_state.rag_session_id:
                from uuid import uuid4

                st.session_state.rag_session_id = str(uuid4())
            out = bridge.ask_rag(
                st.session_state.patient_id,
                q,
                session_id=st.session_state.rag_session_id,
            )
            if out.get("answer"):
                answer = (
                    out["answer"].get("answer")
                    if isinstance(out["answer"], dict)
                    else out["answer"]
                )
            elif out.get("error"):
                err = out["error"]
                if isinstance(err, dict):
                    answer = f"[{err.get('code')}] {err.get('message')}"
                else:
                    answer = str(err)
            else:
                answer = "—"
            st.session_state.rag_history.append({"q": q, "a": answer, "raw": out})
            st.rerun()


def page_summary() -> None:
    _page_header(
        "Discharge Summary",
        "Patient-friendly English summary for auto-approved cases only.",
    )
    summary = st.session_state.summary
    val = st.session_state.validation or {}
    if val and (val.get("discharge_blocked") or val.get("needs_hitl")) and not summary:
        st.warning("Release gate closed — clear blocks in Corrections first.")
        return
    if not summary:
        st.info("No summary yet. Process a Low-risk / auto-approve patient first.")
        return

    sections = [s for s in (summary.get("sections") or []) if str(s.get("markdown") or "").strip()]
    hero = summary_document_html(
        title="Discharge Summary",
        lede="Structured clinical letter · ready for clinician review and patient handoff.",
        sections=sections,
        section_titles=SECTION_TITLES,
    )
    if hero:
        st.markdown(hero, unsafe_allow_html=True)

    if not sections:
        return

    export = {
        "patient_id": summary.get("patient_id"),
        "sections": sections,
        "trace_id": st.session_state.trace_id,
    }
    e1, e2 = st.columns(2)
    e1.download_button(
        "Export JSON",
        data=json.dumps(export, indent=2),
        file_name=f"{summary.get('patient_id')}_summary.json",
        mime="application/json",
        use_container_width=True,
        type="primary",
    )
    md = "\n\n".join(
        f"## {SECTION_TITLES.get(str(s.get('name') or ''), str(s.get('name') or '').title())}\n\n"
        f"{s.get('markdown')}"
        for s in sections
    )
    e2.download_button(
        "Export Markdown",
        data=md,
        file_name=f"{summary.get('patient_id')}_summary.md",
        mime="text/markdown",
        use_container_width=True,
        type="primary",
    )

    trace = case_trace_url(val, st.session_state.get("trace_id"))
    if trace:
        st.markdown(
            f'<p class="summary-trace-note">Audit · '
            f'<a href="{_esc(trace)}" target="_blank" rel="noopener noreferrer">'
            f"Open this case's trace in LangFuse ↗</a></p>",
            unsafe_allow_html=True,
        )


def main() -> None:
    _cfg()
    inject_styles()
    ensure_session_defaults()
    if "doc_count" not in st.session_state:
        st.session_state.doc_count = None

    page = _sidebar()
    _navbar()
    _search_bar()
    if page != "Upload new patients":
        _status_strip()
        _pipeline_line()

    if page == "Upload new patients":
        page_upload()
    elif page == "Document Viewer":
        page_documents()
    elif page == "Validation Report":
        page_validation()
    elif page == "Corrections":
        page_corrections()
    elif page == "RAG Q&A":
        page_rag()
    else:
        page_summary()


if __name__ == "__main__":
    main()
