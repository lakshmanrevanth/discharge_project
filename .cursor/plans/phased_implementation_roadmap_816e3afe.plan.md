---
name: Phased Implementation Roadmap
overview: "Build the discharge-summary system one independently testable module at a time, bottom-up: foundation → Mock EHR → MCP primitives → pipeline agents → HITL/Host. After you approve, only Phase 1 is implemented; later phases wait until you have reviewed that code line-by-line."
todos:
  - id: phase-1-shared-mock-ehr
    content: "Phase 1: shared settings/logger + Mock EHR FastAPI :8050 from seed data (only after plan approval)"
    status: completed
  - id: phase-2-primary-mcp
    content: "Phase 2 (later): Primary MCP skeleton + rules resources on :8200"
    status: completed
  - id: phase-3-monitor-roots
    content: "Phase 3 (later): Watcher + Roots + Discharge Monitor :8103"
    status: completed
  - id: phase-4-harvester-extractor
    content: "Phase 4: Clinical Data Harvester tool + Extractor agent :8100 (completed)"
    status: completed
  - id: phase-5-lang-bridge-normalizer
    content: "Phase 5: Medical Lang Bridge + Sampling + Normalizer :8102 (completed)"
    status: completed
  - id: phase-6-8-validation-gate
    content: "Phases 6-8: Rules Engine + EHR Validation + Reporter + Secondary MCP :8201 + Validator gate :8101 (completed)"
    status: completed
  - id: phase-9-summary
    content: "Phase 9: Summary Generator Google ADK streaming :8104 (completed)"
    status: completed
  - id: phase-10-rag
    content: "Phase 10: Agno RAG 5 agents FAISS streaming :8105 (completed)"
    status: completed
  - id: phase-11-hitl
    content: "Phase 11: Streamlit HITL dashboard :8501 (5 pages + ingest + elicitation) (completed)"
    status: completed
  - id: phase-12-host
    content: "Phase 12: Host ADK + Gradio :8083 + run.py launcher (completed)"
    status: completed
isProject: false
---

# Phased Implementation Roadmap

Authority: [`Documentation/REQUIREMENTS_REFERENCE.md`](Documentation/REQUIREMENTS_REFERENCE.md) + [`Documentation/architecture.md`](Documentation/architecture.md). Repo today is docstring stubs only; real assets are configs, `data/input/` (P1019–P1024), and [`Documentation/mock_ehr/data.py`](Documentation/mock_ehr/data.py).

## Where code will be written

All runtime code lives at **repo root** (not under `Documentation/`). We fill in the existing stub files — we do not invent a parallel tree.

| Phase | Folder / files |
| --- | --- |
| **1 (next)** | [`shared/settings.py`](shared/settings.py), [`shared/logger.py`](shared/logger.py) · [`mock_ehr/app.py`](mock_ehr/app.py), [`mock_ehr/routes.py`](mock_ehr/routes.py), plus seed from `Documentation/mock_ehr/data.py` → e.g. `mock_ehr/seed.py` · light edits to [`pyproject.toml`](pyproject.toml) |
| **2** | [`mcp_servers/primary/server.py`](mcp_servers/primary/server.py), [`resources.py`](mcp_servers/primary/resources.py), [`prompts.py`](mcp_servers/primary/prompts.py) |
| **3** | [`mcp_servers/primary/roots.py`](mcp_servers/primary/roots.py), Watcher tool under `mcp_servers/primary/tools/` · [`agents/monitor/`](agents/monitor/) |
| **4** | Harvester tool under `mcp_servers/primary/tools/` · [`agents/extractor/`](agents/extractor/) |
| **5** | Lang Bridge + [`mcp_servers/primary/sampling.py`](mcp_servers/primary/sampling.py) · [`agents/normalizer/`](agents/normalizer/) (incl. `sampling_callback.py`) |
| **6–7** | Rules / EHR / Reporter tools under `mcp_servers/primary/tools/` · [`mcp_servers/secondary/`](mcp_servers/secondary/) |
| **8** | [`agents/validator/`](agents/validator/) |
| **9** | [`agents/summary/`](agents/summary/) |
| **10** | [`rag/`](rag/) |
| **11** | [`dashboard/`](dashboard/) (+ `elicitation_callback.py`) |
| **12** | [`host/`](host/) · [`run.py`](run.py) |

**Not written as runtime code:** `Documentation/` stays specs/seeds/coding-style only. Configs stay in [`configs/`](configs/) (YAML already present; Phase 1 only *reads* them).

## Coding style & versions (binding — from SSoT)

Source: [`Documentation/REQUIREMENTS_REFERENCE.md`](Documentation/REQUIREMENTS_REFERENCE.md) **§10.1** (PREFERRED pins) and **§10.2** (MUST FOLLOW style). Refs: `Documentation/coding_style/{langgraph,rag,MCP_A2A}.txt`.

**Every phase must:**

1. Install with **`uv add`**, not ad-hoc pip.
2. Use **company pins when the package is listed** (e.g. `uvicorn==0.35.0`, `httpx==0.28.1`, `starlette==0.47.3`, `fastmcp==2.12.2`, `mcp==1.14.0`, `langgraph==0.6.7`, `a2a-sdk==0.3.22`, `google-adk==1.25.0`, `agno==2.1.4`, `litellm==1.80.7`, `gradio==6.5.1`, …). Deviate only with a recorded reason.
3. Add FA5-required packages **not** on the company list as needed (Streamlit, FastAPI, FAISS, LangFuse, sentence-transformers) — latest compatible unless a pin appears later.
4. Follow coding-style refs: beginner-friendly, little abstraction, MCP tools on the server (MCP/A2A wins over LangGraph-local tools), `InMemorySaver` for LangGraph when we reach agents, `A2AStarletteApplication` pattern for `a2a-sdk==0.3.22`.
5. Do **not** invent architectures beyond what the three reference files demonstrate unless FA5 forces it.

**Phase 1 pin note:** Mock EHR needs FastAPI (FA5, not in company list) + pinned `uvicorn==0.35.0`, `httpx==0.28.1`, and `starlette==0.47.3` where pulled in. Later phases pull their pins only when that phase starts (no full stack install in Phase 1).

## Principle

- **One phase at a time.** After approval of this plan, implement **only Phase 1**. Stop. You review every line. Then approve Phase 2, and so on.
- Each phase ends with a **manual test you can run** (curl / small script / single service).
- **Always** apply §10.1 pins + §10.2 coding style above. Shared clinical tools live on MCP — not inside agents.
- Pipeline order in the architecture is Monitor → Extract → Normalize → Validate → Gate → Summary → RAG. **Build order is dependency order**, not left-to-right, so each piece can be tested without unfinished callers.

```mermaid
flowchart LR
  P1[Phase1_Shared_MockEHR]
  P2[Phase2_PrimaryMCP_skeleton]
  P3[Phase3_Watcher_Roots_Monitor]
  P4[Phase4_Harvester_Extractor]
  P5[Phase5_LangBridge_Normalizer]
  P6[Phase6_Rules_EHR_Reporter]
  P7[Phase7_Secondary_Risk]
  P8[Phase8_Validator_Gate]
  P9[Phase9_Summary_A2A]
  P10[Phase10_RAG]
  P11[Phase11_HITL_Elicitation]
  P12[Phase12_Host_run]
  P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9 --> P10 --> P11 --> P12
```

---

## Full build order (why this order)

| Phase | Module | Why next | How you test it alone |
| --- | --- | --- | --- |
| **1** | Shared settings + Mock EHR `:8050` | Everything validation-related needs EHR; no LLM keys; pure FastAPI | `curl` patient/meds/allergy routes |
| **2** | Primary MCP server skeleton `:8200` | Resources + empty tool shell; agents need a live MCP | List/read resources (`rules.yaml` URIs) |
| **3** | Clinical Watcher + Roots + Monitor `:8103` | First real intake slice; matches architecture step 1 | Drop/list files under `data/input/` via Roots |
| **4** | Harvester + Extractor `:8100` | Turns files into structured JSON (start with TXT/JSON patients) | Run Extractor on P1019 / P1021 |
| **5** | Lang Bridge + Sampling + Normalizer `:8102` | Primary langs en/es/hi/de/fr/nl + fallback; confidence; LiteLLM | Run Normalizer on ES/HI/NL (+ optional unexpected lang) |
| **6** | Rules Engine + EHR Validation Tool + Reporter | Completeness + Table 4 + audit artifact | Call tools with hand-built JSON |
| **7** | Secondary MCP risk `:8201` | Third parallel check | `calculate_risk_score` for a known finding set |
| **8** | Validator + release gate `:8101` | Three checks together → report → gate (architecture §3–4) | Assert P1019 auto / P1022 hard HITL |
| **9** | Summary Generator streaming `:8104` | Only after gate allows | Stream sections for an auto-approve case |
| **10** | Agno RAG `:8105` | FAISS + 5 agents + refusal string | Ask in/out-of-context questions |
| **11** | Streamlit HITL + elicitation callback | Non-blocking gaps + Page 3 corrections | Accept/decline/cancel form |
| **12** | Host Gradio + `run.py` wiring | End-to-end orchestration | One case through full pipeline |

**Not first:** Monitor alone (needs MCP Roots/Watcher), Normalizer alone (needs MCP Sampling), Validator alone (needs EHR + rules tools). Those come after their MCP dependencies.

---

## Phase 1 (only this after you approve) — Shared + Mock EHR

**Goal:** Load project config from YAML; serve Mock EHR on `:8050` from the existing seed so later EHR Validation Tool can call real HTTP.

### What we will implement

1. **Dependencies (minimal, SSoT §10.1)**  
   Via `uv add`: `fastapi` (FA5 — unpinned company list), `uvicorn==0.35.0`, `httpx==0.28.1`, `pyyaml`, `pydantic` as needed; align `starlette` with `0.47.3` if resolved as a dep. Do **not** install LangGraph/ADK/Agno/LiteLLM yet.

2. **[`shared/settings.py`](shared/settings.py)**  
   - Load [`configs/agent_config.yaml`](configs/agent_config.yaml) (ports/paths).  
   - Expose typed accessors for `mock_ehr` host/port and `data/` paths.  
   - Keep beginner-simple (no heavy DI framework).

3. **[`shared/logger.py`](shared/logger.py)**  
   - Thin INFO logger writing toward `data/reports/pipeline.log` (or console for Phase 1).

4. **Mock EHR data**  
   - Promote [`Documentation/mock_ehr/data.py`](Documentation/mock_ehr/data.py) into runtime (e.g. `mock_ehr/seed.py` import or copy) — preserve planted mismatches for P1019–P1024.  
   - FA5 wants 5 domains: patients, meds, allergies, labs, care plans. Keep `GUIDELINES` available but unused by routes unless needed later.

5. **[`mock_ehr/routes.py`](mock_ehr/routes.py) + [`mock_ehr/app.py`](mock_ehr/app.py)**  
   - FastAPI app on port **8050**.  
   - Simple REST routes (FA5 leaves schemas to us), e.g.:  
     - `GET /health`  
     - `GET /patients/{patient_id}`  
     - `GET /patients/{patient_id}/medications`  
     - `GET /patients/{patient_id}/allergies`  
     - `GET /patients/{patient_id}/labs`  
     - `GET /patients/{patient_id}/care-plan`  
   - 404 when patient missing; no auth (NOT SPECIFIED).

6. **Smoke entry**  
   - Document: `uvicorn mock_ehr.app:app --port 8050` (or a tiny `python -m mock_ehr.app`).  
   - Do **not** expand `run.py` to launch the whole system yet.

### Explicitly out of Phase 1

- MCP servers, agents, A2A, LiteLLM, Streamlit, RAG, guardrails, LangFuse.

### Done when

- Server starts on `:8050`.  
- `curl` returns P1019 patient + meds + empty allergies; P1022/P1024 show Penicillin; P1021 unpaid bill is **not** in EHR (bill is intake-side) but care-plan/follow-up data is readable.  
- You can read every line of the Phase 1 files and understand them before Phase 2.

---

## After Phase 1 (preview only — not built yet)

- **Phase 2:** FastMCP Primary `:8200/clinicaltools` — expose `resource://clinical-rules/*` from `configs/rules.yaml`; server boots; no agent yet.  
- **Phase 3:** Watcher tool + Roots + Monitor agent — discover `data/input/` files.  
- Then Harvester/Extractor → Normalizer/Sampling → validation tools → Secondary risk → Validator gate → Summary → RAG → HITL → Host.

---

## How we will work together

1. You approve this plan.  
2. I implement **Phase 1 only**, keep code simple and commented where non-obvious.  
3. You review line-by-line; ask questions; we fix Phase 1 if needed.  
4. You explicitly say “go Phase 2” (or adjust order).  
5. Repeat.
