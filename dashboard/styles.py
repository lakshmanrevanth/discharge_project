"""HITL visual system — CSS + pipeline stepper (spec G/H)."""

from __future__ import annotations

CUSTOM_CSS = r"""

@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

:root {
  --ink: #0f172a;
  --muted: #64748b;
  --line: #e8eef5;
  --surface: #ffffff;
  --canvas: #f1f4f9;
  --teal: #0f766e;
  --teal-deep: #115e59;
  --teal-light: #14b8a6;
  --ok: #15803d;
  --warn: #b45309;
  --bad: #b91c1c;
  --info: #1d4ed8;
  --shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 16px rgba(15, 23, 42, 0.03);
  --shadow-hover: 0 4px 12px rgba(15, 23, 42, 0.08), 0 8px 24px rgba(15, 23, 42, 0.06);
  --radius: 14px;
  --sb-bg: #0b1222;
  --sb-card: #162130;
  --sb-text: #f8fafc;
  --sb-muted: #94a3b8;
  --sb-accent: #14b8a6;
  --sb-border: #1e293b;
  --sb-hover: rgba(20,184,166,0.10);
  --sb-active: rgba(20,184,166,0.18);
  --font: "Plus Jakarta Sans", "Segoe UI", system-ui, sans-serif;
  --display: "Source Serif 4", Georgia, serif;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
  font-family: var(--font) !important;
  color: var(--ink) !important;
}
.stApp { background: var(--canvas) !important; }
.block-container {
  padding-top: 1rem !important;
  padding-bottom: 2.5rem !important;
  padding-left: 2.25rem !important;
  padding-right: 2.25rem !important;
  max-width: 1320px !important;
}

/* =============================================
   TOP NAVBAR — branding | search | patient
   ============================================= */
.top-navbar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.65rem 1.25rem;
  margin-bottom: 1.25rem;
  box-shadow: var(--shadow);
  min-height: 3.5rem;
}
.nav-brand {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
  flex: 0 0 auto;
  min-width: 170px;
}
.nav-brand-title {
  font-family: var(--display) !important;
  font-size: 1.45rem;
  font-weight: 700;
  color: var(--teal-deep) !important;
  -webkit-text-fill-color: var(--teal-deep) !important;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0;
  font-style: italic;
}
.nav-brand-sub {
  font-size: 0.68rem;
  font-weight: 500;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  letter-spacing: 0.01em;
  line-height: 1.2;
}
.nav-search {
  flex: 1 1 auto;
  max-width: 480px;
  position: relative;
}
.nav-search-icon {
  position: absolute;
  left: 0.85rem;
  top: 50%;
  transform: translateY(-50%);
  width: 0.9rem;
  height: 0.9rem;
  pointer-events: none;
  z-index: 2;
  color: var(--muted);
}
.nav-search-icon svg {
  width: 100%;
  height: 100%;
}
.nav-search-kbd {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.68rem;
  font-weight: 600;
  color: #94a3b8;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  padding: 0.12rem 0.35rem;
  pointer-events: none;
  line-height: 1;
}
.nav-patient-area {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex: 0 0 auto;
  margin-left: auto;
}
.nav-icons {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.nav-icon-btn {
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: #f8fafc;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 0.85rem;
  cursor: default;
  transition: background 160ms ease, border-color 160ms ease;
}
.nav-icon-btn:hover {
  background: #f1f5f9;
  border-color: #d1d9e6;
}
.nav-patient-chip {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.3rem 0.65rem 0.3rem 0.35rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: #f8fafc;
  cursor: default;
  transition: background 160ms ease;
}
.nav-patient-chip:hover {
  background: #f1f5f9;
}
.nav-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: var(--teal);
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  font-size: 0.72rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.02em;
  flex: 0 0 auto;
}
.nav-patient-info {
  display: flex;
  flex-direction: column;
  gap: 0;
  line-height: 1.15;
}
.nav-patient-name {
  font-size: 0.85rem;
  font-weight: 650;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  white-space: nowrap;
}
.nav-patient-id {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
.nav-chevron {
  font-size: 0.65rem;
  color: var(--muted);
  margin-left: -0.1rem;
}

/* Navbar search input styling (Streamlit text_input in main area) */
.navbar-search-container .stTextInput {
  margin: 0 !important;
}
.navbar-search-container .stTextInput > div > div {
  min-height: 2.35rem !important;
  max-height: 2.35rem !important;
}
.navbar-search-container .stTextInput input {
  background: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 9px !important;
  min-height: 2.35rem !important;
  max-height: 2.35rem !important;
  font-size: 0.88rem !important;
  font-weight: 400 !important;
  color: var(--ink) !important;
  padding-left: 2.2rem !important;
  padding-right: 3.5rem !important;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.navbar-search-container .stTextInput input:focus {
  border-color: var(--teal-light) !important;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.12) !important;
}
.navbar-search-container .stTextInput input::placeholder {
  color: #94a3b8 !important;
  font-weight: 400 !important;
}
.navbar-search-container [data-testid="InputInstructions"] {
  display: none !important;
}
.navbar-search-container [data-testid="stWidgetLabel"] {
  display: none !important;
}

/* Headings — high contrast */
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
.page-title {
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  opacity: 1 !important;
  font-family: var(--display) !important;
}
.page-title {
  font-size: 1.65rem !important;
  font-weight: 700 !important;
  margin: 0 !important;
  letter-spacing: -0.02em;
  line-height: 1.2 !important;
}
.page-lede {
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.92rem !important;
  margin: 0.35rem 0 0 !important;
  line-height: 1.5 !important;
}
.page-header {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.35rem 1.65rem;
  margin-bottom: 1.25rem;
  box-shadow: var(--shadow);
  border-left: 4px solid var(--teal);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
}
.page-header-left {
  flex: 1 1 auto;
}
.page-header-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.page-header-caption {
  font-size: 0.82rem;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  margin-top: 0.45rem;
  line-height: 1.4;
}
.page-header-caption code {
  background: #e2e8f0;
  padding: 0.15rem 0.45rem;
  border-radius: 5px;
  font-size: 0.78rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

/* =============================================
   SIDEBAR — clinical rail (dark, collapsible)
   ============================================= */
section[data-testid="stSidebar"] {
  background:
    radial-gradient(120% 60% at 0% 0%, rgba(20,184,166,0.10) 0%, transparent 55%),
    linear-gradient(180deg, #0d1728 0%, #0b1222 46%, #080f1d 100%) !important;
  border-right: 1px solid rgba(148, 163, 184, 0.14) !important;
  box-shadow: 10px 0 34px rgba(2, 6, 23, 0.16);
  overflow-x: hidden !important;
}
/* Width only while open — forcing it when closed would leave a dead gutter. */
section[data-testid="stSidebar"][aria-expanded="true"] {
  width: 300px !important;
  min-width: 300px !important;
  max-width: 300px !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] {
  width: 0 !important;
  min-width: 0 !important;
  max-width: 0 !important;
  box-shadow: none;
}
section[data-testid="stSidebar"] > div {
  overflow-x: hidden !important;
  width: 100% !important;
  max-width: 100% !important;
}
/* Static, so the pinned collapse button anchors to the rail, not the scroller. */
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  position: static !important;
  padding: 0 !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  padding: 1.05rem 0.95rem 1.4rem !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar {
  width: 6px;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.22);
  border-radius: 999px;
}

/* —— Collapse control — pinned top-right of the rail —— */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
  position: absolute !important;
  top: 0.85rem !important;
  right: 0.85rem !important;
  left: auto !important;
  width: auto !important;
  height: auto !important;
  min-height: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 0 !important;
  background: transparent !important;
  z-index: 30 !important;
  pointer-events: none;
}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] > * {
  pointer-events: auto;
}
/* Streamlit only reveals this on hover — clinicians should always see the exit. */
[data-testid="stSidebarCollapseButton"] {
  display: inline-flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  width: auto !important;
  height: auto !important;
  margin: 0 !important;
  line-height: 0 !important;
  pointer-events: auto !important;
}
[data-testid="stSidebarCollapseButton"] button {
  width: 2.05rem !important;
  height: 2.05rem !important;
  min-height: 0 !important;
  padding: 0 !important;
  border-radius: 10px !important;
  background: rgba(148, 163, 184, 0.10) !important;
  border: 1px solid rgba(148, 163, 184, 0.20) !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: none !important;
  transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
}
[data-testid="stSidebarCollapseButton"] button:hover {
  background: rgba(20, 184, 166, 0.20) !important;
  border-color: rgba(20, 184, 166, 0.50) !important;
  transform: translateX(-2px);
}
[data-testid="stSidebarCollapseButton"] button:focus-visible {
  outline: 2px solid rgba(20, 184, 166, 0.65) !important;
  outline-offset: 2px !important;
}
[data-testid="stSidebarCollapseButton"] button span,
[data-testid="stSidebarCollapseButton"] button svg {
  color: #cbd5e1 !important;
  fill: #cbd5e1 !important;
  font-size: 1.15rem !important;
}
[data-testid="stSidebarCollapseButton"] button:hover span,
[data-testid="stSidebarCollapseButton"] button:hover svg {
  color: #ffffff !important;
  fill: #ffffff !important;
}

/* —— Re-open control — floating pill in the app toolbar —— */
[data-testid="stExpandSidebarButton"] {
  display: inline-flex !important;
  visibility: visible !important;
  align-items: center !important;
  justify-content: center !important;
  width: 2.3rem !important;
  height: 2.3rem !important;
  min-height: 0 !important;
  padding: 0 !important;
  border-radius: 11px !important;
  background: linear-gradient(140deg, #115e59 0%, #0f766e 100%) !important;
  border: 1px solid rgba(20, 184, 166, 0.45) !important;
  box-shadow: 0 6px 18px rgba(15, 118, 110, 0.28) !important;
  transition: transform 160ms ease, box-shadow 160ms ease;
}
[data-testid="stExpandSidebarButton"]:hover {
  transform: translateX(2px);
  box-shadow: 0 8px 22px rgba(15, 118, 110, 0.36) !important;
}
[data-testid="stExpandSidebarButton"] span,
[data-testid="stExpandSidebarButton"] svg {
  color: #f0fdfa !important;
  fill: #f0fdfa !important;
  font-size: 1.2rem !important;
}

/* —— Brand lockup —— */
.sbx-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0 2.4rem 0.9rem 0.15rem;
  margin-bottom: 0.95rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}
.sbx-brand-mark {
  flex: 0 0 auto;
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 700;
  background: linear-gradient(140deg, #14b8a6 0%, #0f766e 100%);
  color: #04211f !important;
  -webkit-text-fill-color: #04211f !important;
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.28);
}
.sbx-brand-text { display: flex; flex-direction: column; min-width: 0; }
section[data-testid="stSidebar"] .sbx-brand-title {
  font-family: var(--display) !important;
  font-size: 1.12rem;
  font-weight: 700;
  font-style: italic;
  letter-spacing: -0.01em;
  line-height: 1.15;
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
}
section[data-testid="stSidebar"] .sbx-brand-sub {
  font-size: 0.63rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #6f8098 !important;
  -webkit-text-fill-color: #6f8098 !important;
}

/* —— Cards on the rail —— */
.sbx-card {
  background: rgba(148, 163, 184, 0.07);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 13px;
  padding: 0.8rem 0.8rem 0.7rem;
  margin-bottom: 0.8rem;
}
section[data-testid="stSidebar"] .sbx-card-label,
section[data-testid="stSidebar"] .sbx-group-label {
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: #5c6b81 !important;
  -webkit-text-fill-color: #5c6b81 !important;
  margin: 0 0 0.55rem;
}
section[data-testid="stSidebar"] .sbx-group-label {
  margin: 0.35rem 0 0.6rem 0.2rem;
  color: #14b8a6 !important;
  -webkit-text-fill-color: #14b8a6 !important;
}

/* —— Active patient —— */
.sbx-patient-top { display: flex; align-items: center; gap: 0.6rem; }
.sbx-avatar {
  flex: 0 0 auto;
  width: 2.35rem;
  height: 2.35rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: linear-gradient(140deg, #14b8a6 0%, #0f766e 100%);
  color: #052e2b !important;
  -webkit-text-fill-color: #052e2b !important;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.12);
}
.sbx-patient-id { display: flex; flex-direction: column; min-width: 0; }
section[data-testid="stSidebar"] .sbx-patient-name {
  font-size: 0.92rem;
  font-weight: 700;
  line-height: 1.25;
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
section[data-testid="stSidebar"] .sbx-patient-sub {
  font-size: 0.72rem;
  font-weight: 500;
  color: #8ea0b8 !important;
  -webkit-text-fill-color: #8ea0b8 !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sbx-meta {
  margin-top: 0.7rem;
  padding-top: 0.6rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}
.sbx-meta-row { display: flex; align-items: baseline; gap: 0.5rem; }
section[data-testid="stSidebar"] .sbx-meta-k {
  flex: 0 0 4.6rem;
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #5c6b81 !important;
  -webkit-text-fill-color: #5c6b81 !important;
}
section[data-testid="stSidebar"] .sbx-meta-v {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.76rem;
  font-weight: 600;
  color: #d7e0ec !important;
  -webkit-text-fill-color: #d7e0ec !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sbx-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.7rem; }
section[data-testid="stSidebar"] .sbx-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  border: 1px solid transparent;
}
section[data-testid="stSidebar"] .sbx-chip.tone-ok {
  background: rgba(16, 185, 129, 0.16); border-color: rgba(16, 185, 129, 0.32);
  color: #6ee7b7 !important; -webkit-text-fill-color: #6ee7b7 !important;
}
section[data-testid="stSidebar"] .sbx-chip.tone-warn {
  background: rgba(245, 158, 11, 0.18); border-color: rgba(245, 158, 11, 0.34);
  color: #fcd34d !important; -webkit-text-fill-color: #fcd34d !important;
}
section[data-testid="stSidebar"] .sbx-chip.tone-bad {
  background: rgba(239, 68, 68, 0.20); border-color: rgba(239, 68, 68, 0.36);
  color: #fca5a5 !important; -webkit-text-fill-color: #fca5a5 !important;
}
section[data-testid="stSidebar"] .sbx-chip.tone-teal {
  background: rgba(20, 184, 166, 0.18); border-color: rgba(20, 184, 166, 0.34);
  color: #5eead4 !important; -webkit-text-fill-color: #5eead4 !important;
}
section[data-testid="stSidebar"] .sbx-chip.tone-mute {
  background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.22);
  color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important;
}
section[data-testid="stSidebar"] .sbx-empty-title {
  font-size: 0.85rem; font-weight: 700;
  color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important;
}
section[data-testid="stSidebar"] .sbx-empty-body {
  font-size: 0.74rem; line-height: 1.45; margin-top: 0.25rem;
  color: #7d8da3 !important; -webkit-text-fill-color: #7d8da3 !important;
}

/* —— Case progress —— */
.sbx-progress { padding: 0 0.2rem; margin-bottom: 1.05rem; }
.sbx-progress-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 0.4rem;
}
section[data-testid="stSidebar"] .sbx-progress-head > span:first-child {
  font-size: 0.62rem; font-weight: 800; letter-spacing: 0.15em;
  text-transform: uppercase;
  color: #5c6b81 !important; -webkit-text-fill-color: #5c6b81 !important;
}
section[data-testid="stSidebar"] .sbx-progress-count {
  font-size: 0.8rem; font-weight: 800;
  color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .sbx-progress-total {
  font-size: 0.7rem; font-weight: 600;
  color: #64748b !important; -webkit-text-fill-color: #64748b !important;
}
.sbx-bar {
  height: 5px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  overflow: hidden;
}
.sbx-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 420ms cubic-bezier(0.4, 0, 0.2, 1);
  background: linear-gradient(90deg, #14b8a6, #2dd4bf);
}
.sbx-bar-fill.tone-warn { background: linear-gradient(90deg, #d97706, #fbbf24); }
.sbx-bar-fill.tone-bad { background: linear-gradient(90deg, #dc2626, #f87171); }
.sbx-bar-fill.tone-mute { background: rgba(148, 163, 184, 0.35); }
section[data-testid="stSidebar"] .sbx-progress-foot {
  margin-top: 0.35rem;
  font-size: 0.7rem; font-weight: 500;
  color: #7d8da3 !important; -webkit-text-fill-color: #7d8da3 !important;
}

/* —— Navigation (radio rendered as an icon nav list) —— */
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
  gap: 0.18rem !important;
}
section[data-testid="stSidebar"] .stRadio label {
  position: relative !important;
  display: flex !important;
  align-items: center !important;
  gap: 0.55rem !important;
  padding: 0.58rem 0.6rem 0.58rem 0.55rem !important;
  border-radius: 11px !important;
  border: 1px solid transparent !important;
  margin-bottom: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  font-size: 0.86rem !important;
  font-weight: 550 !important;
  line-height: 1.3 !important;
  color: #b9c6d6 !important;
  -webkit-text-fill-color: #b9c6d6 !important;
  cursor: pointer;
  transition: background 170ms ease, border-color 170ms ease, color 170ms ease,
    box-shadow 170ms ease;
}
/* Icon tile — glyph comes from the per-index rules injected at render time. */
section[data-testid="stSidebar"] .stRadio label::before {
  flex: 0 0 auto;
  width: 1.7rem;
  height: 1.7rem;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  line-height: 1;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.14);
  color: #8ea0b8;
  transition: background 170ms ease, border-color 170ms ease, color 170ms ease;
}
/* Native radio dot collapsed to zero width — the input stays clickable.
   The mark is the first child of the row that also holds the label text. */
section[data-testid="stSidebar"] .stRadio label
  div:has(> div[data-testid="stMarkdownContainer"]) > div:first-child {
  width: 0 !important;
  min-width: 0 !important;
  flex: 0 0 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  opacity: 0 !important;
  overflow: hidden !important;
}
section[data-testid="stSidebar"] .stRadio label > div,
section[data-testid="stSidebar"] .stRadio label > div > div {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
}
section[data-testid="stSidebar"] .stRadio label [data-testid="stMarkdownContainer"] {
  flex: 1 1 auto;
  min-width: 0;
}
section[data-testid="stSidebar"] .stRadio label [data-testid="stMarkdownContainer"] p {
  margin: 0 !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: inherit !important;
  -webkit-text-fill-color: inherit !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(20, 184, 166, 0.09) !important;
  border-color: rgba(20, 184, 166, 0.16) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
section[data-testid="stSidebar"] .stRadio label:hover::before {
  background: rgba(20, 184, 166, 0.14);
  border-color: rgba(20, 184, 166, 0.26);
  color: #5eead4;
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked),
section[data-testid="stSidebar"] .stRadio label[data-selected="true"] {
  background: linear-gradient(
    90deg, rgba(20, 184, 166, 0.22) 0%, rgba(20, 184, 166, 0.06) 100%
  ) !important;
  border-color: rgba(20, 184, 166, 0.34) !important;
  font-weight: 700 !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
  box-shadow: inset 3px 0 0 0 #14b8a6;
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked)::before,
section[data-testid="stSidebar"] .stRadio label[data-selected="true"]::before {
  background: rgba(20, 184, 166, 0.22);
  border-color: rgba(20, 184, 166, 0.45);
  color: #5eead4;
}
section[data-testid="stSidebar"] .stRadio label:focus-within {
  outline: 2px solid rgba(20, 184, 166, 0.55);
  outline-offset: 1px;
}
section[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {
  display: none !important;
}

/* —— Next-action callout —— */
.sbx-alert {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  margin: 1.1rem 0 0.9rem;
  padding: 0.7rem 0.75rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(148, 163, 184, 0.07);
}
.sbx-alert-icon {
  flex: 0 0 auto;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 800;
  background: rgba(148, 163, 184, 0.16);
  color: #cbd5e1 !important;
  -webkit-text-fill-color: #cbd5e1 !important;
}
.sbx-alert-text { display: flex; flex-direction: column; min-width: 0; }
section[data-testid="stSidebar"] .sbx-alert-title {
  font-size: 0.78rem; font-weight: 700; line-height: 1.3;
  color: #e8eef6 !important; -webkit-text-fill-color: #e8eef6 !important;
}
section[data-testid="stSidebar"] .sbx-alert-body {
  font-size: 0.72rem; font-weight: 500; line-height: 1.4; margin-top: 0.1rem;
  color: #93a3b8 !important; -webkit-text-fill-color: #93a3b8 !important;
}
.sbx-alert.tone-bad {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.10);
}
.sbx-alert.tone-bad .sbx-alert-icon {
  background: rgba(239, 68, 68, 0.22);
  color: #fca5a5 !important; -webkit-text-fill-color: #fca5a5 !important;
}
.sbx-alert.tone-warn {
  border-color: rgba(245, 158, 11, 0.32);
  background: rgba(245, 158, 11, 0.10);
}
.sbx-alert.tone-warn .sbx-alert-icon {
  background: rgba(245, 158, 11, 0.22);
  color: #fcd34d !important; -webkit-text-fill-color: #fcd34d !important;
}
.sbx-alert.tone-ok {
  border-color: rgba(16, 185, 129, 0.30);
  background: rgba(16, 185, 129, 0.10);
}
.sbx-alert.tone-ok .sbx-alert-icon {
  background: rgba(16, 185, 129, 0.20);
  color: #6ee7b7 !important; -webkit-text-fill-color: #6ee7b7 !important;
}
.sbx-alert.tone-info {
  border-color: rgba(20, 184, 166, 0.30);
  background: rgba(20, 184, 166, 0.09);
}
.sbx-alert.tone-info .sbx-alert-icon {
  background: rgba(20, 184, 166, 0.20);
  color: #5eead4 !important; -webkit-text-fill-color: #5eead4 !important;
}

/* —— Footer —— */
.sbx-foot {
  margin-top: 0.35rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}
.sbx-foot-row { display: flex; align-items: center; gap: 0.4rem; }
.sbx-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.16);
  flex: 0 0 auto;
}
section[data-testid="stSidebar"] .sbx-foot-row > span:nth-child(2) {
  font-size: 0.7rem; font-weight: 600;
  color: #93a3b8 !important; -webkit-text-fill-color: #93a3b8 !important;
}
section[data-testid="stSidebar"] code.sbx-foot-mono {
  margin-left: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  font-size: 0.66rem !important;
  padding: 0.1rem 0.38rem !important;
  border-radius: 6px !important;
  background: rgba(148, 163, 184, 0.12) !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  color: #a9b7c8 !important; -webkit-text-fill-color: #a9b7c8 !important;
}
section[data-testid="stSidebar"] a.sbx-foot-link {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.22rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  font-size: 0.66rem !important;
  padding: 0.12rem 0.4rem !important;
  border-radius: 6px !important;
  text-decoration: none !important;
  background: rgba(20, 184, 166, 0.14) !important;
  border: 1px solid rgba(20, 184, 166, 0.30) !important;
  color: #5eead4 !important;
  -webkit-text-fill-color: #5eead4 !important;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
}
section[data-testid="stSidebar"] a.sbx-foot-link:hover {
  background: rgba(20, 184, 166, 0.26) !important;
  border-color: rgba(20, 184, 166, 0.55) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
section[data-testid="stSidebar"] a.sbx-foot-link:focus-visible {
  outline: 2px solid rgba(20, 184, 166, 0.65);
  outline-offset: 2px;
}
.sbx-foot-ext { font-size: 0.6rem; line-height: 1; opacity: 0.85; }

section[data-testid="stSidebar"] .sbx-foot-note {
  margin-top: 0.4rem;
  font-size: 0.66rem; font-weight: 500; letter-spacing: 0.01em;
  color: #8496ac !important; -webkit-text-fill-color: #8496ac !important;
}

/* —— Baseline text colour + chrome resets on the rail —— */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color: var(--sb-text) !important;
  -webkit-text-fill-color: var(--sb-text) !important;
}
section[data-testid="stSidebar"] .stSelectbox,
section[data-testid="stSidebar"] .stRadio,
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  max-width: 100% !important;
  overflow-x: hidden !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],
section[data-testid="stSidebar"] [data-testid="stExpander"],
section[data-testid="stSidebar"] [data-testid="stAlert"],
section[data-testid="stSidebar"] .stAlert,
section[data-testid="stSidebar"] div[data-testid="stDecoration"],
section[data-testid="stSidebar"] [data-testid="stElementContainer"],
section[data-testid="stSidebar"] [data-testid="element-container"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
  background: transparent !important;
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
section[data-testid="stSidebar"] hr {
  border: none !important;
  border-top: 1px solid rgba(148, 163, 184, 0.16) !important;
  background: transparent !important;
  margin: 1rem 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:empty,
section[data-testid="stSidebar"] .element-container:has(> div:empty) {
  display: none !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
  display: none !important;
}

/* Legacy sidebar fragments — superseded by the rail, still hidden if emitted. */
section[data-testid="stSidebar"] .brand-lockup,
section[data-testid="stSidebar"] .patient-card,
section[data-testid="stSidebar"] .sb-empty-hint,
section[data-testid="stSidebar"] .sb-suggest-label,
section[data-testid="stSidebar"] .nav-group-label {
  display: none !important;
}
/* Search moved to the main column — keep the rail free of its widgets. */
section[data-testid="stSidebar"] .stCustomComponentV1,
section[data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(iframe),
section[data-testid="stSidebar"] div[data-testid="element-container"]:has(iframe),
section[data-testid="stSidebar"] iframe {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  max-height: 0 !important;
  overflow: hidden !important;
}

/* =============================================
   STATUS STRIP — premium metric cards
   ============================================= */
.status-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.85rem;
  margin-bottom: 1rem;
}
.status-cell {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem 1.1rem;
  min-height: 5rem;
  box-shadow: var(--shadow);
  transition: box-shadow 200ms ease, transform 200ms ease, border-color 200ms ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.4rem;
}
.status-cell:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
  border-color: #d1dbe8;
}
.status-label {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-weight: 650;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 6px;
  background: #f0fdfa;
  color: var(--teal) !important;
  -webkit-text-fill-color: var(--teal) !important;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
  flex: 0 0 auto;
}
.status-value {
  font-size: 1.08rem; font-weight: 700; margin-top: 0;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  line-height: 1.25;
  word-break: break-word;
}
.status-value.ok { color: var(--ok) !important; -webkit-text-fill-color: var(--ok) !important; }
.status-value.warn { color: var(--warn) !important; -webkit-text-fill-color: var(--warn) !important; }
.status-value.bad { color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important; }
.status-value.teal { color: var(--teal-deep) !important; -webkit-text-fill-color: var(--teal-deep) !important; }

.chip {
  display: inline-flex; align-items: center;
  padding: 0.22rem 0.6rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 700; letter-spacing: 0.02em;
}
.chip.badge-ok { background: #ecfdf5; color: var(--ok) !important; -webkit-text-fill-color: var(--ok) !important; }
.chip.badge-warn { background: #fffbeb; color: var(--warn) !important; -webkit-text-fill-color: var(--warn) !important; }
.chip.badge-bad { background: #fef2f2; color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important; }
.chip.badge-mute { background: #f1f5f9; color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; }
.chip.badge-sea { background: #f0fdfa; color: var(--teal-deep) !important; -webkit-text-fill-color: var(--teal-deep) !important; }

/* Pipeline — workflow pills */
.pipeline-track {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.85rem 1.15rem;
  margin-bottom: 1.5rem;
  box-shadow: var(--shadow);
}
.pipe-sep {
  width: 14px; height: 1.5px;
  background: #dbe4ef;
  flex: 0 0 auto;
  border-radius: 1px;
}
.pipe-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.42rem 0.8rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  background: #f8fafc;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  border: 1px solid transparent;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
}
.pipe-pill .pipe-icon { font-size: 0.72rem; line-height: 1; }
.pipe-pill.done {
  background: #ecfdf5;
  color: var(--ok) !important; -webkit-text-fill-color: var(--ok) !important;
  border-color: #bbf7d0;
}
.pipe-pill.active {
  background: #f0fdfa;
  color: var(--teal-deep) !important; -webkit-text-fill-color: var(--teal-deep) !important;
  border-color: #99f6e4;
}
.pipe-pill.blocked {
  background: #fef2f2;
  color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important;
  border-color: #fecaca;
}
.pipe-pill.skipped {
  background: #fffbeb;
  color: var(--warn) !important; -webkit-text-fill-color: var(--warn) !important;
}
.pipe-pill.pending {
  background: #f8fafc;
  color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important;
}

/* legacy pipeline-line kept for safety */
.pipeline-line { display: none; }

.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.15rem 1.25rem;
  margin-bottom: 1rem;
  box-shadow: var(--shadow);
}
.badge {
  display: inline-flex;
  align-items: center;
  height: 1.7rem;
  padding: 0 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0.01em;
  line-height: 1;
}
.badge-ok { background: #ecfdf5; color: #166534 !important; -webkit-text-fill-color: #166534 !important; }
.badge-warn { background: #fffbeb; color: #92400e !important; -webkit-text-fill-color: #92400e !important; }
.badge-bad { background: #fef2f2; color: #991b1b !important; -webkit-text-fill-color: #991b1b !important; }
.badge-mute { background: #f1f5f9; color: #475569 !important; -webkit-text-fill-color: #475569 !important; }
.badge-info { background: #eff6ff; color: var(--info) !important; -webkit-text-fill-color: var(--info) !important; }
.badge-sea { background: #f0fdfa; color: var(--teal-deep) !important; -webkit-text-fill-color: var(--teal-deep) !important; }

.val-status-card {
  margin-top: 0.25rem;
  margin-bottom: 1.5rem;
  padding: 1rem 1.15rem;
}
.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.rules-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.85rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--line);
}
.rules-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
.rules-hash,
code.rules-hash {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  font-size: 0.78rem !important;
  line-height: 1.4 !important;
  color: #334155 !important;
  -webkit-text-fill-color: #334155 !important;
  background: #f8fafc !important;
  border: 1px solid var(--line) !important;
  border-radius: 8px !important;
  padding: 0.35rem 0.55rem !important;
  word-break: break-all;
  max-width: 100%;
  display: inline-block;
}

.section-label {
  font-family: var(--font) !important;
  font-size: 1.05rem !important;
  font-weight: 700 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin: 1.5rem 0 0.75rem !important;
  letter-spacing: -0.01em;
}

.finding {
  border: 1px solid var(--line);
  border-left: 4px solid var(--teal);
  background: #fcfdff;
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 0.95rem 1.15rem;
  margin-bottom: 0.75rem;
  box-shadow: var(--shadow);
}
.finding.critical {
  border-left-color: var(--bad);
  background: #fff8f8;
}
.finding.warning {
  border-left-color: var(--warn);
  background: #fffdf5;
}
.finding.info {
  border-left-color: var(--info);
  background: #f8fbff;
}
.finding-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.35rem;
}
.finding-sev {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}
.finding.critical .finding-sev {
  color: var(--bad) !important;
  -webkit-text-fill-color: var(--bad) !important;
}
.finding.warning .finding-sev {
  color: var(--warn) !important;
  -webkit-text-fill-color: var(--warn) !important;
}
.finding-action {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
.finding-rule {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin-bottom: 0.35rem;
  word-break: break-word;
}
.finding-msg {
  font-size: 0.9rem;
  line-height: 1.55;
  color: #475569 !important;
  -webkit-text-fill-color: #475569 !important;
}

.gap-panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem 1.1rem;
  margin-bottom: 1rem;
  min-height: 5.5rem;
  box-shadow: var(--shadow);
}
.gap-panel-title {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin-bottom: 0.65rem;
}
.gap-list {
  margin: 0 0 0 1.05rem !important;
  padding: 0 !important;
}
.gap-list li {
  margin: 0.35rem 0 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  font-size: 0.9rem;
  line-height: 1.45;
}

.empty-state {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.4;
}
.empty-ok {
  background: #f0fdf4;
  color: #166534 !important;
  -webkit-text-fill-color: #166534 !important;
  border: 1px solid #bbf7d0;
}
.empty-icon {
  font-size: 0.85rem;
  line-height: 1;
}
.empty-text { font-weight: 600; }

.artifact-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.55rem;
  margin-bottom: 0.55rem;
}
.artifact-kind {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  min-width: 3.5rem;
}
.artifact-uri,
code.artifact-uri {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  font-size: 0.78rem !important;
  background: #f8fafc !important;
  border: 1px solid var(--line) !important;
  border-radius: 8px !important;
  padding: 0.3rem 0.5rem !important;
  color: #334155 !important;
  -webkit-text-fill-color: #334155 !important;
  word-break: break-all;
  max-width: 100%;
}
a.artifact-link,
a.artifact-uri.artifact-link {
  font-family: var(--font) !important;
  font-weight: 650 !important;
  text-decoration: none !important;
  background: #f0fdfa !important;
  border-color: #99f6e4 !important;
  color: var(--teal-deep) !important;
  -webkit-text-fill-color: var(--teal-deep) !important;
  word-break: normal;
  transition: background 160ms ease, border-color 160ms ease;
}
a.artifact-link:hover {
  background: #ccfbf1 !important;
  border-color: var(--teal-light) !important;
}
.summary-trace-note {
  margin: 0.85rem 0 0 !important;
  font-size: 0.82rem;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
.summary-trace-note a {
  color: var(--teal-deep) !important;
  -webkit-text-fill-color: var(--teal-deep) !important;
  font-weight: 650;
  text-decoration: none;
}
.summary-trace-note a:hover { text-decoration: underline; }

/* Metrics row — keep horizontal, polish type */
div[data-testid="stMetric"] {
  background: transparent !important;
  padding: 0.15rem 0.25rem 0.35rem !important;
}
div[data-testid="stMetric"] label,
div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  font-size: 0.72rem !important;
  font-weight: 650 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  line-height: 1.2 !important;
}
div[data-testid="stHorizontalBlock"] {
  gap: 1rem !important;
  margin-bottom: 0.35rem !important;
}

/* Expanders — Audit artifacts / More case fields / Audit notes */
div[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow) !important;
  margin: 0.65rem 0 0.85rem !important;
  overflow: hidden;
}
div[data-testid="stExpander"] details {
  border: none !important;
}
div[data-testid="stExpander"] summary {
  padding: 0.7rem 1rem !important;
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
}
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] {
  color: var(--ink) !important;
}
div[data-testid="stExpander"] summary span,
div[data-testid="stExpander"] summary p {
  font-weight: 700 !important;
  color: #0f172a !important;
  -webkit-text-fill-color: #0f172a !important;
  font-size: 0.95rem !important;
  line-height: 1.25 !important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"],
div[data-testid="stExpander"] .streamlit-expanderContent {
  padding: 0.15rem 1rem 0.9rem !important;
}

/* Code / JSON blocks */
[data-testid="stCode"],
pre, code {
  border-radius: 10px !important;
}
[data-testid="stCode"] {
  background: #f8fafc !important;
  border: 1px solid var(--line) !important;
  padding: 0.75rem 0.9rem !important;
  max-height: 280px;
  overflow: auto !important;
  font-size: 0.8rem !important;
}

/* Discharge Summary — hero letter */
.summary-hero {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.85rem 2rem 1.5rem;
  margin: 0 0 1.25rem;
  box-shadow: var(--shadow);
}
.summary-hero-head {
  margin-bottom: 1.35rem;
  padding-bottom: 1.15rem;
  border-bottom: 1px solid var(--line);
}
.summary-hero-kicker {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--teal) !important;
  -webkit-text-fill-color: var(--teal) !important;
  margin-bottom: 0.45rem;
}
.summary-hero-title {
  font-family: var(--display) !important;
  font-size: 1.75rem !important;
  font-weight: 700 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin: 0 !important;
  letter-spacing: -0.02em;
  line-height: 1.2 !important;
}
.summary-hero-lede {
  margin: 0.45rem 0 0 !important;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.95rem !important;
  line-height: 1.5 !important;
}
.summary-hero-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.summary-block {
  background: #fbfcfe;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.1rem 1.2rem 1rem;
}
.summary-block-title {
  font-family: var(--font) !important;
  font-size: 1.25rem !important;
  font-weight: 600 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin: 0 0 0.7rem !important;
  letter-spacing: -0.01em;
}
.summary-block-body {
  color: var(--ink) !important;
  font-size: 0.98rem !important;
  line-height: 1.65 !important;
}
.summary-block-body p {
  margin: 0 0 0.55rem !important;
  color: var(--ink) !important;
}
.summary-block-body p:last-child { margin-bottom: 0 !important; }
.summary-block-body ul {
  margin: 0.15rem 0 0.25rem 1.15rem !important;
  padding: 0 !important;
}
.summary-block-body li {
  margin: 0.35rem 0 !important;
  color: var(--ink) !important;
  padding-left: 0.15rem;
}
.summary-block-body strong {
  color: var(--teal-deep) !important;
  font-weight: 650 !important;
}
.summary-block-body code {
  background: #f1f5f9;
  border-radius: 6px;
  padding: 0.1rem 0.35rem;
  font-size: 0.88em;
}

/* legacy summary classes unused */
.summary-letter, .summary-section { display: none; }

/* HITL Corrections — zones + workflow chrome */
.hitl-zone {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  margin: 1.5rem 0 0.5rem;
  box-shadow: none;
}
.hitl-zone.hitl2,
.hitl-zone.hitl1,
.hitl-zone.clear {
  border-top: none;
  padding-top: 0;
}
.hitl-zone-head {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  flex-wrap: wrap !important;
  gap: 0.45rem !important;
  margin-bottom: 0.2rem !important;
}
.hitl-zone-head .label,
.hitl-editor-block .ttl .label,
.hitl-section-title,
.corr-group-title {
  font-family: var(--font) !important;
  font-size: 1.2rem !important;
  font-weight: 700 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin-right: 0.1rem !important;
  letter-spacing: -0.015em;
  line-height: 1.25 !important;
}
.hitl-zone-head .sep,
.hitl-editor-block .ttl .sep {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-weight: 600; margin: 0 0.1rem;
}
.hitl-zone-head .tag,
.hitl-editor-block .tag,
.hitl-issue-top .tag,
.corr-group-head .tag {
  display: inline-flex !important;
  align-items: center !important;
  font-size: 0.66rem !important; font-weight: 700 !important;
  letter-spacing: 0.06em; text-transform: uppercase;
  padding: 0.18rem 0.5rem !important; border-radius: 999px !important;
  margin-left: 0.1rem !important;
  height: 1.35rem;
}
.tag-hitl2 { background: #fee2e2; color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important; }
.tag-hitl1 { background: #ffedd5; color: #c2410c !important; -webkit-text-fill-color: #c2410c !important; }
.tag-shared { background: #e0e7ff; color: #3730a3 !important; -webkit-text-fill-color: #3730a3 !important; }
.hitl-zone-lede,
.hitl-section-lede {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.88rem !important; margin: 0 0 0.75rem !important; line-height: 1.4 !important;
}

.hitl-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 1rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.1rem 1.25rem;
  margin: 0 0 1.25rem;
  box-shadow: var(--shadow);
  border-left: 4px solid var(--teal);
}
.hitl-overview-kicker {
  font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--teal) !important;
  -webkit-text-fill-color: var(--teal) !important; margin-bottom: 0.25rem;
}
.hitl-overview-title {
  font-family: var(--display) !important;
  font-size: 1.5rem !important; font-weight: 700 !important;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  letter-spacing: -0.02em; margin: 0 !important; line-height: 1.2;
}
.hitl-overview-lede {
  margin: 0.35rem 0 0 !important; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important; font-size: 0.88rem !important;
  line-height: 1.45 !important;
}
.hitl-overview-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.6rem;
}
.hitl-ov-metric {
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
}
.hitl-ov-metric .k {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}
.hitl-ov-metric .v {
  margin-top: 0.2rem; font-size: 1.15rem; font-weight: 700;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  line-height: 1.2;
}
.hitl-ov-metric .v.tone-bad { color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important; }
.hitl-ov-metric .v.tone-warn { color: var(--warn) !important; -webkit-text-fill-color: var(--warn) !important; }

.hitl-issue-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-left: 4px solid var(--line);
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 0.85rem 1rem;
  margin: 0 0 0.55rem;
  box-shadow: var(--shadow);
}
.hitl-issue-card.critical {
  border-left-color: var(--bad);
  background: #fffafa;
}
.hitl-issue-card.warning {
  border-left-color: #d97706;
  background: #fffdf8;
}
.hitl-issue-top {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem;
  margin-bottom: 0.35rem;
}
.hitl-issue-title {
  font-size: 0.98rem; font-weight: 700;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
}
.hitl-kv {
  display: grid;
  grid-template-columns: 7.75rem minmax(0, 1fr);
  gap: 0.2rem 0.65rem;
  margin-top: 0.25rem;
  align-items: start;
}
.hitl-kv .k {
  font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important; padding-top: 0.1rem;
}
.hitl-kv .v {
  font-size: 0.88rem; line-height: 1.4;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
}
.hitl-kv .v.muted { color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; }
.hitl-kv .v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
}
.hitl-kv .v.sev-critical { color: var(--bad) !important; -webkit-text-fill-color: var(--bad) !important; font-weight: 700; }
.hitl-kv .v.sev-warning { color: #c2410c !important; -webkit-text-fill-color: #c2410c !important; font-weight: 700; }

.hitl-alert {
  display: flex; gap: 0.55rem; align-items: flex-start;
  border: 1px solid var(--line); border-radius: 10px;
  padding: 0.55rem 0.75rem; margin: 0 0 0.55rem;
  background: #f8fafc;
}
.hitl-alert.bad { background: #fff5f5; border-color: #fecaca; }
.hitl-alert.warn { background: #fffbeb; border-color: #fde68a; }
.hitl-alert-icon {
  width: 1.25rem; height: 1.25rem; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.7rem; font-weight: 800; flex: 0 0 auto;
  background: #fee2e2; color: var(--bad) !important;
}
.hitl-alert.warn .hitl-alert-icon { background: #fef3c7; color: #b45309 !important; }
.hitl-alert-title {
  font-size: 0.86rem; font-weight: 700;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
}
.hitl-alert-body {
  font-size: 0.8rem; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important; line-height: 1.35; margin-top: 0.1rem;
}

.hitl-section-title {
  margin: 1.5rem 0 0.25rem !important;
}
.hitl-section-lede {
  margin: 0 0 0.75rem !important;
}

/* Corrections panels — st.container(border=True) + compact header */
div[data-testid="stVerticalBlockBorderWrapper"] {
  margin: 0 0 0.85rem !important;
  border-radius: var(--radius) !important;
  border-color: var(--line) !important;
  background: var(--surface) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
  gap: 0.35rem !important;
  padding: 0.2rem 0.15rem 0.45rem !important;
}
.corr-panel-mark {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}
.corr-group-banner {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0.35rem 0 0.5rem;
  margin: 0;
  border-bottom: 1px solid var(--line);
  box-shadow: none;
}
.corr-group-head {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem;
}
.corr-group-hint {
  margin-top: 0.25rem; font-size: 0.82rem; line-height: 1.35;
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
}
.corr-opt-label {
  font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  margin: 0.65rem 0 0.25rem;
}
.audit-card-lede {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.84rem; margin: 0 0 0.55rem; line-height: 1.4;
}
.hitl-clear-banner {
  display: flex; gap: 0.55rem; align-items: flex-start;
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: var(--radius);
  padding: 0.85rem 1rem; margin: 0.85rem 0 0.75rem;
}
.empty-state {
  margin: 0 0 0.55rem !important;
  padding: 0.6rem 0.8rem !important;
}

/* Label → input proximity + consistent control height */
[data-testid="stAppViewContainer"] div[data-testid="stWidgetLabel"] {
  margin-bottom: 0.2rem !important;
  padding-bottom: 0 !important;
  min-height: 0 !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stWidgetLabel"] p,
[data-testid="stAppViewContainer"] div[data-testid="stWidgetLabel"] label {
  font-size: 0.82rem !important;
  font-weight: 600 !important;
  color: #475569 !important;
  -webkit-text-fill-color: #475569 !important;
  line-height: 1.25 !important;
}
[data-testid="stAppViewContainer"] .stTextInput,
[data-testid="stAppViewContainer"] .stSelectbox,
[data-testid="stAppViewContainer"] .stTextArea,
[data-testid="stAppViewContainer"] .stCheckbox,
[data-testid="stAppViewContainer"] .stNumberInput,
[data-testid="stAppViewContainer"] .stDateInput {
  margin-bottom: 0.45rem !important;
}
[data-testid="stAppViewContainer"] .stTextInput > div > div,
[data-testid="stAppViewContainer"] .stSelectbox > div > div,
[data-testid="stAppViewContainer"] .stNumberInput > div > div,
[data-testid="stAppViewContainer"] .stDateInput > div > div {
  min-height: 2.5rem !important;
}
[data-testid="stAppViewContainer"] .stTextInput input,
[data-testid="stAppViewContainer"] .stNumberInput input,
[data-testid="stAppViewContainer"] .stDateInput input,
[data-testid="stAppViewContainer"] .stSelectbox [data-baseweb="select"] > div {
  min-height: 2.5rem !important;
  border-radius: 10px !important;
  font-size: 0.95rem !important;
}
[data-testid="stAppViewContainer"] .stTextArea textarea {
  border-radius: 10px !important;
  font-size: 0.95rem !important;
  line-height: 1.45 !important;
  min-height: 6.5rem !important;
}

/* —— Upload New Patients (standalone, premium minimal) —— */
.upload-page {
  max-width: 880px;
  margin: 0 auto 0.55rem;
  text-align: center;
}
.upload-page-title {
  font-family: var(--display) !important;
  font-size: 1.65rem !important;
  font-weight: 700 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  letter-spacing: -0.02em;
  margin: 0 0 0.2rem !important;
  line-height: 1.2 !important;
}
.upload-page-lede {
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.9rem !important;
  line-height: 1.4 !important;
  margin: 0 auto !important;
  max-width: 30rem;
}
.upload-field-title {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #64748b !important;
  -webkit-text-fill-color: #64748b !important;
  margin: 0 0 0.35rem;
  text-align: center;
}
.upload-formats-note {
  margin: 0.35rem 0 0.55rem !important;
  text-align: center;
  font-size: 0.78rem !important;
  color: #94a3b8 !important;
  -webkit-text-fill-color: #94a3b8 !important;
  line-height: 1.35 !important;
}
.upload-cta-mark { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }

.upload-success-banner {
  max-width: 880px;
  margin: 0.85rem auto 0;
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.85rem 1.05rem;
  border-radius: var(--radius);
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  text-align: left;
}
.upload-success-check {
  flex: 0 0 auto;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  background: #15803d;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  font-size: 0.85rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.05rem;
}
.upload-success-banner strong {
  display: block;
  color: #065f46 !important;
  -webkit-text-fill-color: #065f46 !important;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.3;
}
.upload-success-meta {
  display: block;
  margin-top: 0.2rem;
  color: #047857 !important;
  -webkit-text-fill-color: #047857 !important;
  font-size: 0.8rem;
  line-height: 1.35;
  word-break: break-word;
}

/* Main upload container */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) {
  max-width: 880px;
  margin-left: auto !important;
  margin-right: auto !important;
  border-radius: var(--radius) !important;
  border: 1px solid var(--line) !important;
  background: var(--surface) !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03), 0 8px 24px rgba(15, 23, 42, 0.04) !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) > div[data-testid="stVerticalBlock"] {
  gap: 0.35rem !important;
  padding: 1.55rem 1.85rem 1.4rem !important;
}
.upload-card-mark { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }

/* Patient ID — tighter under subtitle */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stTextInput"] {
  margin-bottom: 0.45rem !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stTextInput"] label p {
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  color: #475569 !important;
  -webkit-text-fill-color: #475569 !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stTextInput"] input {
  border-radius: 10px !important;
  min-height: 2.55rem !important;
}

/* Drop zones — compact, centered, premium */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stFileUploader {
  margin-bottom: 0 !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"] {
  min-height: 4.1rem !important;
  padding: 0.7rem 0.75rem !important;
  border-radius: var(--radius) !important;
  border: 1.5px dashed #cbd5e1 !important;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.35rem !important;
  transition: border-color 160ms ease, background 160ms ease, box-shadow 160ms ease !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"]:hover {
  border-color: #0f766e !important;
  background: linear-gradient(180deg, #f0fdfa 0%, #ecfeff 100%) !important;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.08) !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"]:focus-within {
  border-color: #0f766e !important;
  border-style: solid !important;
  background: #f0fdfa !important;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12) !important;
}

/* Hide Streamlit's long file limit text */
[data-testid="stAppViewContainer"]:has(.upload-page) [data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stAppViewContainer"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzoneInstructions"] {
  display: none !important;
}

.upload-slot-hint {
  margin: 0.25rem 0 0;
  text-align: center;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.03em;
  color: #94a3b8 !important;
  -webkit-text-fill-color: #94a3b8 !important;
  line-height: 1.3;
}
.upload-selected {
  margin: 0.3rem 0 0;
  text-align: center;
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46 !important;
  -webkit-text-fill-color: #065f46 !important;
  font-size: 0.84rem;
  font-weight: 600;
  word-break: break-word;
  line-height: 1.3;
}

/* Upload button + icon */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"] button {
  border-radius: 9px !important;
  font-size: 0.82rem !important;
  font-weight: 650 !important;
  padding: 0.4rem 0.85rem !important;
  min-height: 2.15rem !important;
  border-color: #cbd5e1 !important;
  color: #0f766e !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"] button:hover {
  border-color: #0f766e !important;
  background: #f0fdfa !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"] button svg,
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderDropzone"] button [data-testid="stIconMaterial"] {
  width: 1.35rem !important;
  height: 1.35rem !important;
  font-size: 1.35rem !important;
  color: #0f766e !important;
}

/* Selected file chip */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderFile"],
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .uploadedFile {
  margin: 0 !important;
  width: 100% !important;
  padding: 0.45rem 0.55rem !important;
  border-radius: 10px !important;
  background: #ecfdf5 !important;
  border: 1px solid #a7f3d0 !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderFileName"]::before,
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .uploadedFileName::before {
  content: "✓ ";
  color: #065f46;
  font-weight: 700;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderFileName"],
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .uploadedFileName {
  color: #065f46 !important;
  -webkit-text-fill-color: #065f46 !important;
  font-weight: 600 !important;
  font-size: 0.84rem !important;
  word-break: break-word;
  white-space: normal !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderFile"] small,
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) [data-testid="stFileUploaderFileSize"],
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .uploadedFileSize {
  display: none !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stFileUploader:has([data-testid="stFileUploaderFile"]) [data-testid="stFileUploaderDropzone"],
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stFileUploader:has(.uploadedFile) [data-testid="stFileUploaderDropzone"] {
  border-style: solid !important;
  border-color: #a7f3d0 !important;
  background: #f0fdf4 !important;
  min-height: 3.6rem !important;
}

/* Primary CTA — more prominent */
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton {
  margin-top: 0.1rem !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton > button[kind="primary"],
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton > button[data-testid="baseButton-primary"] {
  min-height: 2.85rem !important;
  border-radius: 10px !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em !important;
  background: linear-gradient(180deg, #0f766e 0%, #0d5f59 100%) !important;
  border: none !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 6px 16px rgba(15, 118, 110, 0.22) !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton > button[kind="primary"]:hover:not(:disabled),
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton > button[data-testid="baseButton-primary"]:hover:not(:disabled) {
  background: linear-gradient(180deg, #0d9488 0%, #0f766e 100%) !important;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.1), 0 8px 20px rgba(15, 118, 110, 0.28) !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.upload-card-mark) .stButton > button:disabled {
  opacity: 0.45 !important;
  box-shadow: none !important;
}

/* legacy issue styles kept for safety */
.hitl-issue {
  border: 1px solid #fecaca;
  border-left: 4px solid var(--bad);
  background: #fff7f7;
  border-radius: 0 10px 10px 0;
  padding: 0.75rem 0.95rem;
  margin-bottom: 0.65rem;
}
.hitl-issue .rule {
  font-weight: 700; color: var(--bad) !important;
  -webkit-text-fill-color: var(--bad) !important; font-size: 0.9rem;
}
.hitl-issue .fix {
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  font-size: 0.86rem; margin-top: 0.3rem;
}
.hitl-issue .msg {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.78rem; margin-top: 0.3rem; line-height: 1.4;
}
.hitl-soft {
  border: 1px solid #fed7aa;
  border-left: 4px solid #d97706;
  background: #fffbeb;
  border-radius: 0 10px 10px 0;
  padding: 0.65rem 0.9rem;
  margin-bottom: 0.55rem;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  font-size: 0.86rem;
}
.hitl-soft .covered {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.78rem; margin-top: 0.2rem;
}
.hitl-clear {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  border-radius: 10px;
  padding: 0.85rem 1rem;
  color: var(--ok) !important; -webkit-text-fill-color: var(--ok) !important;
  font-weight: 600; font-size: 0.9rem;
}

.hitl-editor-block {
  margin: 0.75rem 0 0.35rem;
  padding-top: 0.55rem;
  border-top: 1px solid var(--line);
}
.hitl-editor-block:first-of-type { border-top: none; padding-top: 0.1rem; }
.hitl-editor-block .ttl {
  display: flex !important; align-items: center !important; flex-wrap: wrap !important;
  gap: 0.35rem !important;
  font-weight: 700; font-size: 0.95rem;
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
  margin-bottom: 0.15rem;
}
.hitl-editor-block .sub {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.8rem; margin-bottom: 0.45rem;
}
.hitl-actions {
  margin-top: 1.15rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--line);
  position: sticky;
  bottom: 0;
  z-index: 30;
  background: linear-gradient(180deg, rgba(241,244,249,0) 0%, var(--canvas) 22%, var(--canvas) 100%);
  padding-bottom: 0.25rem;
}
.hitl-actions-label {
  font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  margin-bottom: 0.45rem;
}

/* Data editor polish */
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
  background: var(--surface) !important;
  box-shadow: none !important;
  margin: 0.35rem 0 0.35rem !important;
}

@media (max-width: 900px) {
  .hitl-overview { grid-template-columns: 1fr; gap: 0.75rem; padding: 1rem; }
  .hitl-kv { grid-template-columns: 1fr; gap: 0.1rem; }
  .hitl-zone { margin: 1.15rem 0 0.4rem; }
  .hitl-section-title { margin: 1.15rem 0 0.2rem !important; }
  .hitl-actions { margin-top: 0.85rem; }
}

.doc-preview {
  white-space: pre-wrap;
  background: #0b1222;
  color: #e2e8f0 !important;
  -webkit-text-fill-color: #e2e8f0 !important;
  border-radius: 10px;
  padding: 0.95rem 1.1rem;
  max-height: 420px;
  overflow: auto;
  font-size: 0.85rem;
  line-height: 1.5;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

/* Buttons — equal-feel primary actions */
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 0.92rem !important;
  padding: 0.65rem 1.1rem !important;
  min-height: 2.75rem !important;
  border: 1px solid var(--line) !important;
  background: var(--surface) !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  box-shadow: var(--shadow) !important;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease !important;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: var(--shadow-hover) !important;
  border-color: #d1dbe8 !important;
}
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stButton"] > button[data-testid="baseButton-primary"],
div[data-testid="stDownloadButton"] > button[kind="primary"],
div[data-testid="stDownloadButton"] > button[data-testid="baseButton-primary"] {
  background: var(--teal) !important;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  border: 1px solid var(--teal) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover,
div[data-testid="stDownloadButton"] > button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] > button[data-testid="baseButton-primary"]:hover {
  background: var(--teal-deep) !important;
  border-color: var(--teal-deep) !important;
}

/* Main area search iframe — transparent blend */
[data-testid="stAppViewContainer"] .stCustomComponentV1 {
  margin: 0 0 0.15rem !important;
  padding: 0 !important;
  background: transparent !important;
}
[data-testid="stAppViewContainer"] .stCustomComponentV1 iframe {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  min-height: 44px !important;
  height: 44px !important;
  max-height: 44px !important;
}
[data-testid="stAppViewContainer"] div[data-testid="stElementContainer"]:has(iframe) {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  margin: 0 !important;
}

header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Document empty state */
.doc-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--muted);
  text-align: center;
}
.doc-empty-icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
  opacity: 0.5;
}
.doc-empty-text {
  font-size: 0.92rem;
  font-weight: 500;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}

@media (max-width: 1100px) {
  .status-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .summary-hero { padding: 1.5rem 1.35rem 1.25rem; }
  .top-navbar { flex-wrap: wrap; gap: 0.75rem; }
}
@media (max-width: 700px) {
  .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
  .status-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
  .status-cell { min-height: 4.5rem; padding: 0.85rem 0.9rem; }
  .page-title, .summary-hero-title { font-size: 1.45rem !important; }
  .pipe-sep { display: none; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.2rem !important;
  }
  .rules-hash, code.rules-hash { font-size: 0.72rem !important; }
  .top-navbar { padding: 0.55rem 0.85rem; }
  .nav-brand-title { font-size: 1.2rem; }
  .nav-search-kbd { display: none; }
}

"""

PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("monitor", "Monitor"),
    ("extract", "Extract"),
    ("normalize", "Normalize"),
    ("validate", "Validate"),
    ("index", "Index"),
    ("gate", "Gate"),
    ("summary_or_hitl", "Summary"),
)

PATIENT_NAMES: dict[str, str] = {
    "P1019": "Thomas Wright",
    "P1020": "Diego Morales",
    "P1021": "Rohan Gupta",
    "P1022": "Daan Bakker",
    "P1023": "Grace Bennett",
    "P1024": "Bram de Vries",
}


_NAV_LABELS: dict[str, str] = {
    "RAG Q&A": "RAG Assistant",
    "Upload new patients": "Upload New Patients",
}


def nav_label(page: str) -> str:
    """Text-only nav labels (no icons)."""
    return _NAV_LABELS.get(page, page)


def selected_patient_card_html(patient_id: str, patient_name: str = "") -> str:
    """Compact selected-patient card for the sidebar."""
    from html import escape

    pid = (patient_id or "").strip()
    if not pid:
        return (
            '<div class="patient-card patient-card-empty">'
            '<div class="patient-card-empty-msg">No patient selected</div>'
            "</div>"
        )
    name = (patient_name or "").strip()
    if not name:
        try:
            from dashboard.components.common import patient_display_name

            name = patient_display_name(pid)
        except Exception:
            name = PATIENT_NAMES.get(pid, "Patient")
    return (
        '<div class="patient-card">'
        f'<div class="patient-card-id">{escape(pid)}</div>'
        f'<div class="patient-card-name" title="{escape(name)}">{escape(name)}</div>'
        "</div>"
    )


def patient_card_html(patient_id: str, patient_name: str) -> str:
    return selected_patient_card_html(patient_id, patient_name)


def navbar_html(patient_id: str, patient_name: str = "") -> str:
    """Top navbar with branding, search placeholder, and patient avatar."""
    from html import escape

    pid = (patient_id or "").strip()
    name = (patient_name or "").strip()
    if not name and pid:
        try:
            from dashboard.components.common import patient_display_name
            name = patient_display_name(pid)
        except Exception:
            name = PATIENT_NAMES.get(pid, "Patient")

    # Build avatar initials
    initials = ""
    if name and name not in ("Patient", "—"):
        parts = name.split()
        initials = "".join(p[0].upper() for p in parts[:2] if p)
    elif pid:
        initials = pid[:2].upper()
    else:
        initials = "?"

    # Patient chip (only if patient is selected)
    if pid:
        patient_chip = (
            f'<div class="nav-patient-chip">'
            f'<span class="nav-avatar">{escape(initials)}</span>'
            f'<div class="nav-patient-info">'
            f'<span class="nav-patient-name">{escape(name)}</span>'
            f'<span class="nav-patient-id">{escape(pid)}</span>'
            f'</div>'
            f'<span class="nav-chevron">▾</span>'
            f'</div>'
        )
    else:
        patient_chip = (
            '<div class="nav-patient-chip">'
            '<span class="nav-avatar" style="background:#94a3b8">?</span>'
            '<div class="nav-patient-info">'
            '<span class="nav-patient-name" style="color:#94a3b8!important;-webkit-text-fill-color:#94a3b8!important">No patient</span>'
            '</div>'
            '</div>'
        )

    return (
        '<div class="top-navbar">'
        '<div class="nav-brand">'
        '<div class="nav-brand-title">Discharge AI</div>'
        '<div class="nav-brand-sub">AI-Assisted Discharge Review</div>'
        '</div>'
        '<div style="flex:1"></div>'
        '<div class="nav-patient-area">'
        f'{patient_chip}'
        '</div>'
        '</div>'
    )


_UNSET = object()


def pipeline_step_states(
    pipeline_result: dict | None,
    *,
    validation: object = _UNSET,
    summary: object = _UNSET,
) -> list[tuple[str, str, str, str]]:
    """Derive stepper UI state from pipeline outcomes (not just stages_run).

    Returns list of (key, label, state, mark) where state is one of:
    done | active | pending | blocked | skipped
    """
    result = pipeline_result or {}
    stages = list(result.get("stages_run") or [])
    if validation is _UNSET:
        validation_d: dict = result.get("validation") or {}
    else:
        validation_d = validation if isinstance(validation, dict) else {}
    if summary is _UNSET:
        summary_obj = result.get("summary")
    else:
        summary_obj = summary

    if validation_d:
        blocked = bool(validation_d.get("discharge_blocked"))
        needs_hitl = bool(validation_d.get("needs_hitl"))
        allow_summary = not (blocked or needs_hitl)
    else:
        gate = result.get("gate") or {}
        allow_summary = gate.get("allow_summary")
        blocked = bool(result.get("discharge_blocked"))
        needs_hitl = bool(result.get("needs_hitl"))
        if allow_summary is None:
            allow_summary = not (blocked or needs_hitl)

    gate_closed = (allow_summary is False) or blocked or (
        needs_hitl and summary_obj is None
    )
    gate_ran = "gate" in stages or "validate" in stages or bool(validation_d)

    out: list[tuple[str, str, str, str]] = []
    for key, label in PIPELINE_STEPS:
        ran = key in stages
        if key == "gate":
            if not gate_ran:
                state, mark = "pending", "○"
            elif gate_closed:
                state, mark = "blocked", "✕"
            else:
                state, mark = "done", "✓"
        elif key == "summary_or_hitl":
            if summary_obj is not None:
                state, mark = "done", "✓"
            elif gate_closed:
                state, mark = "skipped", "–"
            elif gate_ran or ran:
                state, mark = "active", "●"
            else:
                state, mark = "pending", "○"
        else:
            if ran:
                state, mark = "done", "✓"
            else:
                state, mark = "pending", "○"
        out.append((key, label, state, mark))
    return out


def inject_styles() -> None:
    import streamlit as st

    st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)
