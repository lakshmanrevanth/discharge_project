"""Presentation helpers for HITL chrome — status cards, pipeline, summary HTML.

No business logic. Safe HTML escaping for clinician-facing UI fragments.
"""

from __future__ import annotations

import html
import re
from typing import Any


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def markdown_body_to_html(md: str) -> str:
    """Lightweight markdown → HTML for summary bodies (lists, bold, code, paras)."""
    text = (md or "").strip()
    if not text:
        return ""

    def inline(s: str) -> str:
        s = esc(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    blocks: list[str] = []
    list_buf: list[str] = []
    para_buf: list[str] = []

    def flush_list() -> None:
        nonlocal list_buf
        if list_buf:
            items = "".join(f"<li>{inline(x)}</li>" for x in list_buf)
            blocks.append(f"<ul>{items}</ul>")
            list_buf = []

    def flush_para() -> None:
        nonlocal para_buf
        if para_buf:
            blocks.append(f"<p>{'<br/>'.join(inline(x) for x in para_buf)}</p>")
            para_buf = []

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_list()
            flush_para()
            continue
        if stripped.startswith("- "):
            flush_para()
            list_buf.append(stripped[2:].strip())
            continue
        flush_list()
        para_buf.append(stripped)
    flush_list()
    flush_para()
    return "".join(blocks)


def status_value_html(value: str, tone: str = "") -> str:
    """Tone: ok | warn | bad | teal | badge-ok | badge-warn | badge-bad | ''."""
    v = esc(value)
    if tone.startswith("badge-"):
        return f'<span class="chip {tone}">{v}</span>'
    cls = f" status-value {tone}".rstrip() if tone else " status-value"
    return f'<div class="{cls.strip()}">{v}</div>'


def status_strip_html(cells: list[tuple[str, str, str]]) -> str:
    """cells: (label, value, tone)."""
    icons = {
        "Patient ID": "ID",
        "Patient": "Pt",
        "Risk": "●",
        "Gate": "◇",
        "Indexed": "▣",
        "Documents": "≡",
    }
    parts: list[str] = []
    for label, value, tone in cells:
        icon = icons.get(label, "")
        icon_html = (
            f'<span class="status-icon" aria-hidden="true">{esc(icon)}</span>'
            if icon
            else ""
        )
        if tone.startswith("badge-"):
            val_html = status_value_html(value, tone)
            inner = f'<div class="status-value">{val_html}</div>'
        else:
            inner = status_value_html(value, tone)
        parts.append(
            f'<div class="status-cell">'
            f'<div class="status-label">{icon_html}{esc(label)}</div>'
            f"{inner}</div>"
        )
    return f'<div class="status-strip">{"".join(parts)}</div>'


def pipeline_track_html(
    steps: list[tuple[str, str, str, str]],
) -> str:
    """steps: (key, label, state, mark) from pipeline_step_states."""
    pills: list[str] = []
    for i, (_key, label, state, mark) in enumerate(steps):
        if i:
            pills.append('<span class="pipe-sep" aria-hidden="true"></span>')
        icon = {
            "done": "✓",
            "active": "●",
            "blocked": "✕",
            "skipped": "–",
            "pending": "○",
        }.get(state, mark)
        pills.append(
            f'<span class="pipe-pill {esc(state)}">'
            f'<span class="pipe-icon">{esc(icon)}</span>'
            f'<span class="pipe-label">{esc(label)}</span></span>'
        )
    return f'<div class="pipeline-track">{"".join(pills)}</div>'


def page_header_html(title: str, lede: str) -> str:
    return (
        f'<div class="page-header">'
        f'<div class="page-header-left">'
        f'<div class="page-title">{esc(title)}</div>'
        f'<p class="page-lede">{esc(lede)}</p>'
        f'</div>'
        f'<div class="page-header-right"></div>'
        f'</div>'
    )


def summary_document_html(
    *,
    title: str,
    lede: str,
    sections: list[dict[str, Any]],
    section_titles: dict[str, str],
) -> str:
    """One complete hero card — never emit empty wrappers."""
    if not sections:
        return ""
    body_parts: list[str] = []
    for sec in sections:
        key = str(sec.get("name") or "")
        heading = section_titles.get(key, key.replace("_", " ").title())
        md = str(sec.get("markdown") or "").strip()
        if not md:
            continue
        body_parts.append(
            f'<section class="summary-block">'
            f'<h3 class="summary-block-title">{esc(heading)}</h3>'
            f'<div class="summary-block-body">{markdown_body_to_html(md)}</div>'
            f"</section>"
        )
    if not body_parts:
        return ""
    return (
        f'<article class="summary-hero">'
        f'<header class="summary-hero-head">'
        f'<div class="summary-hero-kicker">Clinical discharge letter</div>'
        f'<h2 class="summary-hero-title">{esc(title)}</h2>'
        f'<p class="summary-hero-lede">{esc(lede)}</p>'
        f"</header>"
        f'<div class="summary-hero-body">{"".join(body_parts)}</div>'
        f"</article>"
    )


def _gap_items(gaps: Any) -> list[str]:
    if gaps is None:
        return []
    if isinstance(gaps, str):
        text = gaps.strip()
        return [text] if text and text not in {"—", "-", "[]", "{}", "null", "None"} else []
    if isinstance(gaps, (list, tuple, set)):
        out: list[str] = []
        for item in gaps:
            if item is None:
                continue
            text = str(item).strip()
            if text and text not in {"—", "-", "None", "null"}:
                out.append(text)
        return out
    if isinstance(gaps, dict):
        return [f"{k}: {v}" for k, v in gaps.items() if v is not None and str(v).strip()]
    text = str(gaps).strip()
    return [text] if text and text not in {"—", "-", "[]", "{}", "null", "None"} else []


def blocking_gaps_for_display(
    missing_blocking: Any,
    findings: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Completeness blocking fields + Critical/Block findings clinicians expect here.

    ``missing_blocking`` is only FA5 mandatory-field completeness. Gate blocks from
    EHR/bill/allergy checks live in ``findings`` with action Block — surface those too.
    """
    items = _gap_items(missing_blocking)
    seen = {x.lower() for x in items}
    for finding in findings or []:
        action = str(finding.get("action") or "").strip().lower()
        severity = str(finding.get("severity") or "").strip().lower()
        rule = str(finding.get("rule_id") or "").strip()
        # Gate notes (auto/reviewer elicitation decline) — not clinical Critical.
        if rule.startswith("elicitation_"):
            continue
        if action != "block" and severity != "critical":
            continue
        field = str(finding.get("field") or "").strip()
        message = str(finding.get("message") or "").strip()
        if field:
            label = field
            if message and len(message) <= 120:
                label = f"{field} — {message}"
        elif message:
            label = message if len(message) <= 140 else f"{rule}: {message[:120]}…"
        elif rule:
            label = rule
        else:
            continue
        key = label.lower()
        if key in seen or (field and field.lower() in seen):
            continue
        seen.add(key)
        if field:
            seen.add(field.lower())
        items.append(label)
    return items


def empty_state_html(message: str, *, tone: str = "ok") -> str:
    return (
        f'<div class="empty-state empty-{esc(tone)}">'
        f'<span class="empty-icon" aria-hidden="true">✓</span>'
        f'<span class="empty-text">{esc(message)}</span></div>'
    )


def gaps_panel_html(title: str, gaps: Any, *, empty_message: str) -> str:
    items = _gap_items(gaps)
    if items:
        lis = "".join(f"<li>{esc(x)}</li>" for x in items)
        body = f'<ul class="gap-list">{lis}</ul>'
    else:
        body = empty_state_html(empty_message, tone="ok")
    return (
        f'<div class="gap-panel">'
        f'<div class="gap-panel-title">{esc(title)}</div>'
        f"{body}</div>"
    )


def validation_status_card_html(
    *,
    level: str,
    score: Any,
    blocked: bool,
    needs_hitl: bool,
    rules_version: str | None,
    risk_badge: str,
) -> str:
    badges = (
        f'<span class="badge {esc(risk_badge)}">Risk {esc(level)}</span>'
        f'<span class="badge badge-mute">Score {esc(score)}</span>'
        f'<span class="badge {"badge-bad" if blocked else "badge-ok"}">'
        f'{"Blocked" if blocked else "Not blocked"}</span>'
        f'<span class="badge {"badge-warn" if needs_hitl else "badge-ok"}">'
        f'{"Needs Review" if needs_hitl else "Auto path"}</span>'
    )
    rules = (rules_version or "").strip()
    rules_html = ""
    if rules and rules != "—":
        rules_html = (
            f'<div class="rules-row">'
            f'<span class="rules-label">Rules</span>'
            f'<code class="rules-hash">{esc(rules)}</code></div>'
        )
    return f'<div class="card val-status-card"><div class="badge-row">{badges}</div>{rules_html}</div>'


def trace_link_row_html(url: str, *, kind: str = "trace") -> str:
    """Audit-artifact row whose value opens the LangFuse trace in a new tab."""
    href = esc(url)
    return (
        f'<div class="artifact-row">'
        f'<span class="artifact-kind">{esc(kind)}</span>'
        f'<a class="artifact-uri artifact-link" href="{href}" '
        f'target="_blank" rel="noopener noreferrer">'
        f"Open in LangFuse ↗</a></div>"
    )


def finding_card_html(finding: dict[str, Any]) -> str:
    sev = str(finding.get("severity") or "Info")
    sev_l = sev.lower()
    cls = "critical" if sev_l == "critical" else "warning" if sev_l == "warning" else "info"
    rule = str(finding.get("rule_id") or "—")
    action = str(finding.get("action") or "—")
    msg = str(finding.get("message") or "").strip()
    msg_html = f'<div class="finding-msg">{esc(msg)}</div>' if msg else ""
    return (
        f'<div class="finding {cls}">'
        f'<div class="finding-head">'
        f'<span class="finding-sev">{esc(sev)}</span>'
        f'<span class="finding-action">{esc(action)}</span>'
        f'</div>'
        f'<div class="finding-rule">{esc(rule)}</div>'
        f"{msg_html}</div>"
    )
