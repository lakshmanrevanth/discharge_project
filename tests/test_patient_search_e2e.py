"""End-to-end coverage for sidebar patient search.

Covers the two production bugs:
1. Selecting a hint must not write patient_query after the widget mounts.
2. Live filtering must work for progressive typeahead queries.
Also asserts the live-search iframe frontend never uses a white canvas and
never overwrites the input while focused.
"""

from __future__ import annotations

from pathlib import Path

from dashboard.components.common import filter_patient_hints, patient_display_name
from dashboard.components.live_search import live_patient_search


FRONTEND = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "components"
    / "live_search_frontend"
    / "index.html"
)


def test_live_search_frontend_is_dark_and_focus_safe():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "background: #0b1220" in html
    assert "document.activeElement !== input" in html
    assert "args.reset" in html
    assert "height: 44px" in html
    assert "Search patient by ID or name" not in html or "placeholder" in html
    # Must not paint transparent over browser-default white iframe chrome.
    assert "background: transparent" not in html.split("input {")[0]


def test_typeahead_progressive_queries():
    ids = ["P1003", "P1018", "P1019", "P1020", "P1022", "P1021", "P1023", "P1024"]
    assert filter_patient_hints("", ids) == []
    assert filter_patient_hints("1020", ids) == ["P1020"]
    assert filter_patient_hints("diego", ids) == ["P1020"]
    assert filter_patient_hints("zzz-nope", ids) == []
    # Top 3 only — broad "p10" prefix must not dump the full list
    broad = filter_patient_hints("p10", ids, limit=3)
    assert len(broad) == 3
    assert all(pid.upper().startswith("P10") for pid in broad)
    # Exact ID beats other prefix matches
    assert filter_patient_hints("p1020", ids, limit=3)[0] == "P1020"
    assert patient_display_name("P1020") == "Diego Morales"


def test_select_patient_defers_query_clear(monkeypatch):
    """Regression: clearing patient_query after text widget mount crashes Streamlit."""
    import dashboard.app as app_mod

    class FakeState(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError as exc:
                raise AttributeError(item) from exc

        def __setattr__(self, key, value):
            self[key] = value

    fake = FakeState(
        patient_id="P1003",
        patient_query="P1020",
        pipeline_result={"x": 1},
        case={"patient_id": "P1003"},
        validation={},
        summary=None,
        rag_history=[],
        doc_count=2,
        last_error=None,
    )
    rerun_calls: list[int] = []

    class FakeSt:
        session_state = fake

        @staticmethod
        def rerun():
            rerun_calls.append(1)

    monkeypatch.setattr(app_mod, "st", FakeSt)
    app_mod._select_patient("P1020")

    assert fake["patient_id"] == "P1020"
    assert fake.get("_pending_clear_patient_query") is True
    # Must NOT clear the bound key here — that was the StreamlitAPIException.
    assert fake["patient_query"] == "P1020"
    assert fake["pipeline_result"] is None  # case cleared on change
    assert rerun_calls == [1]


def test_sidebar_clear_happens_before_search_widget(monkeypatch):
    """Simulate one sidebar pass: pending clear → query emptied before search."""
    import dashboard.app as app_mod

    class FakeState(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError as exc:
                raise AttributeError(item) from exc

        def __setattr__(self, key, value):
            self[key] = value

        def pop(self, key, default=None):
            return dict.pop(self, key, default)

        def get(self, key, default=None):
            return dict.get(self, key, default)

    fake = FakeState(
        patient_id="P1020",
        patient_query="diego",
        _pending_clear_patient_query=True,
        patient_search_nonce=0,
        page="Document Viewer",
        last_clinical_page="Document Viewer",
        case={"patient_id": "P1020", "patient_name": "Diego Morales"},
        pipeline_result=None,
        validation=None,
        summary=None,
        rag_history=[],
        doc_count=None,
        last_error=None,
    )

    captured: dict = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return ""

    class FakeSidebar:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    sidebar_cm = FakeSidebar()

    class FakeSt:
        session_state = fake
        sidebar = sidebar_cm

        @staticmethod
        def markdown(*args, **kwargs):
            return None

        @staticmethod
        def button(*args, **kwargs):
            return False

        @staticmethod
        def radio(*args, **kwargs):
            return "Document Viewer"

    monkeypatch.setattr(app_mod, "st", FakeSt)
    monkeypatch.setattr(app_mod, "discover_patient_ids", lambda: ["P1020", "P1019"])
    monkeypatch.setattr(app_mod, "patient_display_name", lambda pid: "Diego Morales")
    monkeypatch.setattr(app_mod, "selected_patient_card_html", lambda *a, **k: "<div/>")
    monkeypatch.setattr(app_mod, "filter_patient_hints", lambda *a, **k: [])
    monkeypatch.setattr(app_mod, "nav_label", lambda p: p)
    monkeypatch.setattr(app_mod, "PAGES", ("Document Viewer", "Upload new patients"))
    monkeypatch.setitem(
        __import__("sys").modules,
        "dashboard.components.live_search",
        type("m", (), {"live_patient_search": staticmethod(fake_search)})(),
    )

    # Import path used inside _sidebar
    import dashboard.components.live_search as ls_mod

    monkeypatch.setattr(ls_mod, "live_patient_search", fake_search)

    page = app_mod._sidebar()
    assert page == "Document Viewer"
    assert fake["patient_query"] == ""
    assert fake["patient_search_nonce"] == 1
    assert "_pending_clear_patient_query" not in fake
    assert captured.get("reset") is True
    assert captured.get("value") == ""


def test_live_patient_search_callable():
    # Smoke: function is importable and returns string default without Streamlit run.
    # Actual component needs a ScriptRunContext; we only check signature contract here.
    assert callable(live_patient_search)
