"""Unit coverage for the clinical sidebar rail (presentation logic only)."""

from dashboard.components.common import case_trace_url
from dashboard.sidebar import (
    NAV_ICONS,
    RailContext,
    _badge_text,
    _next_action,
    alert_html,
    footer_html,
    nav_decoration_css,
    patient_html,
    progress_html,
)
from dashboard.state import ADMIN_PAGES, PAGES
from dashboard.ui_chrome import trace_link_row_html


def test_every_page_has_a_nav_icon():
    assert set(NAV_ICONS) == set(PAGES)


def test_nav_css_emits_one_icon_rule_per_page():
    css = nav_decoration_css({})
    for index, page in enumerate(PAGES, start=1):
        assert f'label:nth-child({index})::before {{ content: "{NAV_ICONS[page]}"; }}' in css


def test_nav_css_badges_land_on_the_right_row():
    css = nav_decoration_css({2: ("4", "bad")})
    assert 'label:nth-child(2)::after' in css
    assert 'content: "4"' in css
    # Tone is baked in — pseudo-elements cannot carry a class.
    assert "rgba(239,68,68,0.20)" in css


def test_admin_group_label_is_placed_on_the_first_admin_row():
    admin_index = next(i for i, page in enumerate(PAGES, start=1) if page in ADMIN_PAGES)
    css = nav_decoration_css({})
    assert f'label:nth-child({admin_index})::after' in css
    assert 'content: "Administration"' in css


def test_badge_text_cannot_break_out_of_the_css_string():
    hostile = _badge_text('3"; } body { display:none')
    assert not set(hostile) & set('"\\{};<>')
    assert len(hostile) <= 8
    assert _badge_text("✓") == "✓"
    assert _badge_text(None) == ""


def test_blocked_case_reports_the_blocking_count():
    ctx = RailContext(patient_id="P1", processed=True, blocked=True, blocking_count=2)
    tone, _icon, title, body = _next_action(ctx)
    assert tone == "bad"
    assert title == "Discharge blocked"
    assert "2 blocking gap(s)" in body
    assert 'tone-bad' in alert_html(ctx)


def test_unprocessed_case_points_at_document_viewer():
    tone, _icon, title, _body = _next_action(RailContext(patient_id="P1"))
    assert (tone, title) == ("info", "Ready to process")


def test_no_patient_asks_for_a_selection():
    ctx = RailContext()
    assert _next_action(ctx)[2] == "Pick a patient"
    assert "No patient selected" in patient_html(ctx)
    assert progress_html(ctx) == ""


def test_patient_card_escapes_untrusted_names():
    ctx = RailContext(patient_id="P1", patient_name="<script>x</script>", initials="XX")
    html = patient_html(ctx)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_footer_links_the_trace_chip_when_a_url_is_available():
    html = footer_html(
        RailContext(trace_id="P1-abcdef123456", trace_url="https://lf.test/project/p/traces/t")
    )
    assert 'href="https://lf.test/project/p/traces/t"' in html
    assert 'rel="noopener noreferrer"' in html
    assert 'target="_blank"' in html
    assert ">ef123456<" in html  # chip shows the short tail
    assert 'title="Trace P1-abcdef123456' in html  # full id stays available on hover


def test_footer_falls_back_to_a_plain_chip_without_a_url():
    html = footer_html(RailContext(trace_id="P1-abcdef123456"))
    assert "<a " not in html
    assert "<code" in html
    assert "audit trail retained" in html


def test_trace_url_prefers_the_stamped_report_url():
    stamped = {"audit_trail": {"langfuse_url": "https://lf.test/project/p/traces/stamped"}}
    assert case_trace_url(stamped, "ignored") == "https://lf.test/project/p/traces/stamped"


def test_local_only_tracing_is_not_treated_as_a_link():
    # langfuse_link returns the local-trace: sentinel when no backend is configured.
    assert case_trace_url({"audit_trail": {"trace_ids": []}}, "") is None


def test_trace_link_row_escapes_the_url():
    row = trace_link_row_html('https://x/y"><script>alert(1)</script>')
    assert "<script>" not in row
    assert "&quot;" in row


def test_progress_bar_width_tracks_completed_stages():
    ctx = RailContext(patient_id="P1", stages_done=7, has_summary=True)
    assert "width:100%" in progress_html(ctx)
    assert "tone-ok" in progress_html(ctx)
