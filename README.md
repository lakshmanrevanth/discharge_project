# Agentic-System-for-Automated-Discharge-Summariser

Agentic AI system for automated hospital discharge summaries (FA5 capstone).

**Status:** Phases 1–12 complete against the SSoT. One-command lab stack via `./scripts/start.sh`.

## Documentation (SSoT)

- [`Documentation/REQUIREMENTS_REFERENCE.md`](Documentation/REQUIREMENTS_REFERENCE.md) — single source of truth
- [`Documentation/architecture.md`](Documentation/architecture.md) — end-to-end architecture
- [`Documentation/coding_style/`](Documentation/coding_style/) — company coding patterns
- [`.cursor/plans/phased_implementation_roadmap_816e3afe.plan.md`](.cursor/plans/phased_implementation_roadmap_816e3afe.plan.md) — build order + per-phase status
- [`NUVEPRO.md`](NUVEPRO.md) — one-shot lab pack / boot checklist

## Quick start

```bash
cp .env.example .env          # fill AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
uv sync                       # create .venv (also run by start.sh)
chmod +x scripts/start.sh scripts/stop.sh

./scripts/start.sh            # EHR · both MCPs · RAG A2A · Streamlit HITL
# open http://127.0.0.1:8501

./scripts/stop.sh             # stop the lab stack
```

**Required in `.env`:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`, `BEDROCK_PRIMARY_MODEL_ID`, `AGENT_AUTH_TOKEN`.  
See [`.env.example`](.env.example). Prove Bedrock with: `uv run python scripts/bedrock_ping.py` (expects `LIVE`).

**NuvePro:** pack with `./scripts/pack_for_nuvepro.sh` (includes filled `.env`), then on the lab run `./scripts/start.sh`. `start.sh` sets `BIND_HOST=0.0.0.0` so the forwarded UI is reachable. Details: [`NUVEPRO.md`](NUVEPRO.md).

### Ports (lab stack from `start.sh`)

| Service | Port |
| --- | --- |
| Mock EHR | `:8050` |
| Primary MCP `/clinicaltools` | `:8200` |
| Secondary MCP `/analyticstools` | `:8201` |
| Clinical RAG A2A | `:8105` |
| Streamlit HITL dashboard | `:8501` |

Logs: `logs/*.log`. Full port map (Monitor / Extractor / Normalizer / Validator / Summary / Host): [`configs/agent_config.yaml`](configs/agent_config.yaml).

### Optional: start services individually

```bash
uv run python -m mock_ehr               # Mock EHR REST API           :8050
uv run python -m mcp_servers.primary    # Primary MCP /clinicaltools  :8200
uv run python -m mcp_servers.secondary  # Secondary MCP /analyticstools :8201
uv run python -m dashboard              # HITL Streamlit              :8501
```

Full A2A agent set (needed for Host Gradio / remote A2A):

```bash
uv run python -m agents.monitor         # Discharge Monitor A2A       :8103
uv run python -m agents.extractor       # Clinical Extractor A2A      :8100
uv run python -m agents.normalizer      # Clinical Normalizer A2A     :8102
uv run python -m agents.validator       # Clinical Validator A2A      :8101
uv run python -m agents.summary         # Summary Generator A2A       :8104 (streaming)
uv run python -m rag                    # Clinical RAG Q&A A2A        :8105 (streaming)
uv run python -m host                   # Host Gradio                 :8083
```

Or via launcher: `uv run python run.py --core` / `uv run python run.py --all`.

## What was built

Pipeline: **Monitor → Extract → Normalize → Validate (gate) → Summary / RAG**, with HITL on Streamlit and Host orchestration on Gradio.

| Phase | Module | Status |
| --- | --- | --- |
| 1 | `shared/` settings + logger · Mock EHR FastAPI `:8050` | ✅ done |
| 2 | Primary MCP `:8200/clinicaltools` — resources + prompts | ✅ done |
| 3 | Roots + Clinical Watcher + Monitor A2A `:8103` | ✅ done |
| 4 | Harvester + Extractor LangGraph A2A `:8100` | ✅ done |
| 5 | Medical Lang Bridge (Sampling) + Normalizer LangGraph A2A `:8102` | ✅ done |
| 6–7 | Rules Engine / EHR Validation / Reporter + Secondary MCP `:8201` | ✅ done |
| 8 | Validator agent + release gate `:8101` | ✅ done |
| 9 | Summary Generator (A2A streaming) `:8104` | ✅ done |
| 10 | Agno RAG `:8105` | ✅ done |
| 11 | Streamlit HITL dashboard `:8501` | ✅ done |
| 12 | Host (ADK + Gradio) `:8083` + `run.py` | ✅ done |

### Phases 4–5 — Extract + Normalize

- **Extractor** — harvest text via MCP, then **LLM** (Bedrock) fills structured fields for every doc (JSON / txt / PDF / OCR). PDFs via PyPDF2; set `TESSERACT_ENABLED=true` for image OCR when no `.ocr.txt` sidecar.
- **JSON intake** — when a file has both a narrative `raw_text` and structured keys (e.g. P1021 Hindi discharge), the Harvester returns the narrative **plus** a `--- structured fields ---` dump so age/ward/dates are not hidden from the LLM. After extraction, blank discharge fields are filled from `structured_data` (same idea as bill merge). Planted nulls (`address`, `follow_up_appointment`) stay empty so validation still HITLs them.
- **Normalizer** — MCP **Sampling** via Medical Lang Bridge. The LLM runs in the client `sampling_callback` (LiteLLM), not inside the MCP server.
- **Languages** — primary set from `rules.yaml`: `en`, `es`, `hi`, `de`, `fr`, `nl`. Unexpected languages use a fallback path (still translate). Post-pass: abbrev expand, med canonicalize (§12.3; Paracetamol is the project canonical form), ICD-10.
- Normalizer A2A can ask Extractor over A2A when no extraction JSON is embedded — start Extractor (`:8100`) for that path.

### Phases 6–8 — Validate + risk

- **Rules Engine** — FA5 Table 3 completeness from `rules.yaml`. Blocking gaps → hard findings; non-blocking gaps → one batched MCP **Elicitation**.
- **EHR Validation** — all 7 FA5 Table 4 rules vs Mock EHR (meds, allergies, labs, care plan, bill), with med name canonicalization.
- **Insight Reporter** — JSON + HTML (+ PDF) under `data/reports/`, stamped with `rules_version` (SHA-256 of `rules.yaml`).
- **Secondary MCP** (`:8201/analyticstools`) — `calculate_risk_score`, `get_population_benchmarks`, `generate_risk_heatmap`. Hard HITL guardrails (e.g. allergy contradiction) force `high`.
- **Validator** (`:8101`) — LangGraph `completeness → ehr → risk → report`. Default elicitation auto-declines; Streamlit installs a real handler on re-run.
- Smoke outcomes (§12): P1019 auto-approves; P1021/P1022 hard/blocking HITL; med-omission → Medium HITL.

### Phase 9 — Summary (streaming)

- Google ADK on `:8104`, A2A streaming only. Fixed section order: `patient → meds → labs → bill → instructions`.
- Release gate refuses when `risk_level=high` or `discharge_blocked=true`.
- Prompt from MCP `summary-generation-prompt` (never hardcoded). ToxicityFilter on `instructions`.

### Phase 10 — RAG (streaming)

- Five Agno agents on `:8105`: Indexing → Retrieval → Augmentation → Generation → Reflection.
- FAISS per `patient_id` under `data/vector_db/{patient_id}/`; MiniLM embeddings.
- Generation uses MCP `rag-answer-prompt`, `MultiMCPTools`, SqliteDb (`num_history_runs=3`).
- Out-of-context → exact refusal from `agent_config.yaml`. RAG Triad gated by `rules.yaml` thresholds.
- After Corrections **Re-run**, FAISS rebuilds from HITL-reviewed discharge facts **including accepted elicitation fields** (e.g. attending physician).

### Phase 11 — HITL Streamlit

- Single app (`dashboard/app.py`) on `:8501` — five clinical pages (Document Viewer, Validation Report, Corrections, RAG Q&A, Discharge Summary) plus **Upload new patients**.
- Sidebar **live patient search** (ID or name) over files under `data/input/` — no hard-coded sample list.
- **Process patient** runs extract → normalize → validate in-process (MCP + Bedrock); pages degrade when backends are offline.
- **Upload** requires discharge + lab + bill; after a full upload the dashboard runs the same Process pipeline. Process is blocked until all three intake types exist on disk.
- Corrections: `st.data_editor`, elicitation accept/decline/cancel, approval, re-run (re-indexes RAG with elicited fields); feedback under `data/hitl/`.

### Phase 12 — Host

- Google ADK Host + Gradio `:8083` with streaming-capable A2A client.
- Tools: list agents / delegate / full case pipeline (Monitor → Extract → Normalize → Validate → Summary when gated).
- `run.py` launches services from `configs/agent_config.yaml`.

### Observability / RAI

- LangFuse traces (cloud when `LANGFUSE_*` set, else local `data/reports/traces/`).
- A2A `trace_id` metadata, PIIRedactor on logs, GuardrailManager release gate.
- Audit + summary PDF beside JSON/HTML. RAG Generation dual-MCP (Primary+Secondary, Primary-only fallback).

## Layout

| Folder | Role |
| --- | --- |
| `agents/` | Monitor · Extractor · Normalizer · Validator · Summary (A2A) |
| `rag/` | Agno Clinical RAG Q&A `:8105` (5 agents + FAISS) |
| `mcp_servers/` | Primary `:8200/clinicaltools` · Secondary `:8201/analyticstools` |
| `shared/` | settings, logger, llm, guardrails, tracing, models, clinical_normalize |
| `mock_ehr/` | FastAPI Mock EHR `:8050` |
| `dashboard/` | Streamlit HITL `:8501` |
| `host/` | Gradio Host Orchestrator `:8083` |
| `configs/` | `rules.yaml`, prompts, agent/model/MCP config |
| `scripts/` | `start.sh` · `stop.sh` · `bedrock_ping.py` · `pack_for_nuvepro.sh` · `e2e_ssot_validate.py` |
| `tests/` | HITL smoke + patient-search e2e |
| `data/input/` | MCP Roots workspace (sample corpus P1019–P1024) |
| `Documentation/` | Specs, seeds, coding style (not runtime) |

## Manually testing what's built

```bash
# Mock EHR
curl http://127.0.0.1:8050/health
curl http://127.0.0.1:8050/patients/P1019

# Primary MCP — FastMCP Inspector / CLI
uv run fastmcp dev mcp_servers/primary/server.py

# Extractor (needs Primary MCP + Bedrock)
uv run python -c "
import asyncio, json
from agents.extractor.graph import run_extraction
print(json.dumps(asyncio.run(run_extraction('P1019')), indent=2, ensure_ascii=False))
"

# Normalizer — Hindi sample via Sampling (needs Primary MCP + Bedrock)
uv run python -c "
import asyncio, json
from agents.extractor.graph import run_extraction
from agents.normalizer.graph import run_normalization
async def main():
    ext = await run_extraction('P1021')
    print(json.dumps(await run_normalization('P1021', ext), indent=2, ensure_ascii=False))
asyncio.run(main())
"

# A2A AgentCards (public; services must be running)
curl http://127.0.0.1:8103/.well-known/agent.json
curl http://127.0.0.1:8100/.well-known/agent.json
curl http://127.0.0.1:8102/.well-known/agent.json
curl http://127.0.0.1:8101/.well-known/agent.json
curl http://127.0.0.1:8104/.well-known/agent.json
curl http://127.0.0.1:8105/.well-known/agent.json

# Validator — full pipeline (Primary + Secondary MCP, Mock EHR, Bedrock)
uv run python -c "
import asyncio, json
from agents.extractor.graph import run_extraction
from agents.normalizer.graph import run_normalization
from agents.validator.graph import run_validation
async def main():
    ext = await run_extraction('P1019')
    norm = await run_normalization('P1019', ext)
    report = await run_validation('P1019', norm)
    print(json.dumps(report, indent=2, ensure_ascii=False))
asyncio.run(main())
"

# Summary — gate + section texts (needs Primary MCP + Bedrock)
uv run python -c "
import asyncio, json
from agents.summary.agent import run_summary
payload = {
  'patient_id': 'P1019',
  'discharge': {'patient_id': 'P1019', 'patient_name': 'Thomas Wright', 'age': 58,
    'gender': 'M', 'admission_date': '2026-01-01', 'discharge_date': '2026-01-05',
    'ward': 'Medicine', 'bed_no': '12', 'attending_physician': 'Dr. Patel',
    'consulting_doctors': [], 'discharge_diagnosis': ['Type 2 Diabetes Mellitus'],
    'medications': [{'medicine_name': 'Metformin', 'strength': '500 mg',
      'frequency': 'BID', 'route': 'PO', 'period': '7 days'}],
    'allergies': [], 'follow_up_appointment': 'Endocrinology in 30 days',
    'discharge_instructions': 'Monitor blood sugar.', 'discharge_approved': True},
  'lab': {}, 'bill': {'total_amount': 420.0, 'payment_status': 'PAID'},
}
async def main():
    s = await run_summary(patient_id='P1019', risk_level='low',
                          discharge_blocked=False, extraction=payload)
    print(json.dumps(s.model_dump(), indent=2, ensure_ascii=False))
asyncio.run(main())
"

# RAG — grounded Q&A (needs Primary MCP + Bedrock; indexes data/input/)
uv run python -c "
import asyncio, json
from rag.pipeline import ask
async def main():
    print(json.dumps(await ask('P1019', 'What medications were prescribed?'), indent=2))
    print(json.dumps(await ask('P1019', 'Who won the World Cup?'), indent=2))
asyncio.run(main())
"

# HITL dashboard (lab stack: EHR + MCPs + RAG + Streamlit)
./scripts/start.sh
# Sidebar: search P1019 / Diego → Document Viewer → Process patient
# or: uv run python -m dashboard

# Host Orchestrator — Gradio :8083 (needs A2A agents for live pipeline)
uv run python -m host

# Launch many services at once
uv run python run.py              # dry-run plan
uv run python run.py --core       # EHR + MCP + A2A agents
uv run python run.py --all        # everything including Host + HITL

# Optional smoke tests
uv run pytest tests/test_hitl_dashboard_smoke.py -q
uv run python scripts/e2e_ssot_validate.py   # needs lab stack + Bedrock
```
# discharge_project
