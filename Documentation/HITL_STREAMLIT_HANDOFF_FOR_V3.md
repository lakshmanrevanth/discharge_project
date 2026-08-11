# HITL Streamlit Spec + Cursor Prompt (self-contained)

**Audience:** `cap_proj_v3` Cursor agent / engineer.  
**Do not copy files from another repo.** Rebuild the HITL Streamlit UI from this document alone.  
**Backend:** Keep V3 FA5 agents as-is. UI only calls them through a thin bridge.

---

## A. Problems to fix in V3

1. **URL** — must be clean: `http://127.0.0.1:8501` (headless Streamlit, no usage stats, fixed port/address).
2. **Patient already loaded** — **idle-first**: on open, only a patient *selector* is set. `case`, `validation`, `summary`, `pipeline_result` are `None`. Charts/findings/summary appear only after **Process patient**. Switching patient clears clinical state.
3. **No progress bar** — implement a **pipeline track** (not only `st.progress`):  
   `Monitor → Extract → Normalize → Validate → Index → Gate → Summary`  
   States: `pending` | `done` | `active` | `blocked` | `skipped`.

---

## B. Product requirements (FA5 HITL)

Five pages (Table 13), port **8501**:

1. Document Viewer  
2. Validation Report  
3. HITL Corrections  
4. RAG Q&A (nav label: **RAG Assistant**)  
5. Discharge Summary  

Rules live in agents. Streamlit never reimplements risk / allergy / bill logic.

---

## C. Layout (every page)

```text
SIDEBAR (dark, pinned)          MAIN
------------------------        --------------------------------
Brand lockup                    Status strip (6 cards)
Patient selectbox               Pipeline track (progress)
Nav radio (5 pages)             Page header card
                                Page body
```

Brand HTML:

```html
<div class="brand-lockup">
  <div class="brand-kicker">FA5 Capstone</div>
  <div class="brand-title">Discharge AI</div>
  <div class="brand-sub">AI-Assisted Discharge Review</div>
</div>
```

Status strip cells: Patient ID | Patient | Risk | Gate | Indexed | Documents  

Gate labels: `Idle` | `Clear` | `Needs HITL` | `Blocked`  

Patient select format: `P1019 — Thomas Wright` (name map or dynamic). No extra sidebar patient card.

Hide Streamlit menu, footer, and sidebar collapse chevron via CSS below.

---

## D. `.streamlit/config.toml` (create this)

```toml
[theme]
base = "light"
primaryColor = "#0f766e"
backgroundColor = "#eef2f6"
secondaryBackgroundColor = "#ffffff"
textColor = "#0f172a"
font = "sans serif"

[server]
headless = true
port = 8501
address = "127.0.0.1"

[browser]
gatherUsageStats = false
```

Launch:

```bash
python -m <hitl_package>
# or
streamlit run path/to/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

---

## E. Session state (idle-first)

```python
PAGES = (
    "Document Viewer",
    "Validation Report",
    "HITL Corrections",
    "RAG Q&A",
    "Discharge Summary",
)

def ensure_session_defaults() -> None:
    import streamlit as st
    defaults = {
        "patient_id": "P1019",
        "page": PAGES[0],
        "pipeline_result": None,
        "case": None,
        "validation": None,
        "summary": None,
        "trace_id": None,
        "rag_session_id": None,
        "rag_history": [],
        "last_error": None,
        "doc_count": None,
        "approval_note": "",
        "risk_override": "Keep model",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

On patient change: clear `pipeline_result`, `case`, `validation`, `summary`, `rag_history`, `doc_count` then `st.rerun()`.

---

## F. Design tokens

```text
Fonts: Plus Jakarta Sans (UI), Source Serif 4 (titles)
--ink #0f172a  --muted #64748b  --line #e8eef5  --surface #fff  --canvas #f7f9fc
--teal #0f766e  --teal-deep #115e59  --ok #15803d  --warn #b45309  --bad #b91c1c
Sidebar: #0b1220 / accent #14b8a6
```

Avoid purple themes, cream broadsheet, emoji nav, Material Symbols.

---

## G. Full CSS (`CUSTOM_CSS`)

Put this into `styles.py` and inject with `st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)`.

```css

@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

:root {
  --ink: #0f172a;
  --muted: #64748b;
  --line: #e8eef5;
  --surface: #ffffff;
  --canvas: #f7f9fc;
  --teal: #0f766e;
  --teal-deep: #115e59;
  --ok: #15803d;
  --warn: #b45309;
  --bad: #b91c1c;
  --info: #1d4ed8;
  --shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 16px rgba(15, 23, 42, 0.04);
  --shadow-hover: 0 4px 12px rgba(15, 23, 42, 0.08), 0 8px 24px rgba(15, 23, 42, 0.06);
  --radius: 12px;
  --sb-bg: #0b1220;
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
  padding-top: 1.5rem !important;
  padding-bottom: 2.5rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  max-width: 1260px !important;
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
  font-size: 1.75rem !important;
  font-weight: 700 !important;
  margin: 0 !important;
  letter-spacing: -0.02em;
  line-height: 1.2 !important;
}
.page-lede {
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  font-size: 0.95rem !important;
  margin: 0.4rem 0 0 !important;
  line-height: 1.5 !important;
}
.page-header {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
  box-shadow: var(--shadow);
  border-left: 3px solid var(--teal);
}

/* Sidebar — clinical console rail */
section[data-testid="stSidebar"] {
  background:
    linear-gradient(180deg, #0c1424 0%, #0b1220 48%, #09101c 100%) !important;
  border-right: 1px solid #243044;
  width: 288px !important;
  min-width: 288px !important;
  max-width: 288px !important;
  overflow-x: hidden !important;
}
section[data-testid="stSidebar"] > div {
  overflow-x: hidden !important;
  width: 100% !important;
  max-width: 288px !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding: 1.2rem 1.1rem 1.6rem !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
/* Keep nav pinned — hide Streamlit's collapse / expand chevron */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"],
button[kind="header"][data-testid="baseButton-header"],
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapsedControl"] {
  display: none !important;
  visibility: hidden !important;
  pointer-events: none !important;
  width: 0 !important;
  height: 0 !important;
}
section[data-testid="stSidebar"] .brand-kicker {
  font-size: 0.72rem; letter-spacing: 0.15em; text-transform: uppercase;
  font-weight: 700; color: var(--sb-accent) !important;
  -webkit-text-fill-color: var(--sb-accent) !important; margin-bottom: 0.55rem;
}
section[data-testid="stSidebar"] .brand-title {
  font-family: var(--display) !important; font-size: 1.95rem !important;
  font-weight: 700 !important; color: #fff !important;
  -webkit-text-fill-color: #fff !important; margin: 0 !important; line-height: 1.1;
  letter-spacing: -0.015em;
}
section[data-testid="stSidebar"] .brand-sub {
  color: var(--sb-muted) !important; -webkit-text-fill-color: var(--sb-muted) !important;
  font-size: 0.9rem !important; margin-top: 0.5rem; font-weight: 500;
  line-height: 1.4; max-width: 17rem;
}
.brand-lockup {
  padding-bottom: 1.2rem; margin-bottom: 1.15rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}
.nav-group-label {
  font-size: 0.7rem; letter-spacing: 0.11em; text-transform: uppercase;
  font-weight: 600; color: #7c8aa0 !important;
  -webkit-text-fill-color: #7c8aa0 !important;
  margin: 0.95rem 0 0.6rem;
}
.patient-card {
  background: var(--sb-card); border: 1px solid var(--sb-border);
  border-radius: 10px; padding: 0.75rem 0.85rem; margin-bottom: 0.65rem;
}
.patient-card-id {
  color: var(--sb-text) !important; -webkit-text-fill-color: var(--sb-text) !important;
  font-size: 1.05rem; font-weight: 700;
}
.patient-card-name {
  color: var(--sb-muted) !important; -webkit-text-fill-color: var(--sb-muted) !important;
  font-size: 0.85rem; margin-top: 0.15rem;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color: var(--sb-text) !important;
  -webkit-text-fill-color: var(--sb-text) !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: #121c2c !important;
  color: var(--sb-text) !important;
  -webkit-text-fill-color: var(--sb-text) !important;
  border: 1px solid #2a3a52 !important;
  border-radius: 9px !important;
  min-height: 2.75rem !important;
  max-width: 100% !important;
  overflow: hidden !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
  border-color: #3a516e !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span {
  color: var(--sb-text) !important;
  -webkit-text-fill-color: var(--sb-text) !important;
  font-weight: 600 !important;
  font-size: 0.95rem !important;
  opacity: 1 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  max-width: 230px !important;
  display: inline-block !important;
}
section[data-testid="stSidebar"] .stSelectbox,
section[data-testid="stSidebar"] .stRadio,
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  max-width: 100% !important;
  overflow-x: hidden !important;
}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
  gap: 0.38rem !important;
}
section[data-testid="stSidebar"] .stRadio label {
  padding: 0.78rem 0.85rem !important;
  border-radius: 9px !important;
  border: 1px solid transparent !important;
  border-left: 3px solid transparent !important;
  margin-bottom: 0 !important;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
  white-space: normal !important;
  word-break: break-word !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  font-size: 0.98rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.01em;
  line-height: 1.35 !important;
  color: #d6dee9 !important;
  -webkit-text-fill-color: #d6dee9 !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(20, 184, 166, 0.08) !important;
  border-color: rgba(42, 58, 82, 0.9) !important;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
  background: rgba(20, 184, 166, 0.14) !important;
  border-color: rgba(20, 184, 166, 0.28) !important;
  border-left-color: var(--sb-accent) !important;
  font-weight: 600 !important;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  box-shadow: inset 0 0 0 1px rgba(20, 184, 166, 0.08);
}
/* Quieter radio glyphs — keep Streamlit control, reduce visual noise */
section[data-testid="stSidebar"] .stRadio label > div:first-child {
  margin-right: 0.55rem !important;
}
section[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {
  display: none !important;
}

/* Status strip — premium metric cards */
.status-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
.status-cell {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem 1.05rem;
  min-height: 5.25rem;
  box-shadow: var(--shadow);
  transition: box-shadow 180ms ease, transform 180ms ease, border-color 180ms ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.45rem;
}
.status-cell:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-1px);
  border-color: #d7e2ee;
}
.status-label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
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
  width: 1.15rem;
  height: 1.15rem;
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
  font-size: 1.05rem; font-weight: 700; margin-top: 0;
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
  padding: 0.85rem 1rem;
  margin-bottom: 1.5rem;
  box-shadow: var(--shadow);
}
.pipe-sep {
  width: 12px; height: 1px;
  background: #dbe4ef;
  flex: 0 0 auto;
}
.pipe-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
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
  border-left: 3px solid var(--teal);
  background: #fcfdff;
  border-radius: 0 12px 12px 0;
  padding: 0.95rem 1.1rem;
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
  border-radius: 12px;
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
  border-radius: 12px !important;
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
  border-radius: 14px;
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
  border-radius: 12px;
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
  border-radius: 12px;
  padding: 1.1rem 1.25rem;
  margin: 0 0 1.25rem;
  box-shadow: var(--shadow);
  border-left: 3px solid var(--teal);
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
  border-left: 3px solid var(--line);
  border-radius: 0 12px 12px 0;
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
  border-radius: 12px !important;
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
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px;
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
[data-testid="stAppViewContainer"] .stCaption,
[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] {
  margin-top: 0.15rem !important;
  margin-bottom: 0.35rem !important;
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
  background: linear-gradient(180deg, rgba(247,249,252,0) 0%, var(--canvas) 22%, var(--canvas) 100%);
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
  background: #0b1220;
  color: #e2e8f0 !important;
  -webkit-text-fill-color: #e2e8f0 !important;
  border-radius: 8px;
  padding: 0.85rem 1rem;
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
  transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease, border-color 160ms ease !important;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: var(--shadow-hover) !important;
  border-color: #d7e2ee !important;
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

header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

@media (max-width: 1100px) {
  .status-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .summary-hero { padding: 1.5rem 1.35rem 1.25rem; }
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
}
```

---

## H. Pipeline stepper logic (must match)

```python
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


def page_header_html(title: str, lede: str) -> str:
    from services.hitl_dashboard.ui_chrome import page_header_html as _hdr

    return _hdr(title, lede)


def nav_label(page: str) -> str:
    if page == "RAG Q&A":
        return "RAG Assistant"
    return page


def patient_card_html(patient_id: str, patient_name: str) -> str:
    name = patient_name or PATIENT_NAMES.get(patient_id, "—")
    return (
        f'<div class="patient-card">'
        f'<div class="patient-card-id">{patient_id}</div>'
        f'<div class="patient-card-name">{name}</div></div>'
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

    Live ``validation`` / ``summary`` from the HITL session win over a stale
    Host ``pipeline_result`` from the first blocked pass. Pass explicit ``None``
    for summary after re-validate (cleared) — do not fall back to the snapshot.
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

    # Prefer live validation for block flags (do not OR with stale Host snapshot)
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
```

Render:

```python
steps = pipeline_step_states(
    st.session_state.pipeline_result,
    validation=st.session_state.validation,
    summary=st.session_state.summary,
)
st.markdown(pipeline_track_html(steps), unsafe_allow_html=True)
```

Semantics:
- Host may include `summary_or_hitl` in `stages_run` even when summary withheld → Summary must be **skipped**, not done.
- After HITL re-validate, live session `validation`/`summary` override stale Host snapshot.
- Before Process: all **pending**.

Optional: during spinner, also show `st.progress` or indeterminate bar — pipeline track remains permanent chrome.

---

## I. HTML chrome helpers (`ui_chrome.py`)

Implement exactly (or equivalent):

```python
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
        f'<div class="page-title">{esc(title)}</div>'
        f'<p class="page-lede">{esc(lede)}</p></div>'
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
        if action != "block" and severity != "critical":
            continue
        field = str(finding.get("field") or "").strip()
        rule = str(finding.get("rule_id") or "").strip()
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
        f'{"Needs HITL" if needs_hitl else "Auto path"}</span>'
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
```

---

## J. Bridge contract (adapt to V3 imports)

UI must call thin functions with these shapes (wire to V3 Host/Monitor/Validator/RAG/Summary):

```python
list_patient_documents(patient_id) -> dict  # {files: [...], error?}
read_doc_preview(path, limit=6000) -> str   # roots-safe
run_host_pipeline(patient_id, *, use_fixture=True) -> dict
# returns: trace_id, patient_id, case, validation, summary, stages_run,
#          indexed, needs_hitl, discharge_blocked, gate{allow_summary,reason}, error?
load_working_case(patient_id) -> dict
revalidate_case(case, *, elicit_answers=None) -> dict  # {case, result, error?}
ensure_indexed(case, validation) -> dict  # {indexed_chunks}
ask_rag(patient_id, question, *, session_id=None) -> dict
maybe_summarize(case, validation) -> dict  # {summary} or {error: {code: SUMMARY_REFUSED_BLOCKED}}
```

Reference shape of a working bridge (adjust imports to V3):

```python
"""Bridge HITL UI → Host / Validator / RAG / Summary (no duplicated business rules)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from discharge_ai.infra.config import get_settings
from discharge_ai.infra.faiss_store import FaissStore
from services.agent_monitor.service import discover_documents
from services.agent_rag.service import index_case, run_ask
from services.agent_summary.service import gate_allows_summary, run_summary
from services.agent_validator.graph import run_validator
from services.orchestrator.pipeline import PipelineDeps, load_fixture_case, process_patient


def _vector_store() -> FaissStore:
    settings = get_settings()
    return FaissStore(root=settings.abs_path(settings.paths.data_vector_db))


def list_patient_documents(patient_id: str) -> dict[str, Any]:
    return discover_documents(patient_id=patient_id)


def read_doc_preview(rel_or_abs: str, limit: int = 6000) -> str:
    settings = get_settings()
    root = settings.abs_path(settings.paths.data_input)
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = root / rel_or_abs
    try:
        path.relative_to(root)
    except ValueError:
        return "[path outside roots — blocked]"
    if not path.exists():
        return "[file missing]"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf"}:
        sidecar = Path(str(path) + ".ocr.txt")
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8", errors="replace")[:limit]
        return f"[{path.suffix} binary — open OCR sidecar if available]"
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def run_host_pipeline(patient_id: str, *, use_fixture: bool = True) -> dict[str, Any]:
    deps = PipelineDeps(faiss_store=_vector_store())
    return process_patient(
        patient_id,
        trace_id=str(uuid4()),
        deps=deps,
        use_fixture_case=use_fixture,
        allow_elicit=False,
    )


def load_working_case(patient_id: str) -> dict[str, Any]:
    try:
        return load_fixture_case(patient_id)
    except FileNotFoundError:
        return {"patient_id": patient_id, "medications": [], "allergies": []}


def revalidate_case(
    case: dict[str, Any],
    *,
    elicit_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handler = None
    if elicit_answers is not None:

        async def _accept(message, response_type, params, context):  # noqa: ANN001
            return elicit_answers

        handler = _accept

    return run_validator(
        case=case,
        trace_id=str(uuid4()),
        allow_elicit=bool(handler),
        elicitation_handler=handler,
        skip_push=True,
    )


def ensure_indexed(case: dict[str, Any], validation: dict[str, Any] | None) -> dict[str, Any]:
    return index_case(case=case, validation=validation, store=_vector_store())


def ask_rag(
    patient_id: str,
    question: str,
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    return run_ask(
        patient_id=patient_id,
        question=question,
        session_id=session_id or str(uuid4()),
        store=_vector_store(),
    )


def maybe_summarize(case: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    allowed, reason = gate_allows_summary(validation)
    if not allowed:
        return {
            "error": {
                "code": "SUMMARY_REFUSED_BLOCKED",
                "message": reason,
            }
        }
    return run_summary(
        case=case,
        validation=validation,
        trace_id=str(uuid4()),
        skip_push=True,
    )
```

---

## K. Main app structure

`main()` order: `set_page_config` → `inject_styles` → `ensure_session_defaults` → sidebar → status strip → pipeline track → page body.

Reference implementation (replace `services.hitl_dashboard.*` imports with your V3 package paths; keep behavior):

```python
"""Discharge AI — HITL Streamlit Dashboard (:8501).

Five FA5 Table 13 pages. Agents own business rules; this UI only calls them.
Simple, professional layout — Streamlit-native where possible.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from services.hitl_dashboard import bridge
from services.hitl_dashboard.corrections import (
    critical_fix_hints as _critical_fix_hints,
    critical_issues as _critical_issues,
    page_corrections as _page_corrections_impl,
)
from services.hitl_dashboard.state import (
    PAGES,
    PATIENTS,
    append_feedback,
    ensure_session_defaults,
    risk_badge_class,
)
from services.hitl_dashboard.styles import (
    PATIENT_NAMES,
    inject_styles,
    nav_label,
    pipeline_step_states,
)
from services.hitl_dashboard.ui_chrome import (
    esc as _esc,
    blocking_gaps_for_display,
    finding_card_html,
    gaps_panel_html,
    page_header_html,
    pipeline_track_html,
    status_strip_html,
    summary_document_html,
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


def _sidebar() -> str:
    """Patient selectbox (name only here) + page navigation. Sidebar stays pinned."""
    with st.sidebar:
        st.markdown(
            """
            <div class="brand-lockup">
              <div class="brand-kicker">FA5 Capstone</div>
              <div class="brand-title">Discharge AI</div>
              <div class="brand-sub">AI-Assisted Discharge Review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="nav-group-label">Current Patient</div>', unsafe_allow_html=True)

        def _opt(pid: str) -> str:
            return f"{pid} — {PATIENT_NAMES.get(pid, pid)}"

        prev = st.session_state.patient_id
        patient = st.selectbox(
            "Patient",
            PATIENTS,
            index=PATIENTS.index(prev) if prev in PATIENTS else 0,
            format_func=_opt,
            label_visibility="collapsed",
            key="patient_select",
        )
        if patient != prev:
            st.session_state.patient_id = patient
            st.session_state.pipeline_result = None
            st.session_state.case = None
            st.session_state.validation = None
            st.session_state.summary = None
            st.session_state.rag_history = []
            st.session_state.doc_count = None
            st.rerun()

        st.markdown('<div class="nav-group-label">Navigation</div>', unsafe_allow_html=True)
        page = st.radio(
            "Navigation",
            list(PAGES),
            index=list(PAGES).index(st.session_state.page)
            if st.session_state.page in PAGES
            else 0,
            format_func=nav_label,
            label_visibility="collapsed",
            key="nav_radio",
        )
        st.session_state.page = page
    return page


def _gate_status(val: dict[str, Any] | None) -> tuple[str, str]:
    if not val:
        return "Idle", "teal"
    if val.get("discharge_blocked"):
        return "Blocked", "bad"
    if val.get("needs_hitl"):
        return "Needs HITL", "warn"
    return "Clear", "ok"


def _status_strip() -> None:
    pid = st.session_state.patient_id
    case = st.session_state.case or {}
    name = str(case.get("patient_name") or "").strip() or PATIENT_NAMES.get(pid, "—")
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
        # Cleared gate but summary not generated yet — drop withheld None from first pass
        pr["summary"] = None
    if case is not None:
        pr["case"] = case
    if indexed is not None:
        pr["indexed"] = indexed
    # Ensure stepper sees gate/summary stages after HITL
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


def page_documents() -> None:
    _page_header(
        "Document Viewer",
        "Review packets under MCP Roots, then run the Host pipeline.",
    )
    files = _list_files()

    use_fixture = st.toggle("Lab mode · fixture case after Monitor", value=True)
    if st.button("Process patient", type="primary"):
        with st.spinner("Running Host pipeline…"):
            try:
                out = bridge.run_host_pipeline(
                    st.session_state.patient_id, use_fixture=use_fixture
                )
                _sync_from_pipeline(out)
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
        st.info("No files found. Run seed_input if needed.")
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
    if uris:
        with st.expander("Audit artifacts", expanded=False):
            for kind, uri in uris.items():
                st.markdown(
                    f'<div class="artifact-row">'
                    f'<span class="artifact-kind">{_esc(kind)}</span>'
                    f'<code class="artifact-uri">{_esc(uri)}</code></div>',
                    unsafe_allow_html=True,
                )

    st.markdown('<div class="section-label">Findings</div>', unsafe_allow_html=True)
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
        "Grounded answers after indexing (works during HITL-2 review).",
    )
    case = st.session_state.case
    if st.button("Ensure FAISS index"):
        if not case:
            case = bridge.load_working_case(st.session_state.patient_id)
            st.session_state.case = case
        out = bridge.ensure_indexed(case, st.session_state.validation)
        st.success(f"Indexed {out.get('indexed_chunks')} chunks")

    for turn in st.session_state.rag_history:
        with st.chat_message("user"):
            st.write(turn["q"])
        with st.chat_message("assistant"):
            st.write(turn.get("a") or "—")
            raw = turn.get("raw") or {}
            if isinstance(raw.get("answer"), dict) and raw["answer"].get("triad"):
                st.caption(f"Triad · {raw['answer']['triad']}")

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
                answer = f"[{out['error'].get('code')}] {out['error'].get('message')}"
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
        st.warning("HITL-2 gate closed — clear the case in Corrections first.")
        return
    if not summary:
        st.info("No summary yet. Process a Low-risk patient (e.g. P1019).")
        return

    from services.agent_summary.service import SECTION_TITLES

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
        "⬇ Export JSON",
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
        "⬇ Export Markdown",
        data=md,
        file_name=f"{summary.get('patient_id')}_summary.md",
        mime="text/markdown",
        use_container_width=True,
        type="primary",
    )


def main() -> None:
    _cfg()
    inject_styles()
    ensure_session_defaults()
    if "doc_count" not in st.session_state:
        st.session_state.doc_count = None

    page = _sidebar()
    _status_strip()
    _pipeline_line()

    if page == "Document Viewer":
        page_documents()
    elif page == "Validation Report":
        page_validation()
    elif page == "HITL Corrections":
        page_corrections()
    elif page == "RAG Q&A":
        page_rag()
    else:
        page_summary()


if __name__ == "__main__":
    main()
```

Entrypoint pattern:

```python
"""CLI: python -m services.hitl_dashboard  → streamlit on :8501"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from discharge_ai.infra.config import get_settings


def main() -> None:
    settings = get_settings()
    app = Path(__file__).resolve().parent / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.address",
        settings.bind_host,
        "--server.port",
        str(settings.ports.hitl_dashboard),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
```

---

## L. Page behavior summary

### Document Viewer
- Toggle lab/fixture mode; primary **Process patient** with spinner.
- List Roots files; tabs Discharge/Lab/Bill; dark `.doc-preview`.
- Do not auto-process on load.

### Validation Report
- If no validation → warn to Process first.
- Metrics + status card + finding cards + soft/blocking gaps + audit URIs expander.

### HITL Corrections
- Overview metrics (critical/soft/shared/status).
- HITL-2 Critical panels: allergy, bill, followup, approval (+ other).
- HITL-1 soft elicitation fields (skip if covered by Critical panel).
- One-click allergy remove & re-run when flagged meds known.
- Sticky actions: **Re-run validation**, **Generate summary**.
- Append feedback.jsonl rows.
- After re-validate: sync pipeline snapshot so Gate/Summary stepper updates.

Critical map:

```python
CRITICAL_FIX = {
    "allergy_contradiction_check": {"title": "Allergy contradiction", "panel": "allergy",
        "fix": "Delete conflicting drug(s) from Medications; keep allergy; re-run."},
    "bill_settlement_check": {"title": "Bill settlement", "panel": "bill",
        "fix": "Set payment status to PAID."},
    "follow_up_missing_check": {"title": "Follow-up missing", "panel": "followup",
        "fix": "Enter follow-up appointment."},
    "discharge_approval_check": {"title": "Discharge approval", "panel": "approval",
        "fix": "Confirm discharge_ok."},
}
SOFT_COVERED_BY_PANEL = {
    "follow_up_appointment": "followup",
    "allergies": "allergy",
}
```

Full corrections reference (adapt imports; keep UX):

```python
"""HITL Corrections page — HITL-1 elicitation vs HITL-2 Critical/Block (shared case state).

Presentation-only layout. Backend / validation / bridge calls are unchanged.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from discharge_ai.domain.drug_normalize import drug_names_match
from services.hitl_dashboard import bridge
from services.hitl_dashboard.state import append_feedback

# Extracts the flagged drug name from validator messages like:
#   "...but discharge includes 'Amoxicilline' (normalized=amoxicillin)"
# Used only as fallback when ``flagged_medications`` is absent (older audits).
_ALLERGY_MED_RE = re.compile(r"includes '([^']+)'")


def _flagged_allergy_meds(issues: list[dict[str, str]]) -> list[str]:
    """Drug name(s) the validator flagged as contradicting an allergy.

    Prefers structured ``flagged_medications`` on the finding; falls back to
    parsing the Critical message so older audits still drive the Remove button.
    """
    names: list[str] = []
    for i in issues:
        if i.get("rule_id") != "allergy_contradiction_check":
            continue
        structured = i.get("flagged_medications") or []
        if isinstance(structured, list) and structured:
            for med in structured:
                text = str(med).strip()
                if text and text not in names:
                    names.append(text)
            continue
        m = _ALLERGY_MED_RE.search(i.get("message") or "")
        if m and m.group(1) not in names:
            names.append(m.group(1))
    return names


def _allergy_fix_text(flagged: list[str]) -> str:
    if not flagged:
        return (
            "Delete the conflicting drug(s) from Medications (keep the allergy on file). "
            "Then Re-run validation."
        )
    joined = ", ".join(flagged)
    return (
        f"Delete {joined} from Medications (keep the allergy on file). "
        "Then Re-run validation."
    )

def _remove_meds_by_name(case: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """Return case with any medication matching one of `names` removed."""
    meds = case.get("medications") or []
    kept = [
        m
        for m in meds
        if not any(
            drug_names_match(str(m.get("medicine_name") or m.get("name") or ""), n)
            for n in names
        )
    ]
    return {**case, "medications": kept}


def _run_revalidate(
    case: dict[str, Any],
    *,
    pid: str,
    elicit_answers: dict[str, Any] | None,
    sync_pipeline_after_hitl,
) -> None:
    """Shared revalidate → sync-state → feedback-log path used by every fix action."""
    out = bridge.revalidate_case(case, elicit_answers=elicit_answers)
    if out.get("error"):
        st.error(out["error"])
        return
    updated_case = out.get("case") or case
    validation = out.get("result")
    bridge.ensure_indexed(updated_case, validation)
    if validation and not (validation.get("discharge_blocked") or validation.get("needs_hitl")):
        st.session_state.summary = None
    sync_pipeline_after_hitl(case=updated_case, validation=validation, indexed=True)
    append_feedback(
        {
            "patient_id": pid,
            "action": "rerun_validation",
            "validation": st.session_state.validation,
        }
    )
    st.success("Validation updated")
    st.rerun()


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# Extensible Critical → editor map. Unknown rules → panel "other" (no crash).
CRITICAL_FIX: dict[str, dict[str, str]] = {
    "allergy_contradiction_check": {
        "title": "Allergy contradiction",
        "fix": "Delete the conflicting drug(s) from Medications (keep the allergy on file). Then Re-run validation.",
        "panel": "allergy",
    },
    "bill_settlement_check": {
        "title": "Bill settlement",
        "fix": "Set payment status to PAID after settlement.",
        "panel": "bill",
    },
    "follow_up_missing_check": {
        "title": "Follow-up missing",
        "fix": "Enter a follow-up appointment.",
        "panel": "followup",
    },
    "discharge_approval_check": {
        "title": "Discharge approval",
        "fix": "Confirm discharge approved (discharge_ok).",
        "panel": "approval",
    },
}

# Soft elicit fields covered by a Critical panel — one widget serves HITL-1 + HITL-2
SOFT_COVERED_BY_PANEL: dict[str, str] = {
    "follow_up_appointment": "followup",
    "allergies": "allergy",
}


def critical_issues(findings: list[Any]) -> list[dict[str, str]]:
    """Build Critical checklist from live findings (safe for unknown rule_ids)."""
    issues: list[dict[str, str]] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        if str(f.get("severity") or "") != "Critical":
            continue
        rule = str(f.get("rule_id") or "unknown")
        meta = CRITICAL_FIX.get(rule) or {
            "title": rule.replace("_", " ").title(),
            "fix": "Edit the related case fields below, then re-run validation.",
            "panel": "other",
        }
        flagged = []
        raw_flagged = f.get("flagged_medications") or []
        if isinstance(raw_flagged, list):
            flagged = [str(x).strip() for x in raw_flagged if str(x).strip()]
        if not flagged and rule == "allergy_contradiction_check":
            m = _ALLERGY_MED_RE.search(str(f.get("message") or ""))
            if m:
                flagged = [m.group(1)]
        fix = meta["fix"]
        if rule == "allergy_contradiction_check":
            fix = _allergy_fix_text(flagged)
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


def critical_fix_hints(findings: list[Any]) -> list[str]:
    return [f"{i['title']} — {i['fix']}" for i in critical_issues(findings)]


# Back-compat aliases for tests importing from app
_CRITICAL_FIX = CRITICAL_FIX
_critical_issues = critical_issues
_critical_fix_hints = critical_fix_hints


def _empty_ok(message: str) -> None:
    st.markdown(
        f'<div class="empty-state empty-ok">'
        f'<span class="empty-icon" aria-hidden="true">✓</span>'
        f'<span class="empty-text">{_esc(message)}</span></div>',
        unsafe_allow_html=True,
    )


def _section_head(title: str, tag: str, tag_cls: str, lede: str, zone_cls: str) -> None:
    """Section header — title and badge separated so Streamlit HTML cannot glue them."""
    st.markdown(
        f'<div class="hitl-zone {zone_cls}">'
        f'<div class="hitl-zone-head">'
        f'<span class="label">{_esc(title)}</span>'
        f'<span class="sep">·</span>'
        f'<span class="tag {tag_cls}">{_esc(tag)}</span>'
        f"</div>"
        f'<div class="hitl-zone-lede">{_esc(lede)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _overview_html(
    *,
    critical_n: int,
    soft_n: int,
    shared_n: int,
    status: str,
    status_tone: str,
) -> str:
    return (
        f'<div class="hitl-overview">'
        f'<div class="hitl-overview-copy">'
        f'<div class="hitl-overview-kicker">HITL workflow</div>'
        f'<div class="hitl-overview-title">HITL Corrections</div>'
        f'<p class="hitl-overview-lede">Resolve all blocking issues before a discharge '
        f"summary can be generated.</p></div>"
        f'<div class="hitl-overview-metrics">'
        f'<div class="hitl-ov-metric"><div class="k">Critical Issues</div>'
        f'<div class="v tone-bad">{critical_n}</div></div>'
        f'<div class="hitl-ov-metric"><div class="k">Soft Issues</div>'
        f'<div class="v tone-warn">{soft_n}</div></div>'
        f'<div class="hitl-ov-metric"><div class="k">Shared Fields</div>'
        f'<div class="v">{shared_n}</div></div>'
        f'<div class="hitl-ov-metric"><div class="k">Overall Status</div>'
        f'<div class="v"><span class="chip {status_tone}">{_esc(status)}</span></div></div>'
        f"</div></div>"
    )


def _issue_card_html(
    *,
    title: str,
    severity: str,
    severity_cls: str,
    reason: str,
    action: str,
    field: str = "",
    shared: bool = False,
    covered: bool = False,
) -> str:
    shared_badge = (
        '<span class="tag tag-shared">Shared (HITL-1 + HITL-2)</span>' if shared else ""
    )
    covered_note = (
        '<div class="hitl-kv"><span class="k">Status</span>'
        '<span class="v muted">Covered in Corrections below — edited once.</span></div>'
        if covered
        else ""
    )
    field_row = (
        f'<div class="hitl-kv"><span class="k">Affected field</span>'
        f'<span class="v mono">{_esc(field)}</span></div>'
        if field
        else ""
    )
    reason_row = (
        f'<div class="hitl-kv"><span class="k">Reason</span>'
        f'<span class="v">{_esc(reason)}</span></div>'
        if reason
        else ""
    )
    action_row = (
        f'<div class="hitl-kv"><span class="k">Required action</span>'
        f'<span class="v">{_esc(action)}</span></div>'
        if action
        else ""
    )
    return (
        f'<div class="hitl-issue-card {severity_cls}">'
        f'<div class="hitl-issue-top">'
        f'<div class="hitl-issue-title">{_esc(title)}</div>'
        f"{shared_badge}</div>"
        f'<div class="hitl-kv"><span class="k">Severity</span>'
        f'<span class="v sev-{severity_cls}">{_esc(severity)}</span></div>'
        f"{reason_row}{action_row}{field_row}{covered_note}</div>"
    )


def _corr_group_open(title: str, *, shared: bool = False, hint: str = "") -> None:
    shared_bit = (
        '<span class="tag tag-shared">Shared (HITL-1 + HITL-2)</span>' if shared else ""
    )
    hint_html = f'<div class="corr-group-hint">{_esc(hint)}</div>' if hint else ""
    st.markdown(
        f'<div class="corr-group-banner">'
        f'<div class="corr-group-head"><span class="corr-group-title">{_esc(title)}</span>'
        f"{shared_bit}</div>{hint_html}</div>",
        unsafe_allow_html=True,
    )


class _CorrPanel:
    """Group banner + widgets in one bordered Streamlit container."""

    def __init__(self, title: str, *, shared: bool = False, hint: str = "") -> None:
        self.title = title
        self.shared = shared
        self.hint = hint
        try:
            self._cm = st.container(border=True)
        except TypeError:
            self._cm = st.container()

    def __enter__(self):
        self._cm.__enter__()
        st.markdown('<div class="corr-panel-mark"></div>', unsafe_allow_html=True)
        _corr_group_open(self.title, shared=self.shared, hint=self.hint)
        return self

    def __exit__(self, *args):
        return self._cm.__exit__(*args)


def _edit_allergy_meds(case: dict[str, Any], *, pid: str) -> None:
    allergies = case.get("allergies") or []
    allergy_text = (
        ", ".join(str(a) for a in allergies) if isinstance(allergies, list) else str(allergies)
    )
    allergy_text = st.text_input(
        "Allergies (comma-separated)",
        value=allergy_text,
        key=f"allergies_{pid}",
    )
    case["allergies"] = [a.strip() for a in allergy_text.split(",") if a.strip()]
    rows = []
    for m in case.get("medications") or []:
        if isinstance(m, dict):
            rows.append(
                {
                    "medicine_name": m.get("medicine_name") or m.get("name") or "",
                    "strength": m.get("strength") or "",
                    "frequency": m.get("frequency") or "",
                    "route": m.get("route") or "",
                }
            )
    if not rows:
        st.caption("No medications on file — add rows in the table below.")
    edited = st.data_editor(
        pd.DataFrame(
            rows or [{"medicine_name": "", "strength": "", "frequency": "", "route": ""}]
        ),
        num_rows="dynamic",
        use_container_width=True,
        key=f"meds_editor_{pid}",
    )
    meds_out: list[dict[str, Any]] = []
    for row in edited.to_dict(orient="records"):
        name = str(row.get("medicine_name") or "").strip()
        if not name:
            continue
        meds_out.append(
            {
                "medicine_name": name,
                "name": name,
                "strength": row.get("strength") or "",
                "frequency": row.get("frequency") or "",
                "route": row.get("route") or "",
            }
        )
    case["medications"] = meds_out


def _edit_bill(case: dict[str, Any], *, pid: str) -> None:
    bill = case.get("bill") if isinstance(case.get("bill"), dict) else {}
    if not isinstance(bill, dict):
        bill = {}
    b1, b2 = st.columns(2)
    bill_id = b1.text_input(
        "Bill ID", value=str(bill.get("bill_id") or ""), key=f"bill_id_{pid}"
    )
    current = str(bill.get("payment_status") or "UNKNOWN").strip().upper() or "UNKNOWN"
    choices = ["PAID", "UNPAID", "PENDING", "PARTIAL", "UNKNOWN"]
    if current not in choices:
        choices = [current, *choices]
    payment_status = b2.selectbox(
        "Payment status",
        choices,
        index=choices.index(current),
        key=f"bill_payment_{pid}",
    )
    amount = bill.get("total_amount")
    currency = str(bill.get("currency") or "")
    if amount is not None:
        st.caption(f"Amount on file: {amount} {currency}".strip())
    case["bill"] = {**bill, "bill_id": bill_id, "payment_status": payment_status}


def _edit_followup(case: dict[str, Any], *, pid: str) -> None:
    case["follow_up_appointment"] = st.text_input(
        "Follow-up appointment",
        value=str(case.get("follow_up_appointment") or ""),
        key=f"followup_{pid}",
    )


def _edit_approval(case: dict[str, Any], *, pid: str) -> None:
    case["discharge_ok"] = st.checkbox(
        "Discharge approved (discharge_ok)",
        value=bool(case.get("discharge_ok")),
        key=f"discharge_ok_{pid}",
    )


def _edit_soft_field(
    case: dict[str, Any],
    field: str,
    *,
    pid: str,
    elicit_answers: dict[str, Any],
) -> None:
    label = field.replace("_", " ").title()
    if field == "discharge_diagnosis":
        dx = case.get("discharge_diagnosis")
        dx_text = "; ".join(str(x) for x in dx) if isinstance(dx, list) else str(dx or "")
        dx_text = st.text_input(
            "Discharge diagnosis (semicolon-separated)",
            value=dx_text,
            key=f"soft_{pid}_{field}",
        )
        case["discharge_diagnosis"] = [p.strip() for p in dx_text.split(";") if p.strip()]
        elicit_answers[field] = case["discharge_diagnosis"]
        return
    if field == "consulting_doctors":
        raw = case.get("consulting_doctors")
        text = ", ".join(str(x) for x in raw) if isinstance(raw, list) else str(raw or "")
        text = st.text_input(label, value=text, key=f"soft_{pid}_{field}")
        case[field] = [p.strip() for p in text.split(",") if p.strip()]
        elicit_answers[field] = case[field]
        return
    if field == "allergies":
        raw = case.get("allergies") or []
        text = ", ".join(str(a) for a in raw) if isinstance(raw, list) else str(raw)
        text = st.text_input(label, value=text, key=f"soft_{pid}_{field}")
        case[field] = [a.strip() for a in text.split(",") if a.strip()]
        elicit_answers[field] = case[field]
        return
    val = st.text_input(
        label,
        value=str(case.get(field) or ""),
        key=f"soft_{pid}_{field}",
    )
    case[field] = val
    elicit_answers[field] = val


def page_corrections(
    *,
    page_header,
    sync_pipeline_after_hitl,
) -> None:
    """HITL Corrections UI. Injected helpers avoid circular imports with app.py."""
    page_header(
        "HITL Corrections",
        "Fix Critical blocks (HITL-2) and soft gaps (HITL-1). Shared fields are edited once.",
    )
    pid = str(st.session_state.patient_id)
    case = st.session_state.case or bridge.load_working_case(pid)
    st.session_state.case = case
    val = st.session_state.validation or {}
    issues = critical_issues(list(val.get("findings") or []))
    open_panels = {i["panel"] for i in issues}
    soft = [str(s) for s in (val.get("missing_soft") or [])]
    gate_busy = bool(val.get("discharge_blocked") or val.get("needs_hitl") or issues)
    elicit_answers: dict[str, Any] = {}
    rendered: set[str] = set()

    if not val:
        st.info("Process the patient on Document Viewer first.")
        return

    shared_n = sum(
        1
        for field in soft
        if SOFT_COVERED_BY_PANEL.get(field) is not None
        and SOFT_COVERED_BY_PANEL.get(field) in open_panels
    )
    if issues:
        status, status_tone = "Needs Review", "badge-bad"
    elif soft or gate_busy:
        status, status_tone = "Needs Review", "badge-warn"
    else:
        status, status_tone = "Clear", "badge-ok"

    st.markdown(
        _overview_html(
            critical_n=len(issues),
            soft_n=len(soft),
            shared_n=shared_n,
            status=status,
            status_tone=status_tone,
        ),
        unsafe_allow_html=True,
    )

    # ── Critical Issues (HITL-2) ───────────────────────────────────────
    _section_head(
        "Critical Issues",
        "HITL-2",
        "tag-hitl2",
        "Hard gate. Summary stays closed until these are cleared.",
        "hitl2",
    )
    if issues:
        for i in issues:
            shared = any(
                soft_f
                for soft_f, panel in SOFT_COVERED_BY_PANEL.items()
                if panel == i["panel"] and soft_f in soft
            )
            st.markdown(
                _issue_card_html(
                    title=i["title"],
                    severity="Critical",
                    severity_cls="critical",
                    reason=i.get("message") or "",
                    action=i["fix"],
                    field=i.get("field") or "",
                    shared=shared,
                ),
                unsafe_allow_html=True,
            )
    elif gate_busy:
        st.markdown(
            '<div class="hitl-alert warn">'
            '<span class="hitl-alert-icon">!</span>'
            '<div><div class="hitl-alert-title">No Critical findings</div>'
            '<div class="hitl-alert-body">Gate may still be closed for Medium/High risk. '
            "Review soft gaps and re-run validation.</div></div></div>",
            unsafe_allow_html=True,
        )
    else:
        _empty_ok("No critical issues detected")

    # ── Soft Issues (HITL-1) ──────────────────────────────────────────
    _section_head(
        "Soft Issues",
        "HITL-1",
        "tag-hitl1",
        "Fill missing soft fields. Overlap with HITL-2 is edited once in Corrections.",
        "hitl1",
    )
    if soft:
        for field in soft:
            cover_panel = SOFT_COVERED_BY_PANEL.get(field)
            already = field in rendered or (
                cover_panel is not None and cover_panel in open_panels
            )
            label = field.replace("_", " ").title()
            st.markdown(
                _issue_card_html(
                    title=label,
                    severity="Warning",
                    severity_cls="warning",
                    reason=f"Soft completeness gap: {field}",
                    action=(
                        "Covered by Critical editor below — one edit clears both."
                        if already
                        else "Enter the missing value in Corrections."
                    ),
                    field=field,
                    shared=already,
                    covered=already,
                ),
                unsafe_allow_html=True,
            )
            if already and field in case and case.get(field) not in (None, "", []):
                elicit_answers[field] = case.get(field)
    else:
        _empty_ok("No soft gaps detected")

    # ── Corrections (single grouped form) ─────────────────────────────
    soft_to_edit = [
        f
        for f in soft
        if f not in rendered
        and not (
            SOFT_COVERED_BY_PANEL.get(f) is not None
            and SOFT_COVERED_BY_PANEL.get(f) in open_panels
        )
    ]
    need_corrections = bool(open_panels) or bool(soft_to_edit)

    if need_corrections:
        st.markdown(
            '<div class="hitl-section-title">Corrections</div>'
            '<p class="hitl-section-lede">Edit each required field once. Shared HITL-1 + HITL-2 '
            "fields are not duplicated.</p>",
            unsafe_allow_html=True,
        )

        if "allergy" in open_panels:
            flagged = _flagged_allergy_meds(issues)
            with _CorrPanel(
                "Medication & allergies",
                shared="allergies" in soft,
                hint=(
                    "Delete the flagged drug from the medications table, then Re-run validation. "
                    "Keep the allergy on file."
                ),
            ):
                if flagged:
                    st.markdown(
                        f'<div class="hitl-alert bad">'
                        f'<span class="hitl-alert-icon">!</span>'
                        f"<div><div class=\"hitl-alert-title\">Flagged medication</div>"
                        f'<div class="hitl-alert-body">{_esc(", ".join(flagged))}</div></div></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"Remove {', '.join(flagged)} & re-run validation",
                        key=f"fix_allergy_{pid}",
                        type="primary",
                    ):
                        fixed_case = _remove_meds_by_name(case, flagged)
                        st.session_state.case = fixed_case
                        with st.spinner("Validator…"):
                            _run_revalidate(
                                fixed_case,
                                pid=pid,
                                elicit_answers=None,
                                sync_pipeline_after_hitl=sync_pipeline_after_hitl,
                            )
                _edit_allergy_meds(case, pid=pid)
            rendered.update({"allergies", "medications"})

        if "bill" in open_panels:
            with _CorrPanel("Billing", hint="Mark PAID after settlement."):
                _edit_bill(case, pid=pid)
            rendered.add("bill")

        if "followup" in open_panels:
            with _CorrPanel(
                "Follow-up",
                shared="follow_up_appointment" in soft,
                hint="Required by EHR care plan.",
            ):
                _edit_followup(case, pid=pid)
            rendered.add("follow_up_appointment")
            elicit_answers["follow_up_appointment"] = case.get("follow_up_appointment")

        if "approval" in open_panels:
            with _CorrPanel(
                "Discharge approval",
                hint="Clinician must confirm discharge_ok.",
            ):
                _edit_approval(case, pid=pid)
            rendered.add("discharge_ok")

        if "other" in open_panels:
            st.markdown(
                '<div class="hitl-alert warn">'
                '<span class="hitl-alert-icon">!</span>'
                "<div><div class=\"hitl-alert-title\">Unknown Critical rule</div>"
                '<div class="hitl-alert-body">Use More case fields, then re-run validation.</div>'
                "</div></div>",
                unsafe_allow_html=True,
            )

        # Remaining soft fields not covered by Critical panels
        patient_soft = [
            f
            for f in soft
            if f not in rendered
            and f
            not in {
                "follow_up_appointment",
                "allergies",
                "medications",
                "bill",
                "discharge_ok",
            }
            and not (
                SOFT_COVERED_BY_PANEL.get(f) is not None
                and SOFT_COVERED_BY_PANEL.get(f) in open_panels
            )
        ]
        if patient_soft:
            with _CorrPanel("Patient information", hint="Soft completeness gaps."):
                for field in patient_soft:
                    _edit_soft_field(case, field, pid=pid, elicit_answers=elicit_answers)
                    rendered.add(field)

        # Any leftover soft fields (edge cases)
        for field in soft:
            if field in rendered:
                continue
            cover_panel = SOFT_COVERED_BY_PANEL.get(field)
            if cover_panel is not None and cover_panel in open_panels:
                if field in case and case.get(field) not in (None, "", []):
                    elicit_answers[field] = case.get(field)
                continue
            with _CorrPanel(field.replace("_", " ").title(), hint="Soft gap"):
                _edit_soft_field(case, field, pid=pid, elicit_answers=elicit_answers)
            rendered.add(field)

    elif not issues and not soft and not gate_busy:
        st.markdown(
            '<div class="hitl-clear-banner">'
            '<span class="empty-icon" aria-hidden="true">✓</span>'
            "<div><div class=\"hitl-alert-title\">No corrections needed</div>"
            '<div class="hitl-alert-body">Validation is clear. You can generate the '
            "discharge summary.</div></div></div>",
            unsafe_allow_html=True,
        )

    # ── Optional case fields ──────────────────────────────────────────
    with st.expander("More case fields", expanded=False):
        st.caption("Optional edits not required by open HITL items.")
        opt_patient = "patient_name" not in rendered or "address" not in rendered
        if "allergy" not in open_panels:
            st.markdown('<div class="corr-opt-label">Medication</div>', unsafe_allow_html=True)
            _edit_allergy_meds(case, pid=f"{pid}_x")
        if "bill" not in open_panels:
            st.markdown('<div class="corr-opt-label">Billing</div>', unsafe_allow_html=True)
            _edit_bill(case, pid=f"{pid}_x")
        if "followup" not in open_panels and "follow_up_appointment" not in rendered:
            st.markdown('<div class="corr-opt-label">Follow-up</div>', unsafe_allow_html=True)
            _edit_followup(case, pid=f"{pid}_x")
        if "approval" not in open_panels:
            st.markdown('<div class="corr-opt-label">Approval</div>', unsafe_allow_html=True)
            _edit_approval(case, pid=f"{pid}_x")
        if opt_patient:
            st.markdown('<div class="corr-opt-label">Patient</div>', unsafe_allow_html=True)
            d1, d2 = st.columns(2)
            if "patient_name" not in rendered:
                case["patient_name"] = d1.text_input(
                    "Patient name",
                    value=str(case.get("patient_name") or ""),
                    key=f"x_pname_{pid}",
                )
            if "address" not in rendered:
                case["address"] = d2.text_input(
                    "Address",
                    value=str(case.get("address") or ""),
                    key=f"x_addr_{pid}",
                )

    # ── Audit notes ───────────────────────────────────────────────────
    with st.expander("Audit notes", expanded=False):
        st.markdown(
            '<div class="audit-card-lede">Documentation only — does not clear HITL-1 or HITL-2.</div>',
            unsafe_allow_html=True,
        )
        st.session_state.risk_override = st.selectbox(
            "Risk override",
            ["Keep model", "Force Low (document reason)", "Force HITL"],
            index=["Keep model", "Force Low (document reason)", "Force HITL"].index(
                st.session_state.risk_override
            )
            if st.session_state.risk_override
            in {"Keep model", "Force Low (document reason)", "Force HITL"}
            else 0,
            key=f"risk_override_{pid}",
        )
        st.session_state.approval_note = st.text_area(
            "Correction note",
            value=st.session_state.approval_note,
            height=120,
            key=f"approval_note_{pid}",
        )

    # ── Primary actions ───────────────────────────────────────────────
    can_summarize = bool(val) and not (
        val.get("discharge_blocked") or val.get("needs_hitl") or issues
    )
    st.markdown(
        '<div class="hitl-actions">'
        '<div class="hitl-actions-label">Primary actions</div></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Save note", use_container_width=True):
            path = append_feedback(
                {
                    "patient_id": pid,
                    "trace_id": st.session_state.trace_id,
                    "approval_note": st.session_state.approval_note,
                    "risk_override": st.session_state.risk_override,
                    "case_snapshot": case,
                }
            )
            st.success(f"Saved → `{path}`")
    with c2:
        if st.button("Re-run validation", type="primary", use_container_width=True):
            for k, v in elicit_answers.items():
                if v is not None and str(v).strip() != "":
                    case[k] = v
            answers = {
                k: v for k, v in elicit_answers.items() if v is not None and str(v).strip() != ""
            } or None
            with st.spinner("Validator…"):
                _run_revalidate(
                    case,
                    pid=pid,
                    elicit_answers=answers,
                    sync_pipeline_after_hitl=sync_pipeline_after_hitl,
                )
    with c3:
        if st.button(
            "Generate summary",
            use_container_width=True,
            disabled=not can_summarize,
        ):
            if not st.session_state.validation:
                st.warning("Validate first.")
            else:
                out = bridge.maybe_summarize(case, st.session_state.validation)
                if out.get("error"):
                    st.error(out["error"])
                else:
                    sync_pipeline_after_hitl(
                        case=case,
                        validation=st.session_state.validation,
                        summary=out.get("summary"),
                        indexed=True,
                    )
                    st.success("Summary ready — open Discharge Summary")
                    st.rerun()
    if not can_summarize:
        st.caption("Generate summary unlocks when Critical blocks and HITL flags are cleared.")
```

### RAG Assistant
- Ensure index button; chat_input; works during HITL-2.

### Discharge Summary
- Gate closed → warning; no summary → info.
- Hero letter HTML; Export JSON + Markdown.

---

## M. Extra features (implement freely if helpful)

Stay in the same visual language. Suggestions:
- Indeterminate progress while Host runs
- Reset case button
- Print CSS for summary
- Live stage highlight if Host streams stages
- Better empty states, a11y labels, audit openers
- Do not break idle-first or stepper semantics

---

## N. Acceptance checklist

- [ ] `http://127.0.0.1:8501` clean chrome
- [ ] First paint idle (no chart/findings/summary); Gate=Idle; all steps pending
- [ ] Status strip + pipeline track on every page
- [ ] Process patient fills state; spinner while running
- [ ] Patient change clears clinical state
- [ ] Blocked case: Gate blocked ✕, Summary skipped –
- [ ] Clear case with summary: Gate done ✓, Summary done ✓
- [ ] HITL re-validate flips Gate without full Host re-run
- [ ] Five pages; RAG nav = RAG Assistant
- [ ] Visual: dark sidebar, teal primary, fonts, cards, pipe pills
- [ ] No clinical rules reimplemented in UI

---

## O. CURSOR PROMPT (paste into cap_proj_v3)

```
Rebuild the Streamlit HITL Dashboard for this project (cap_proj_v3) from the SPEC DOCUMENT I am providing / attaching: HITL Streamlit Spec + Cursor Prompt (self-contained). Do NOT copy files from another repository. Implement everything from the spec.

GOALS
- Fix bad URL → http://127.0.0.1:8501 via .streamlit/config.toml + launch flags.
- Fix preloaded patient chart → idle-first session (case/validation/summary/pipeline_result start as None; only patient selector set).
- Fix missing progress → permanent pipeline track Monitor→Extract→Normalize→Validate→Index→Gate→Summary with pending/done/active/blocked/skipped semantics from the spec.
- Match clinical visual system: dark sidebar, teal #0f766e, Plus Jakarta Sans + Source Serif 4, status strip, page headers, finding cards, summary hero. Use the FULL CSS block from the spec.
- Five FA5 pages; RAG nav label "RAG Assistant".
- Thin bridge to EXISTING V3 agents only — do not rewrite FA5 backend or duplicate clinical rules.

IMPLEMENTATION
1. Create HITL package modules: app.py, styles.py (CUSTOM_CSS + pipeline_step_states + inject_styles), ui_chrome.py, state.py, bridge.py (V3 imports), corrections.py, __main__.py.
2. Create .streamlit/config.toml exactly as in the spec.
3. main() order: set_page_config → inject_styles → ensure_session_defaults → sidebar → status_strip → pipeline_track → page body.
4. Wire bridge to V3 Host/Monitor/Validator/RAG/Summary APIs using the contract in the spec.
5. Port page behaviors and Corrections UX from the reference code blocks in the spec (adapt imports).
6. Optionally add extras from section M (progress during run, reset, print CSS, etc.) without breaking idle-first/stepper.
7. Add smoke tests for idle defaults, patient clear, pipeline_step_states blocked vs clear, five pages.
8. Run the app and verify the acceptance checklist.

CONSTRAINTS
- No file copies from other repos.
- No purple/cream default AI themes; no emoji nav.
- No feature flag dual UI.
- If a V3 API is missing, smallest stub + clear comment — no fake clinical outcomes.

DONE WHEN acceptance checklist in the spec is green.

Start now: inspect V3 Streamlit entrypoints, then implement the full UI from the spec in one pass.
```

---

## P. State module reference

```python
"""Session state + HITL feedback persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from discharge_ai.infra.config import get_settings

PATIENTS = ["P1019", "P1020", "P1021", "P1022", "P1023", "P1024"]

PAGES = (
    "Document Viewer",
    "Validation Report",
    "HITL Corrections",
    "RAG Q&A",
    "Discharge Summary",
)


def ensure_session_defaults() -> None:
    import streamlit as st

    defaults: dict[str, Any] = {
        "patient_id": "P1019",
        "page": PAGES[0],
        "pipeline_result": None,
        "case": None,
        "validation": None,
        "summary": None,
        "trace_id": None,
        "rag_session_id": None,
        "rag_history": [],
        "langfuse_trace_url": "",
        "last_error": None,
        "approval_note": "",
        "risk_override": "Keep model",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def feedback_path() -> Path:
    settings = get_settings()
    root = settings.abs_path(settings.paths.data_hitl)
    root.mkdir(parents=True, exist_ok=True)
    return root / "feedback.jsonl"


def append_feedback(payload: dict[str, Any]) -> Path:
    path = feedback_path()
    row = {
        **payload,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def risk_badge_class(level: str | None) -> str:
    lv = (level or "").lower()
    if lv == "high":
        return "badge-bad"
    if lv == "medium":
        return "badge-warn"
    if lv == "low":
        return "badge-ok"
    return "badge-mute"
```

---

**End of document.** Feed Section O + this whole file into Cursor on `cap_proj_v3`.
