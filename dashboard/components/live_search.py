"""Dark live patient search (keyup) for the sidebar.

Streamlit's text_input only commits on Enter/blur. This component emits on
input so recommendations can update while typing.

Critical behaviors (see tests):
  - Never overwrite the field while it is focused (prevents typing fights).
  - Iframe / body use the sidebar dark color (no white chrome flash).
  - Height is clamped to one row so Streamlit's default tall iframe cannot
    paint a white slab over the sidebar.
"""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_BUILD = Path(__file__).parent / "live_search_frontend"
_component = components.declare_component("sb_live_search", path=str(_BUILD))


def live_patient_search(
    *,
    placeholder: str = "Search patient by ID or name...",
    value: str = "",
    debounce_ms: int = 120,
    reset: bool = False,
    key: str | None = None,
) -> str:
    """Return the current search string; reruns the app as the user types."""
    result = _component(
        placeholder=placeholder,
        value=value or "",
        debounce=int(debounce_ms),
        reset=bool(reset),
        key=key,
        default=value or "",
    )
    if result is None:
        return str(value or "")
    return str(result)
