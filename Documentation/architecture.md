# System Architecture — Automated Discharge Summaries

**Project:** Agentic AI System for Automated Discharge Summaries for Hospitals  
**Authority:** [`REQUIREMENTS_REFERENCE.md`](REQUIREMENTS_REFERENCE.md) (SSoT)  
**Status:** Finalized workflow for implementation  

---

## 1. Design Rules

1. **Monitor discovers** intake files via MCP Roots / Clinical Watcher.
2. **Host orchestrates** the case via A2A (Gradio :8083).
3. **HITL is Streamlit** (:8501) — review, elicitation UI, corrections, RAG Q&A, exports.
4. **Shared tools live on MCP** — agents call tools; they do not reimplement them.
5. **Mock EHR** is reached only through the Primary **EHR Validation Tool**.
6. **Validation runs three checks together** — rules/completeness, EHR cross-validation, risk score (same Validation Agent step).
7. **MCP Elicitation ≠ full HITL** — elicitation is only for **non-blocking** gaps; owned by the Rules Engine Tool; decline/cancel still force Mandatory HITL (§4).
8. **Summary runs only after the release gate** allows it.
9. **RAG** is a top-level Agno subsystem (five agents), not nested under `agents/`.

---

## 2. Service Map


| Step | Component           | Framework           | Port                   | Notes                                       |
| ---- | ------------------- | ------------------- | ---------------------- | ------------------------------------------- |
| —    | Host Orchestrator   | Google ADK + Gradio | 8083                   | A2A client                                  |
| —    | HITL Dashboard      | Streamlit           | 8501                   | 5 FA5 pages + elicitation callback          |
| 1    | Discharge Monitor   | Google ADK          | 8103                   | Roots + Watcher                             |
| 2    | Clinical Extractor  | LangGraph           | 8100                   | Harvester + Resources/Prompts               |
| 3    | Clinical Normalizer | LangGraph           | 8102                   | Lang Bridge + **Sampling callback**         |
| 4    | Clinical Validation | LangGraph           | 8101                   | Rules, EHR tool, risk, Reporter             |
| 5    | Summary Generator   | Google ADK          | 8104                   | **A2A streaming**                           |
| 6    | Clinical RAG Q&A    | Agno (×5)           | 8105                   | **A2A streaming**                           |
| —    | Primary MCP         | FastMCP             | 8200 `/clinicaltools`  | All 6 primitives                            |
| —    | Secondary MCP       | FastMCP             | 8201 `/analyticstools` | Risk / benchmarks / heatmap                 |
| —    | Mock EHR            | FastAPI             | 8050                   | Patients, meds, allergies, labs, care plans |


**Runtime intake path:** `data/input/{doctor_reports,lab_reports,bills}/` (MCP Root).  
Seed corpus: `Documentation/Data/incoming/` → synced into `data/input/`.

---

## 3. End-to-End Architecture (ASCII)

```text
HOSPITAL

                 Different Hospital Departments Generate Documents
        ┌──────────────────┬───────────────────┬───────────────────┐
        │                  │                   │
        ▼                  ▼                   ▼
 Doctor Report        Lab Report            Hospital Bill
        │                  │                   │
        └──────────────────┴───────────────────┘
                           │
                           ▼
                data/input/          ← MCP Root workspace
                ├── doctor_reports/
                ├── lab_reports/
                └── bills/
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
                 1. DISCHARGE MONITOR AGENT
                    (Google ADK · A2A :8103)
                           │
                  Registers MCP ROOT
                  Clinical Watcher Tool
                  (ctx.list_roots only — no raw paths)
                           │
                     New case files found
                           │
                           ▼
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
              GOOGLE ADK HOST ORCHESTRATOR
                 (Gradio UI · A2A client :8083)
                           │
                  Creates / attaches Case ID
                  Groups files by patient
                  Calls agents in order via A2A
                           │
         ┌─────────────────┴──────────────────┐
         │                                    │
         ▼                                    ▼
   Streamlit HITL                      A2A Agent Pipeline
   Dashboard :8501                     (steps 2–6)
   (5 pages + elicitation)
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
               2. CLINICAL EXTRACTOR AGENT
                  (LangGraph · A2A :8100)
                           │
              Clinical Data Harvester Tool
              (Primary MCP :8200)
                           │
         OCR │ PDF │ PNG │ TXT │ JSON
                           │
              MCP Resources + Prompts
              (discharge-extraction-prompt)
                           │
                           ▼
               Structured Clinical JSON
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
               3. CLINICAL NORMALIZER AGENT
                  (LangGraph · A2A :8102)
                           │
           Medical Language Bridge Tool
              (Primary MCP + SAMPLING)
                           │
              Detect language
              Primary path: en/es/hi/de/fr/nl (seed + rules)
              Fallback path: unexpected lang → still translate
              Translate → English
              Expand abbreviations
              Emit confidence score
                           │
        MCP Sampling + Prompts + Resources
        (Normalizer owns sampling_callback → LiteLLM)
                           │
                           ▼
            Standardized English JSON
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
               4. CLINICAL VALIDATION AGENT
                  (LangGraph · A2A :8101)
                           │
         ┌─────────────────┼──────────────────────┐
         │                 │                      │
         ▼                 ▼                      ▼
   rules.yaml        EHR Validation Tool    Secondary MCP :8201
   via MCP Resource  → Mock EHR :8050       calculate_risk_score
   (Primary MCP)     (Patients/Meds/        (+ benchmarks / heatmap)
                      Allergies/Labs/
                      Care Plans)
         │                 │                      │
         └──────── Compare / score everything ────┘
                           │
              Checks:
              • Mandatory fields (blocking vs non-blocking)
              • Allergies / medicines / labs
              • Care plan / billing / business rules
              • Risk score
                           │
                           ▼
              Clinical Insight Reporter
              → Audit Report JSON + HTML(/PDF)
                (rules_version = SHA-256 of rules.yaml)
                           │
═══════════════════════════╪══════════════════════════════════════════════
                    RELEASE GATE
═══════════════════════════╪══════════════════════════════════════════════
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 Blocking missing     Non-blocking         Complete enough
 OR Critical block    missing fields       to score
 OR High / hard HITL       │                  │
        │                  ▼                  │
        │           MCP ELICITATION           │
        │           (Rules Engine             │
        │            ctx.elicit)              │
        │                  │                  │
        │           Streamlit form            │
        │           accept / decline /        │
        │           cancel                    │
        │                  │                  │
        ▼                  ▼                  ▼
 HITL Corrections     accept → continue    Risk tier:
 (Page 3)             decline/cancel          │
 st.data_editor       → escalate HITL         │
 fix + re-run                                 │
 Validation                                   │
        │                         ┌───────────┼───────────┐
        │                         │           │           │
        │                         ▼           ▼           ▼
        │                       LOW         MEDIUM       HIGH /
        │                    auto-approve   standard     blocked
        │                         │         HITL         │
        │                         │           │           │
        └──────────── only after human approve ───────────┘
                           │
                           ▼ (only if gate allows)
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
             5. DISCHARGE SUMMARY GENERATOR
                (Google ADK · A2A :8104 STREAMING)
                           │
           summary-generation-prompt (MCP Prompt)
                           │
        Streams section-by-section:
        patient → meds → labs → bill → instructions
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
                           ▼
             6. AGNO RAG Q&A SUBSYSTEM
                (Agno · A2A :8105 STREAMING)
                           │
         Five agents (not one script):
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Indexing     Retrieval    Augmentation
          (FAISS)      (top-k)      (keyword re-rank)
              │            │            │
              └────────────┼────────────┘
                           ▼
                      Generation
                 (rag-answer-prompt via MCP)
                           │
                           ▼
                      Reflection
                 (RAG Triad quality scores)
                           │
                           ▼
              Clinical Question Answering
              (or exact “I don’t know…” refusal)
                           │
───────────────────────────┼──────────────────────────────────────────────
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
   data/reports/                      data/vector_db/
   audit JSON/HTML/PDF                FAISS index
   pipeline.log                       data/rag_sessions/
         │                                   │
         └────────── LangFuse traces ────────┘
                     RAI guardrails
                     (PII / hallucination /
                      injection / toxicity /
                      HITL escalation)
```

---

## 4. Release Gate (detail)

**Chosen presentation:** all three validation checks run together in one Validation Agent step
(rules + EHR + risk), then Reporter, then Release Gate — this is the diagram above and is
fine for implementation.

**How that maps to FA5 (no contradiction):**

```text
Validation Agent (one step — three checks together)
        │
        ├─ rules.yaml / Rules Engine (completeness + cross-val rules)
        ├─ EHR Validation Tool → Mock EHR
        └─ Secondary MCP risk score (+ benchmarks / heatmap)
                │
                ▼
        Clinical Insight Reporter → Audit Report
                │
RELEASE GATE (routes outcomes)
        │
        ├─ Blocking missing field
        │  OR Critical cross-val fail
        │  OR High / hard HITL ──────────────► Mandatory HITL (Page 3) · no auto-summary
        │
        ├─ Non-blocking missing fields only ─► MCP Elicitation (Rules Engine ctx.elicit)
        │                                         one batched schema · Streamlit form
        │                                         accept  → continue / re-score path
        │                                         decline → escalate HITL
        │                                         cancel  → abort / escalate HITL
        │
        └─ Complete enough to score
                 ├─ Low  (≤ low_max) ─► Auto-approve → Summary
                 ├─ Medium             ► Standard HITL → Summary if approved
                 └─ High / hard HITL   ► Mandatory HITL → Summary only after approve
```

**Semantics to keep when implementing (do not invent from the diagram alone):**

- Elicitation is owned by the **Rules Engine Tool** (`ctx.elicit`) — the gate only *routes* to it for non-blocking gaps; blocking fields never elicit.
- One batched elicitation call per case (all non-blocking gaps in one schema), not per field.
- Critical Table 4 rules (`allergy_contradiction`, `discharge_approval`, `bill_settlement`, `follow_up_missing`) always force Mandatory HITL — `follow_up_missing` is absolute even though `rules.yaml` only weights it 2 (SSoT §16 row 12).
- Warning Table 4 rules only add risk-score weight; they do not block by themselves.
- Decline/cancel on elicitation always escalates to Mandatory HITL — never outweighed by a low score.

---

## 5. MCP Topology

### Primary — `:8200` `/clinicaltools`


| Kind        | Items                                                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tools       | Clinical Watcher · Clinical Data Harvester · Medical Lang Bridge · Clinical Rules Engine · EHR Validation · Clinical Insight Reporter                   |
| Resources   | clinical-rules/completeness · clinical-rules/cross-validation · discharge-report/{id} · lab-report/{id} · report-template/html · medical-abbreviations  |
| Prompts     | `discharge-extraction-prompt` · `ehr-cross-validation-prompt` · `abbreviation-normalization-prompt` · `summary-generation-prompt` · `rag-answer-prompt` |
| Sampling    | Lang Bridge ↔ Normalizer `sampling_callback`                                                                                                            |
| Elicitation | Rules Engine ↔ Streamlit `elicitation_callback`                                                                                                         |
| Roots       | Monitor registers Root; Watcher uses `list_roots` + path-traversal guards                                                                               |


### Secondary — `:8201` `/analyticstools`

- `calculate_risk_score`  
- `get_population_benchmarks`  
- `generate_risk_heatmap`

---

## 6. UI Responsibilities


| UI             | Port | Responsibility                                                                       |
| -------------- | ---- | ------------------------------------------------------------------------------------ |
| Gradio Host    | 8083 | Orchestrate A2A workflow; streaming views for Summary / ops                          |
| Streamlit HITL | 8501 | Document Viewer · Validation Report · HITL Corrections · RAG Q&A · Discharge Summary |


---

## 7. Repo Folders (quick map)

See SSoT §0.1 and the project tree:

- `agents/` — Monitor, Extractor, Normalizer, Validator, Summary  
- `rag/` — five Agno agents + A2A :8105  
- `mcp_servers/primary/` · `mcp_servers/secondary/`  
- `host/` · `dashboard/` · `mock_ehr/` · `configs/` · `data/`

---

## 8. Observability & Safety

- **LangFuse:** end-to-end trace ID per case; agent/tool/LLM/sampling/elicitation/guardrail/error spans.  
- **RAI:** PIIRedactor · HallucinationChecker · PromptInjectionGuard · ToxicityFilter · GuardrailManager.

---

*If this document and `REQUIREMENTS_REFERENCE.md` ever disagree, update both in the same change — SSoT wins on requirements; this file wins on the narrative workflow diagram.*