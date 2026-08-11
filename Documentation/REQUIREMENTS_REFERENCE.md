# Requirements Reference — Single Source of Truth (SSoT)

**Project:** Agentic AI System for Automated Discharge Summaries for Hospitals
**Capstone:** FA5_SP_Interns_Capstone_AI_Discharge_Summaries
**Last refactored:** 2026-08-04 · **Re-audited:** 2026-08-05 · **§12 expanded from `mock_ehr/seed.py` validation oracle:** 2026-08-05

## 0. How to Use This Document

- **Sources of truth, in priority order:** (1) `FA5_SP_Interns_Capstone_AI_Discharge_Summaries.docx`, (2) runtime `configs/rules.yaml` (seeded from `Documentation/configs/rules.yaml`), (3) runtime `mock_ehr/seed.py` (from `Documentation/mock_ehr/data.py` — validation test oracle, §12), (4) `Documentation/Data/incoming/` sample packets (synced to `data/input/`), (5) user-provided screenshots (logged in §19), (6) company coding-style refs in `Documentation/coding_style/` (§10.2).
- **Everything in this document is MUST** unless explicitly marked `OPTIONAL`, `PREFERRED`, or `NOT SPECIFIED`. Implementation must follow it strictly — do not invent requirements, do not silently drop a documented detail.
- **One concept, one place.** Each table/contract is defined exactly once and cross-referenced elsewhere (e.g. "see §3.6") instead of being repeated.
- **Conflicts** between FA5 and `rules.yaml`/samples are never silently resolved — they are all consolidated in §16 with a stated stance.
- **Company dependency pins** (§10.1) are **PREFERRED**, not FA5-mandatory — use them when possible; deviate only with a recorded reason.
- **Coding style** (§10.2): before implementing any feature, verify alignment with `langgraph.txt`, `rag.txt`, and `MCP_A2A.txt`. If LangGraph patterns conflict with MCP/A2A design, **MCP/A2A wins**.
- **Project layout** (§0.1) must stay in sync with the repo folders — rename code or update §0.1 in the same change.
- This file is updated after every new screenshot/requirement clarification; §19 logs what has been reviewed.

### 0.1 Project Layout (repo folders ↔ §2 services)

Runtime code lives at **repo root**. `Documentation/` is specs/seeds/coding-style only.

| SSoT §2 Component | Port | Folder |
| --- | --- | --- |
| Discharge Monitor Agent (Google ADK) | 8103 | `agents/monitor/` |
| Clinical Extractor Agent (LangGraph) | 8100 | `agents/extractor/` |
| Clinical Normalizer Agent (LangGraph) | 8102 | `agents/normalizer/` — owns `sampling_callback.py` |
| Clinical Validation Agent (LangGraph) | 8101 | `agents/validator/` |
| Discharge Summary Generator (Google ADK, streaming) | 8104 | `agents/summary/` |
| Clinical RAG Q&A (5 Agno agents, streaming) | 8105 | `rag/` (top-level, not under `agents/`) |
| Host Orchestrator (Google ADK + Gradio) | 8083 | `host/` |
| Streamlit HITL Dashboard (5 pages) | 8501 | `dashboard/` (+ `elicitation_callback.py`) |
| Primary MCP Clinical Tools | 8200 `/clinicaltools` | `mcp_servers/primary/` |
| Secondary MCP Analytics | 8201 `/analyticstools` | `mcp_servers/secondary/` |
| Mock EHR (FastAPI) | 8050 | `mock_ehr/` |

**Also:** `configs/` (runtime YAML/JSON) · `shared/` (settings, llm, guardrails, tracing) · `templates/discharge_summary.html` · `data/input/` (MCP Root) · `data/reports/` · `data/vector_db/` · `data/rag_sessions/` · `run.py` launcher.

**Workflow diagram (ASCII):** [`Documentation/architecture.md`](architecture.md) — finalized end-to-end architecture, release gate, and MCP topology.

**Must not:** put Sampling callback on Extractor; put Watcher logic inside Monitor (MCP tool only); call Mock EHR from Validator except via Primary EHR Validation Tool; nest RAG under `agents/`.

---

## 1. Project Intent & Objectives

**What it is:** An end-to-end Agentic AI system that ingests multi-format, multi-language hospital discharge documents (discharge reports, lab reports, bills), extracts and normalizes clinical data, validates it against a Mock EHR and configurable YAML rules, supports Human-in-the-Loop (HITL) review, answers clinical questions via Agentic RAG, and generates patient-friendly discharge summaries — all with full audit trails.

**Business context:** A global multi-specialty hospital network (**St. Marian Regional Medical Center**, per samples/rules) handles high discharge volume. Documents arrive as PDF, DOCX, scanned/handwritten, and structured EHR exports, in English, Hindi, Spanish, German (FA5 §1.2) — `rules.yaml` and the sample corpus additionally cover French and Dutch. Manual review is slow, error-prone, and senior-staff dependent; failures cause re-admissions, medication errors, missed follow-ups, and regulatory non-compliance.

**Twelve project objectives (all mandatory):**
1. Ingest discharge reports, lab reports, hospital bills — multi-format, multi-language.
2. Extract and translate into English using **MCP Sampling**.
3. Validate against **Mock EHR** + configurable **YAML rules**.
4. Collect missing fields via **MCP Elicitation** from human reviewers.
5. Index discharge documents into **FAISS** for RAG Q&A.
6. Generate structured validation reports (**JSON + HTML/PDF**) with full audit trails.
7. Stream patient-friendly discharge summaries via **A2A Streaming**.
8. Support HITL feedback, corrections, and re-run via a **Streamlit** dashboard.
9. Expose clinical tools through **two MCP servers**, demonstrating **all six MCP primitives**.
10. Orchestrate agents across **LangGraph, Google ADK, Agno** via the **A2A Protocol**.
11. Enforce RAI guardrails: PII redaction, hallucination check, prompt injection guard (+ toxicity filter, §8).
12. Provide real-time **LangFuse** tracing for every agent, tool call, LLM generation, and guardrail event.

---

## 2. System Components — Master Table

This is the **single canonical table** for every agent/service: framework, port, protocol, A2A mode, MCP primitives, and role. All other sections reference this table instead of repeating it.

| # | Component | Framework (fixed) | Port | Protocol | A2A Mode | MCP Primitives Used | Role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Discharge Monitor Agent | **Google ADK** | 8103 | A2A | Non-streaming | Tools + Roots | Monitor input folder via MCP Roots |
| 2 | Clinical Extractor Agent | **LangGraph** (StateGraph + MemorySaver) | 8100 | A2A | Non-streaming | Tools + Resources + Prompts | Extract structured data from docs |
| 3 | Clinical Normalizer Agent | **LangGraph** | 8102 | A2A | Non-streaming | Tools + Sampling + Prompts | Translate + normalize medical terms |
| 4 | Clinical Validation Agent | **LangGraph** | 8101 | A2A | Non-streaming | Tools + Elicitation + Resources | Completeness + EHR cross-validation |
| 5 | Discharge Summary Generator | **Google ADK** | 8104 | A2A | **Streaming** | Tools + Prompts | Generate patient-friendly summary |
| 6 | Clinical RAG Q&A Agent (5 internal Agno agents, §5.6) | **Agno** | 8105 | A2A | **Streaming** | MultiMCPTools + Prompts | 5-role RAG: Indexing, Retrieval, Augmentation, Generation, Reflection |
| 7 | Host Orchestrator | **Google ADK** | 8083 | Gradio + A2A client | Streaming-capable client | — | Coordinate all agents |
| 8 | Streamlit HITL Dashboard | **Streamlit** | 8501 | HTTP | — | — | 5-page human review interface (§7) |
| 9 | Primary MCP Clinical Tools Server | FastMCP | 8200 | MCP streamable-HTTP `/clinicaltools` | — | **All 6 primitives** | Watcher, Harvester, Lang Bridge, Rules Engine, EHR Validator, Reporter |
| 10 | Secondary MCP Analytics Server | FastMCP | 8201 | MCP streamable-HTTP `/analyticstools` | — | Tools only | `calculate_risk_score`, `get_population_benchmarks`, `generate_risk_heatmap` |
| 11 | Mock EHR System | FastAPI | 8050 | HTTP/REST | — | — | Patients, Meds, Allergies, Labs, Care Plans |

**MUST NOT:**
- Build Monitor / Summary Generator / Host Orchestrator in LangGraph.
- Build Extractor / Validator / Normalizer in ADK or Agno.
- Build any part of RAG (rows 6, all 5 sub-agents) outside Agno.
- Swap any port, framework, or streaming mode listed above.
- Confuse **Google ADK** (an agent-building framework, rows 1/5/7) with **A2A / `a2a-sdk`** (the inter-agent protocol used by *all* agents including LangGraph/Agno ones — see §4). ADK does not replace `a2a-sdk`.
- Confuse **FastAPI** (Mock EHR only, row 11) with the A2A agent transport layer.
- Replace **Streamlit**/**Gradio** with any other UI framework (e.g. Svelte — never mentioned in FA5).

---

## 3. MCP Layer (Model Context Protocol)

### 3.1 Dual-Server Topology

Agents MUST connect to **both** MCP servers simultaneously (rows 9–10 in §2). This is mandatory multi-server MCP connectivity, not optional.

### 3.2 Six Primitives — Coverage Matrix (all mandatory)

| Primitive | Where Implemented | Key APIs Used |
| --- | --- | --- |
| Tools | Primary MCP Server (8200) | `mcp.tool()` decorator, tool invocation |
| Resources | Primary MCP Server (8200) | `mcp.resource()`, `list_resources()`, `read_resource()` |
| Prompts | Primary MCP Server (8200) | `mcp.prompt()`, `list_prompts()`, `get_prompt()` |
| Sampling | Medical Lang Bridge Tool | `ctx.session.create_message()`, `sampling_callback`, `ModelPreferences` |
| Elicitation | Clinical Rules Engine Tool + HITL Dashboard | `ctx.elicit()`, `ElicitResult`, `elicitation_callback`, accept/decline/cancel |
| Roots | Discharge Monitor Agent ↔ Watcher Tool | `ctx.list_roots()`, `Root(uri=...)`, path-traversal prevention |

**MUST NOT** relocate Sampling/Elicitation/Roots away from the tools/agents above, or omit any primitive.

### 3.3 Resources (Primary Server) — exact URIs, MUST NOT rename

| Resource URI | Type | Content |
| --- | --- | --- |
| `resource://clinical-rules/completeness` | TextResource | Completeness rules from `rules.yaml` |
| `resource://clinical-rules/cross-validation` | TextResource | Cross-validation rules from `rules.yaml` |
| `resource://discharge-report/{patient_id}` | FileResource | Raw discharge document text |
| `resource://lab-report/{patient_id}` | FileResource | Raw lab report text |
| `resource://report-template/html` | FileResource | HTML discharge summary template |
| `resource://medical-abbreviations` | TextResource | Abbreviation expansion dictionary |

### 3.4 Prompts (Primary Server) — exact names/params, MUST NOT rename or hardcode

| Prompt Name | Parameters | Used By |
| --- | --- | --- |
| `discharge-extraction-prompt` | `language`, `doc_types` | Clinical Extractor Agent |
| `ehr-cross-validation-prompt` | `patient_id` | Clinical Validation Agent |
| `abbreviation-normalization-prompt` | `source_language` | Clinical Normalizer Agent |
| `summary-generation-prompt` | `risk_level`, `audience` | Discharge Summary Generator |
| `rag-answer-prompt` | `context_length` | Agno RAG Generation Agent |

All five agents above MUST fetch their prompt via MCP (`get_prompt`) — none may use a hardcoded prompt string.

### 3.5 Tools — exact names/purposes

| Tool Name | MCP Primitive | Purpose | Server |
| --- | --- | --- | --- |
| Clinical Watcher Tool | Tool + Roots | Detects new discharge files within Roots-scoped workspace | Primary :8200 |
| Clinical Data Harvester Tool | Tool | Extracts text, tables, images from clinical documents | Primary :8200 |
| Medical Lang Bridge Tool | Tool + Sampling | Translates/normalizes clinical language via LLM sampling | Primary :8200 |
| Clinical Rules Engine Tool | Tool + Elicitation | Validates completeness; elicits missing data from reviewer | Primary :8200 |
| EHR Validation Tool | Tool | Cross-checks discharge data against Mock EHR REST API | Primary :8200 |
| Clinical Insight Reporter Tool | Tool + Resources | Generates JSON and HTML audit/risk reports | Primary :8200 |
| Risk Score Tool | Tool | Computes composite discharge risk score | Secondary :8201 |
| Population Benchmarks Tool | Tool | Returns readmission rates and benchmarks | Secondary :8201 |
| `generate_risk_heatmap` | Tool | Risk heatmap | Secondary :8201 |

### 3.6 Sampling Contract (Medical Lang Bridge ↔ Clinical Normalizer) — verbatim, MUST follow exactly

- The **Medical Lang Bridge MCP Tool** issues a `ctx.session.create_message()` sampling request to the calling agent's LLM client, including the text to translate and **ModelPreferences** with model hints (`nova-lite` for multilingual, `command-r-plus` for English).
- The calling **LangGraph** agent implements a `sampling_callback` that reads the server's model hints, routes to the appropriate **LiteLLM** model, performs inference, and returns the translated text as `CreateMessageResult`.
- This separates **LLM resource management (client responsibility)** from **tool logic (server)** — the architectural intent of the Sampling primitive.

**MUST NOT:** run LLM inference inside the MCP tool server; skip the translation confidence score; ignore `ModelPreferences` hints; bypass Sampling with a direct/hardcoded LiteLLM call from the tool.

### 3.7 Elicitation Contract (Clinical Rules Engine ↔ HITL) — verbatim, MUST follow exactly

- When the **Rules Engine Tool** detects **non-blocking** missing fields, it calls `ctx.elicit()` **once** with a single **Pydantic-based schema** describing *all* the missing fields (and their types) for that case — FA5 describes one schema covering the set of gaps, not one elicitation per field.
- The tool handles all three outcomes of that one call: **accept** (use reviewer input for all supplied fields, continue validation normally), **decline** (mark the gaps unresolved, flag the case for HITL), **cancel** (abort the elicitation attempt and escalate).
- Both **decline** and **cancel** guarantee the case cannot auto-approve — it is routed to Mandatory HITL at the Release Gate (§6.3, §8) exactly like a blocking-field or Critical cross-validation failure; they are not merely extra risk-score weight.
- The HITL **Streamlit** dashboard implements the `elicitation_callback` — renders one dynamic form (all gaps at once) to the reviewer and returns a single `ElicitResult`.

**MUST NOT:** elicit on *blocking* fields (blocking fields stop auto-summary and go straight to HITL — elicitation is for non-blocking gaps only); issue a separate `ctx.elicit()` call per missing field; let a decline/cancel outcome be silently outweighed by an otherwise-low risk score.

### 3.8 Roots Contract (Discharge Monitor ↔ Clinical Watcher) — MUST follow exactly

- Agent registers the input folder as a Root URI when opening the MCP connection (FA5 example: `file:///data/input`).
- Clinical Watcher discovers folders **only** via `ctx.list_roots()` — raw filesystem paths must never be passed as tool parameters.
- Server enforces path-traversal prevention via `Path.relative_to()`; requests outside the declared root are rejected.

---

## 4. A2A Protocol

- Implemented via **`a2a-sdk`** (FA5 tech stack, Table 14) — this is the transport/discovery layer used by *every* agent regardless of build framework (LangGraph, ADK, or Agno).
- Every agent MUST expose an **AgentCard** at `GET /.well-known/agent.json`.
- Every A2A server MUST authenticate with shared-secret header **`X-Agent-Auth-Token`**.
- Push Notifications are required in the stack list (cover + Table 14) but their behavior is **NOT SPECIFIED** beyond the mention — must still be present, not omitted.

### Streaming vs. non-streaming — MUST match exactly

| Agent | Mode | Client Must Use | Progressive Output |
| --- | --- | --- | --- |
| Discharge Summary Generator (8104) | `streaming=True` | `send_message_streaming()` / `async for event in stream` | Section-by-section: **patient → meds → labs → bill → instructions** |
| Clinical RAG Q&A Agent (8105) | `streaming=True` | `send_message_streaming()` / `async for event in stream` | Token-by-token answer in HITL Q&A page |
| All other agents | `streaming=False` | `send_message()` / `await response` | Single final artifact |

**MUST NOT:** make 8104/8105 non-streaming; change the Summary section order; omit AgentCard or `X-Agent-Auth-Token`.

---

## 5. Agent Specifications

Each entry below states only what is *specific* to that agent; shared MCP contracts are cross-referenced to §3.

### 5.1 Discharge Monitor Agent (Google ADK · 8103 · non-streaming)
- Scans the incoming folder for discharge reports, lab reports, hospital bills.
- File-system simulation only — no live EHR feed required.
- MCP Roots mandatory — see §3.8 for the exact contract.

### 5.2 Clinical Extractor Agent (LangGraph — StateGraph + MemorySaver · 8100 · non-streaming)
- Extracts structured **and** unstructured clinical data from discharge reports, lab reports, medication lists, clinical notes, and hospital bills.
- Must support multiple languages and multi-modal content.
- Uses Primary MCP Resources + Prompts; its prompt is `discharge-extraction-prompt` (see §3.4).

### 5.3 Clinical Normalizer Agent (LangGraph · 8102 · non-streaming)
- **Primary languages** (same set as `mock_ehr/seed.py` comments + `rules.yaml` `language_codes_supported`): **en, es, hi, de, fr, nl**. These are the focus path (high-confidence translation expected).
- **Fallback:** if a new / unexpected language appears, still translate → English via multilingual Sampling (`nova-lite`). Do **not** reject the case; record a note and use lower confidence when unsure. Helpers live in `shared/language.py` (`PRIMARY_LANGUAGE_CODES`, `language_path`).
- Normalizes medical abbreviations (e.g. BID = twice daily, PO = by mouth; full map §6.2).
- Output **MUST include a translation confidence score**.
- Uses prompt `abbreviation-normalization-prompt` (see §3.4).
- **MCP Sampling is mandatory** — see §3.6 for the exact contract.

### 5.4 Clinical Validation Agent (LangGraph · 8101 · non-streaming)
- **Completeness validation**: checks discharge/lab/bill/prescription documents against the mandatory-field schema (§6.1, Table 3). Any **blocking** field missing → auto-summary generation is blocked and HITL must intervene, immediately, with **no elicitation attempt** for that field.
- **Cross-validation vs. Mock EHR / care plan / labs**: the 7 rules in §6.1 (Table 4), split into two enforcement styles:
  - **Critical → absolute block** (ignores risk score entirely): `allergy_contradiction_check`, `discharge_approval_check`, `bill_settlement_check`, and `follow_up_missing_check` (the last one is under-weighted in `rules.yaml` — see conflict §16 row 12 — implementation MUST still treat it as an absolute block per FA5).
  - **Warning → score-only** (does not by itself force HITL): `med_omission_check`, `diagnosis_mismatch_check`, `lab_follow_up_mismatch_check` — each only contributes its `rules.yaml` weight (§6.3) to the aggregate risk score; the resulting tier (Low/Medium/High) is what actually decides auto-approve vs. standard/mandatory HITL.
- Non-blocking completeness gaps trigger **MCP Elicitation** — see §3.7 for the exact contract. All non-blocking gaps for a case are batched into **one** `ctx.elicit()` call (one Pydantic schema, one `ElicitResult`) — not one round-trip per missing field.
- Completeness, EHR cross-validation, and risk scoring may run **together in one Validation Agent step** (the preferred architecture diagram shows all three side-by-side). They must not be short-circuited early — the Reporter (§5.5) always gets a complete picture.
- Rules are fetched at runtime via MCP Resources `resource://clinical-rules/completeness` and `resource://clinical-rules/cross-validation` (§3.3) — never hardcoded.

### 5.5 Audit & Risk Reporter (Clinical Insight Reporter Tool)
- Generates a clinician/admin-friendly discharge audit report. Runs **unconditionally** after completeness + cross-validation + risk scoring, regardless of whether the case ended up blocked/escalated — the Release Gate (§5.4, §6.3, §8) reads this report rather than re-deriving anything.
- Output formats: **JSON** (system) + **HTML/PDF** (clinician-friendly) — see conflict §16 row 6 re: `rules.yaml` formats.
- Report MUST include: (1) missing fields, (2) EHR discrepancies, (3) medication conflicts, (4) translation confidence, (5) risk level (Low/Medium/High), (6) recommendation (Approve/Edit/Reject — FA5 wording; see conflict §16 row 2), (7) audit trail with LangFuse trace IDs, (8) bill amount and payment status.
- Every report stamps **SHA-256 of `rules.yaml`** as `rules_version` (compliance reproducibility; see §6).
- Output directory: `data/reports` (per `rules.yaml`).

### 5.6 Agentic RAG — Clinical Q&A (Agno · A2A port 8105 · streaming)
- Framework for the **entire** RAG subsystem MUST be Agno — no LangGraph, no Google ADK.
- RAG is **multi-agent**: exactly five distinct Agno agents (not one agent performing five informal roles):

| # | Agent | Responsibility |
| --- | --- | --- |
| 1 | Indexing Agent | Parses and indexes discharge documents into the **FAISS** vector store |
| 2 | Retrieval Agent | Converts questions to embeddings; retrieves top-k chunks |
| 3 | Augmentation Agent | Re-ranks retrieved chunks by keyword relevance |
| 4 | Generation Agent | Generates grounded responses; prompt fetched via MCP (`rag-answer-prompt`, §3.4) |
| 5 | Reflection Agent | Scores quality via the **RAG Triad**: Faithfulness / Answer Relevance / Context Relevance |

- Out-of-context questions MUST get **exactly** this response: `I don't know — this information is not available in the patient records.`
- Agno-specific implementation: `agno.Agent` + `MultiMCPTools`, SQLite-backed session persistence (`SqliteDb`, **last 3 turns** as context), async `arun()` invocation.
- The five agents are together exposed as the Clinical RAG Q&A A2A service on port 8105 (streaming).

**MUST NOT:** collapse the five agents into one non-agent script; implement fewer than five; assign any of the five to a non-Agno framework; invent an answer when out of context; change the refusal string wording.

### 5.7 Discharge Summary Generator (Google ADK · 8104 · streaming)
- Streams the patient-friendly discharge summary in the fixed order defined in §4 (patient → meds → labs → bill → instructions).
- Uses prompt `summary-generation-prompt` (risk_level, audience) — §3.4.
- Only runs for cases allowed to proceed (not High risk, not `discharge_blocked`).

### 5.8 Host Orchestrator (Google ADK + Gradio · 8083)
- Gradio UI on :8083; A2A client, streaming-capable; coordinates all agents.

### 5.9 Mock EHR System (FastAPI · 8050)
- Domains: Patients, Meds, Allergies, Labs, Care Plans.
- FA5 specifies 5 JSON data files; the provided seed is Python dicts in `mock_ehr/seed.py` (plus a `GUIDELINES` dict that is not one of the five named files — see conflict §16 row 7). Inline comments in `seed.py` are the validation oracle — see §12.
- Exact REST route schemas: **NOT SPECIFIED** — implementer must design.

---

## 6. Validation & Risk Rules (`configs/rules.yaml` — canonical)

`rules.yaml` is the single source of truth for clinical validation and risk scoring at runtime, loaded by the Completeness Agent, EHR Validation Agent, and Reporting Agent. Every audit report stamps the file's SHA-256 hash as `rules_version`.

### 6.1 Mandatory Field Schema

**FA5 Table 3 — Completeness validation fields by document type**

| Document | Required Fields | Blocking If Missing |
| --- | --- | --- |
| Discharge Report | patient_id, patient_name, age, gender, address, admission_date, discharge_date, ward, bed_no, doctors, discharge_diagnosis, medications, adr_allergy_info, follow_up_appointments, discharge_instructions, discharge_approved_by, discharge_approved | patient_id, patient_name, discharge_diagnosis, discharge_approved, medications |
| Lab Report | patient_id, vendor_name, lab_name, report_date, tests | patient_id, tests |
| Bill | patient_id, hospital_name, billing_date, line_items, total_amount, payment_status | patient_id, total_amount, payment_status |
| Prescription (per med) | sl_no, medicine_name, strength, dosage, frequency, route, period, remarks, total_quantity | medicine_name, strength, frequency, route |

**`rules.yaml` mandatory field lists** (used at runtime by the Completeness Agent):
- `mandatory_clinical_fields`: patient_id, patient_name, age, gender, address, admission_date, discharge_date, ward, bed_no, **attending_physician, consulting_doctors**, discharge_diagnosis, medications, **allergies**, **follow_up_appointment**, discharge_instructions
- `mandatory_prescription_fields`: sl_no, medicine_name, strength, dosage, frequency, route, period, remarks, total_quantity

> Field-name drift between the two lists above (e.g. `doctors` vs `attending_physician`/`consulting_doctors`; `adr_allergy_info` vs `allergies`) is tracked as **conflict §16 row 1** — both sets of names must be represented in the internal schema, not silently merged.

**FA5 Table 4 — Cross-validation rules vs. Mock EHR / Care Plan / Labs**

| Rule ID | Severity | Check Description | Action |
| --- | --- | --- | --- |
| `med_omission_check` | Warning | Discharge meds differ from EHR medication history | Flag for review |
| `allergy_contradiction_check` | Critical | Prescribed med conflicts with known allergy | Block discharge |
| `diagnosis_mismatch_check` | Warning | Discharge diagnosis differs from EHR care plan | Flag for review |
| `follow_up_missing_check` | Critical | Follow-up not documented despite care plan requirement | Block discharge |
| `lab_follow_up_mismatch_check` | Warning | Abnormal lab values have no documented action | Flag for review |
| `discharge_approval_check` | Critical | Discharge not approved by treating physician | Block discharge |
| `bill_settlement_check` | Critical | Bill not PAID or lacking insurance guarantee letter | Block discharge |

**`rules.yaml` clinical validation policies** (additional, not in FA5 Table 4):
- `abnormal_lab_requires_followup: true`
- `allergy_must_not_match_prescription: true`
- `high_risk_meds_need_counseling`: Warfarin, Insulin, Methotrexate, Digoxin, Heparin
- Always HITL regardless of score: pediatric, obstetric, oncology service lines

> **Critical vs. Warning enforcement (§5.4):** `allergy_contradiction_check`, `discharge_approval_check`, `bill_settlement_check` are absolute blocks backed by a `rules.yaml` hard guardrail/business rule. `follow_up_missing_check` is also Critical/Block per FA5, but `rules.yaml` only weights it 2 points (`risk_scoring_matrix.weights.followup_missing`) — **conflict §16 row 12**, resolved in favor of FA5 (absolute block). The 3 Warning rules are pure score contributors with no override.

### 6.2 Normalization Standards

- **Abbreviation map** (expand all): HTN→Hypertension, T2DM/DM2→Type 2 Diabetes Mellitus, CHF→Congestive Heart Failure, COPD→Chronic Obstructive Pulmonary Disease, MI→Myocardial Infarction, CAD→Coronary Artery Disease, CKD→Chronic Kidney Disease, UTI→Urinary Tract Infection, PNA→Pneumonia, SOB→Shortness of Breath, BP→Blood Pressure, HR→Heart Rate, RR→Respiratory Rate, Temp→Temperature, Hx→History, Rx→Prescription, Dx→Diagnosis, Tx→Treatment, PRN→as needed, BID→twice daily, TID→three times daily, QID→four times daily, QD→once daily, QHS→at bedtime.
- **ICD-10 map**: Type 2 Diabetes Mellitus→E11.9, Hypertension→I10, CHF→I50.9, COPD→J44.9, MI→I21.9, Asthma→J45.909, Pneumonia→J18.9, Acute Bronchitis→J20.9, CAD→I25.10.
- **Languages supported** (`rules.yaml`): `en, es, hi, de, fr, nl`.

### 6.3 Risk Scoring Matrix & Business Rules

**Weights:**

| Finding | Weight |
| --- | --- |
| missing_mandatory_field | 3 |
| missing_address (soft) | 1 |
| missing_gender (soft) | 1 |
| incomplete_prescription_fields | 4 |
| medication_omission | 3 |
| medication_added | 4 |
| high_risk_med_missing_in_ehr | 9 (always escalates High) |
| allergy_contradiction | 8 (always escalates) |
| diagnosis_mismatch | 4 |
| followup_missing | 2 |
| abnormal_lab_unresolved | 3 |
| low_translation_confidence | 3 |
| high_risk_med_no_counseling | 4 |
| bill_unpaid_with_discharge_ok | 5 |

- **Thresholds:** `low_max = 2` → auto-approve; `medium_max = 8` → standard HITL; score > 8 → High / escalate.
- **Hard HITL guardrails** (always force human review regardless of score): allergy_contradiction, high_risk_med_missing_in_ehr, incomplete_prescription_fields, translation_confidence_below_threshold, rag_unsafe_response, service_line_pediatric, service_line_obstetric, service_line_oncology.
- **Business rules:** `bill_must_be_paid_before_release: true`, `discharge_ok_field_required: true`, `auto_approve_max_risk_score: 2`, `hitl_standard_max_risk_score: 8`.
- **SLAs:** auto_approve 60s · hitl_standard 14,400s (4h) · hitl_urgent 1,800s (30m).

### 6.4 Quality Thresholds

`translation_confidence_min: 0.70` · `rag_groundedness_min: 0.75` · `rag_relevance_min: 0.70` · `rag_safety_required: true`.

> `rag_groundedness_min` (0.75, here) vs the RAI Hallucination Check faithfulness trigger (0.7, §8) is tracked as **conflict §16 row 5**.

### 6.5 Reporting & Logging Config

- **Reporting:** output_dir `data/reports`; formats `[json, html]` (see conflict §16 row 6 re: FA5's PDF requirement); `include_audit_trail: true`; `include_tool_calls: true`.
- **Recommendation strings** (`rules.yaml` wording — see conflict §16 row 2 for FA5's alternate wording):
  - low → `"Approve — Auto-release"`
  - medium → `"Needs Review for any data entry mistakes — Standard HITL"`
  - high → `"Urgent Attention — Block release"`
- **Logging:** level `INFO`; `audit_trail: true`; `log_tool_calls: true`; log file `data/reports/pipeline.log`.

---

## 7. HITL Dashboard — Streamlit (5 Pages, :8501)

UI framework MUST be Streamlit only (not Gradio, not any other framework) for this dashboard.

| Page | Title | Key Features |
| --- | --- | --- |
| 1 | Document Viewer | Patient selector · Tab view (Discharge/Lab/Bill) · Language detection badge · Structured data preview · Process trigger button |
| 2 | Validation Report | Completeness score (colour-coded) · Cross-validation issues table · Risk level badge · Recommendation · Discharge blocked indicator · LangFuse trace link |
| 3 | HITL Corrections | Editable medication table (`st.data_editor`) · Elicitation Response Form (dynamic, schema-driven) · Risk label override · Approval decision · Save feedback · Re-run Validation (streaming) |
| 4 | RAG Q&A | Patient filter · Example query buttons · Prompt injection indicator · Streaming response display · Source docs panel · RAG Triad quality metrics |
| 5 | Discharge Summary | Patient-friendly summary for auto-approved cases · Plain-English prescription table · Colour-coded lab results · Export JSON / HTML / PDF · LangFuse trace link |

**MUST NOT:** omit any page or key feature; skip `st.data_editor` on page 3; skip LangFuse trace links on pages 2 and 5.

---

## 8. Responsible AI (RAI) Guardrails

| Guardrail | Module | Trigger Condition | Action |
| --- | --- | --- | --- |
| PII/PHI Redaction | PIIRedactor | Text containing patient name, phone, Aadhaar, PAN | Mask before logging/API calls |
| Hallucination Check | HallucinationChecker | RAG response faithfulness < 0.7 | Block response; request regeneration |
| Prompt Injection Guard | PromptInjectionGuard | Query matches injection patterns | Sanitize or reject; log alert |
| Toxicity Filter | ToxicityFilter | LLM output in clinical instructions | Filter before including in summary |
| HITL Escalation | GuardrailManager | `risk_level=High` OR `discharge_blocked=True` | Mandatory human review; no auto-approve |

(Faithfulness 0.7 here vs. `rag_groundedness_min: 0.75` in §6.4 — see conflict §16 row 5.)

---

## 9. LangFuse Observability

Required event coverage, mandatory across the whole system:
- End-to-end **trace ID** per discharge case, propagated through all agents via A2A message metadata.
- Per-agent spans: latency, input payload, output payload.
- Per-tool-call spans for every MCP tool invocation: tool name, parameters, result, duration.
- LLM generation events: model name, prompt, response, token counts, estimated cost.
- Sampling events: server model preferences, client model selected, translation result.
- Elicitation events: schema sent, reviewer response, action taken (accept/decline/cancel).
- Guardrail intervention spans: guardrail name, check result, content blocked/allowed.
- Error spans: exception type, stack trace, fallback action taken.

---

## 10. Technology Stack

| Category | Details |
| --- | --- |
| Backend & Frameworks | Python 3.11+ · LangGraph · Google ADK · Agno (bindings: §2) |
| Vector Database | FAISS (primary) · Qdrant / Weaviate (optional) |
| OCR / Document Parsing | Tesseract (optional) · text extraction from .txt / .pdf / .docx |
| LLM Models | AWS Bedrock Nova Lite (primary) · Cohere Command R+ (fallback) · `sentence-transformers/all-MiniLM-L6-v2` (embeddings) |
| LLM Gateway | LiteLLM — unified interface to AWS Bedrock + Cohere |
| MCP Protocol | Primary :8200 / Secondary :8201 (§3) · `mcp-use` multi-server client |
| A2A Protocol | `a2a-sdk` (§4) |
| Mock EHR System | FastAPI :8050 (§5.9) |
| Frontend / UI | Streamlit :8501 (§7) · Gradio :8083 (§5.8) |
| Observability | LangFuse (§9) |
| RAI Guardrails | PIIRedactor · HallucinationChecker (LLM-as-judge) · PromptInjectionGuard · ToxicityFilter (§8) |
| Configuration | `configs/rules.yaml` (§6) · `configs/prompts.yaml` · `configs/agent_config.yaml` |
| Deployment | NuvePro Lab |

> **NOT SPECIFIED / missing artifacts:** `configs/prompts.yaml` and `configs/agent_config.yaml` are named in the stack but not provided — bodies must be authored later without changing the prompt names/parameters already fixed in §3.4.

### 10.1 Company-Approved Dependency Pins — PREFERRED

Company / lab environment versions provided by the team. **Not FA5-mandated**, but **prefer these pins** during implementation so the project matches the corporate stack. Deviate only when a pin is incompatible with an FA5 MUST (framework identity, protocol APIs, etc.) and record the reason.

**Install style:** `uv add …` (project uses `uv`).

#### Pinned packages (authoritative company list)

| Package | Preferred version | Maps to FA5 role |
| --- | --- | --- |
| `agno` | **2.1.4** (also seen: 2.0.3 — prefer **2.1.4** from `uv add` list) | Agno RAG (5 agents) |
| `a2a-sdk` | **0.3.22** | A2A AgentCard + streaming/non-streaming |
| `google-adk` | **1.25.0** | Monitor, Summary Generator, Host Orchestrator |
| `litellm` | **1.80.7** | LLM gateway (Nova Lite / Command R+) |
| `gradio` | **6.5.1** | Host Orchestrator UI :8083 |
| `fastmcp` | **2.12.2** | Primary + Secondary MCP servers |
| `mcp` | **1.14.0** (also `uv add mcp` unpinned — prefer pin) | MCP protocol |
| `mcp-use` | **1.3.10** | Multi-server MCP client |
| `langgraph` | **0.6.7** | Extractor, Validator, Normalizer |
| `langchain` | **0.3.27** | LangChain ecosystem (with LangGraph) |
| `langchain-aws` | **0.2.18** | Bedrock / AWS LLM integration |
| `langchain-mcp-adapters` | **0.1.9** | LangGraph ↔ MCP tool bridging |
| `langchain-ollama` | **0.3.8** | Ollama adapter (lab/local) |
| `aiofiles` | **24.1.0** | Async file I/O |
| `httpx` | **0.28.1** | HTTP client |
| `numpy` | **2.3.3** | Numerics / FAISS adjunct |
| `pandas` | **2.3.2** | Tabular data |
| `ollama` | **0.5.3** | Local Ollama client |
| `pypdf2` | **3.0.1** | PDF text extraction |
| `starlette` | **0.47.3** | ASGI (MCP/HTTP stack) |
| `uvicorn` | **0.35.0** | ASGI server |
| `urllib3` | **2.5.0** | HTTP transport |
| `pip-system-certs` | **5.2** | System CA certs (esp. Windows/lab) |
| `python-certifi-win32` | **1.6.1** | Windows cert bundle |

#### Also `uv add` (version not pinned in the company list — add latest compatible unless a pin appears later)

`rich` · `cohere` · `google-search-results` · `langchain-classic` · `langchain-cohere` · `langchain-community` · `langchain-tavily` · `langgraph-prebuilt` · `openai` · `aioboto3`

#### Notes for implementation

- Prefer **`uv add`** over plain `pip` for dependency management.
- When the older lockfile (`agno==2.0.3`) and the `uv add` list (`agno==2.1.4`) disagree, **prefer the `uv add` pin (2.1.4)** unless lab images force 2.0.3.
- FA5 still requires packages not listed above (e.g. **Streamlit**, **FAISS**, **LangFuse**, **sentence-transformers**, **FastAPI** for Mock EHR) — add those as needed; company list does not replace FA5 stack completeness.
- Windows/lab cert packages (`pip-system-certs`, `python-certifi-win32`) are environment helpers, not architecture components.
- **Phase 3 pin deviation (recorded):** `google-adk==1.25.0` (FA5 MUST framework) requires `mcp>=1.23.0` and `starlette>=0.49.1`. Company pins `mcp==1.14.0` and `starlette==0.47.3` are therefore **relaxed** for ADK compatibility (`mcp>=1.23.0,<2.0.0`, `starlette>=0.49.1,<1.0.0`). `fastmcp==2.12.2` still accepts this mcp range. Prefer company pins again only if a future ADK release re-aligns.

### 10.2 Coding Style & Development Guidelines — MUST FOLLOW

**Location:** `Documentation/coding_style/`
| File | Covers |
| --- | --- |
| `langgraph.txt` | LangGraph graphs, TypedDict state, nodes, conditional edges, checkpointers, HITL `interrupt` |
| `rag.txt` | Document loaders, text splitters, FAISS, embeddings, retrieve→generate graphs |
| `MCP_A2A.txt` | FastMCP servers, Resources/Tools/Prompts/Sampling/Elicitation, Agno + MultiMCPTools, A2A AgentCard/`a2a-sdk`, LangGraph↔MCP adapters |

These files are the **company coding SSoT** for style, structure, naming, and patterns. Treat them as authoritative for *how* to write code. FA5 (§1–§9) remains authoritative for *what* to build (ports, agents, contracts).

#### Priority rules (when approaches conflict)

1. **MCP / A2A design wins over LangGraph-local design.** Shared tools live on the MCP server — never re-implement the same tool inside each agent.
2. **LangGraph reference is the baseline style** for graph/state/node code. Implement **Google ADK** and **Agno** with the same philosophy: simple, explicit, readable, little abstraction.
3. Do **not** invent architectures, layers, or patterns beyond what the three reference files demonstrate, unless FA5 makes it unavoidable.
4. Keep code **beginner-friendly** (or only slightly above): readability and maintainability over cleverness.
5. Before implementing any feature: re-check the matching reference snippet; if multiple options exist, pick the one closest to the references.

#### Patterns to mirror (extracted from the refs)

**LangGraph (`langgraph.txt`):**
- `TypedDict` state (often with `Annotated[..., operator.add]` for message lists).
- Plain functions as nodes that take `state` and return a partial state dict.
- `StateGraph` → `add_node` → `add_edge` / `add_conditional_edges` → `compile(checkpointer=…)`.
- Company examples use `InMemorySaver` (FA5 names `MemorySaver` — use the company checkpointer class available in pinned LangGraph; same role).
- HITL via `interrupt({...})` + `Command(resume=...)` where appropriate; simple `input()` HITL demos in refs are style examples — production HITL for this project is Streamlit (§7) + MCP Elicitation (§3.7).
- LLM via `ChatBedrockConverse` / structured output (`with_structured_output`) when scoring; `rich` for console prints.
- Routing functions return string keys mapped in a dict — keep that explicit style.

**RAG (`rag.txt`):**
- Loaders: `PyPDFLoader`, `TextLoader`, JSON → `Document(page_content=…, metadata=…)`.
- Splitters: `RecursiveCharacterTextSplitter` with clear `chunk_size` / `chunk_overlap` / `separators`.
- Vector store: **FAISS** (`FAISS.from_documents`); embeddings include `SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")` (matches FA5) and Bedrock embeddings in some demos — **prefer FA5 embedding model** for this project.
- Retrieve as an MCP/tool-friendly function when possible; generation grounded on retrieved context; refuse/out-of-context behavior still follows FA5 exact string (§5.6).
- Simple LangGraph RAG loop: assistant → tools → generate, with `ToolNode` and a `should_continue` router.

**MCP + A2A (`MCP_A2A.txt`):**
- Servers: `FastMCP(name=…, port=…, streamable_http_path=…, host=…)` + `mcp.run(transport="streamable-http")`.
- Decorators: `@mcp.resource`, `@mcp.tool`, `@mcp.prompt` with explicit `name` / `title` / `description` (and tool `annotations` where shown).
- Resources via `TextResource` / `FileResource` / direct async resource functions; use `aiofiles` for async file reads.
- Sampling: tool receives `ctx: Context`, calls sampling (`ctx.sample` / `create_message` per FA5 contract §3.6); client supplies `sampling_callback` on `ClientSession`.
- Elicitation: client-side `on_elicitation` / `Callbacks(on_elicitation=…)` returning `ElicitResult(action="accept"|"decline"|"cancel", …)` — Streamlit implements the UI form for this project.
- Multi-server client: JSON config of server URLs + `MultiServerMCPClient` / `mcp-use`; Agno uses `MultiMCPTools(urls=…, urls_transports=['streamable-http', …])` → `await connect()` → `Agent(..., tools=[multi_mcp_tools], db=SqliteDb(...), num_history_runs=3)` → `await agent.arun(...)`.
- A2A: `AgentCard` + skills + `A2AStarletteApplication` / `DefaultRequestHandler` + `AgentExecutor.execute(...)` via **`a2a-sdk`**; client uses `send_message` / streaming equivalents; uvicorn hosts the A2A app.
- LangGraph agents load MCP tools via `langchain-mcp-adapters` (`load_mcp_tools`) rather than duplicating tool logic.

**Google ADK / Agno (no dedicated ADK sample file):**
- Mirror the same simplicity: thin agent wrappers, tools from MCP, A2A executor shell around the agent — do not invent a parallel framework abstraction layer.

#### Explicit anti-patterns (do not do)

- Shared clinical tools implemented only inside one LangGraph node instead of on Primary/Secondary MCP.
- Heavy OOP frameworks, deep inheritance, or “enterprise” service layers not shown in the refs.
- Hardcoded prompts/resources that FA5 requires to come from MCP (§3.3–§3.4).
- Replacing Streamlit HITL or Gradio Host with another UI stack.
- Copying demo ports/paths from the coding_style snippets (`8007`, `mcpserver`, movie/stock examples) — those are style only; **this project's ports/paths are §2 / §12**.

#### Notes confirmed during the 2026-08-05 line-by-line re-audit

- **A2A server wrapper depends on `a2a-sdk` major version.** `MCP_A2A.txt` shows two patterns: `A2AStarletteApplication` (for `a2a-sdk<1.0.0`) vs. route-factory functions `create_agent_card_routes`/`create_jsonrpc_routes`/`create_rest_routes` (mandatory once the wrapper classes were removed in `a2a-sdk>=1.0.0`). The **company pin is `a2a-sdk==0.3.22`** (§10.1) — use the **`A2AStarletteApplication` + `DefaultRequestHandler` + `AgentExecutor`** pattern, not the v1.0+ route-factory style.
- **Push Notifications now have a concrete pattern to mirror** (resolves part of conflict §16 row 9 — FA5 never specifies *behavior*, but the company reference shows *how*): `MCP_A2A.txt` demonstrates `BasePushNotificationSender` + `InMemoryPushNotificationConfigStore` wired into `DefaultRequestHandler`. Use this scaffold; the actual trigger condition/payload for this project is still an implementer decision (not specified by FA5).
- **No company reference exists for the RAG Triad / Reflection Agent.** Neither `rag.txt` nor `MCP_A2A.txt` shows a faithfulness/relevance scoring pattern — the Reflection Agent (§5.6, Agno agent 5) must be designed from scratch as an LLM-as-judge, consistent in spirit with `HallucinationChecker` (§8). This is the one place in the RAG/MCP/A2A pipeline with zero style precedent to copy.

---

## 11. System Architecture

**Layered flow:** Users → Host Orchestrator → A2A Agents → Dual MCP Servers + Mock EHR → Data/Storage. Inter-layer protocol on the diagram is labelled **A2A / MCP / HTTP**.

| Layer | Contents |
| --- | --- |
| User | Hospital Admin/Clinician via Streamlit HITL Dashboard :8501 |
| Orchestrator | Host Orchestrator (Google ADK), Gradio UI :8083, A2A client |
| A2A Agents | LangGraph: Extractor :8100 · Validator :8101 · Normalizer :8102 — ADK: Monitor :8103 · Summary Generator :8104 [STREAMING] — Agno RAG Q&A Agent :8105 [STREAMING] |
| MCP + EHR | Primary MCP :8200 · Secondary MCP :8201 · Mock EHR (FastAPI) :8050 |
| Data/Storage | FAISS `data/vector_db/` · Input Docs (MCP Roots) `data/input/P001/` · LangFuse |

**Colour legend:** Navy/Blue = LangGraph Agents · Orange = Google ADK Agents + Host · Purple = Agno RAG Q&A Agent · Green = MCP Servers · Light Grey = Data/Storage Layer.

Ports/frameworks/roles for each box are defined once in §2 — this section only describes the visual layering and colour coding.

---

## 12. Data, Paths & Sample Corpus

**Documented paths (FA5):** input example `data/input/P001/`, `P002/`; Roots example `file:///data/input`; FAISS `data/vector_db/`; reports `data/reports` (+ `pipeline.log`).

**Actual provided corpus:** `Documentation/Data/incoming/{doctor_reports,lab_reports,bills}/` (synced to `data/input/`), covering patients **P1019–P1024** only.
- Naming: doctor `P{id}_{firstname}_{lastname}.{ext}`; labs `P{id}_labs.{ext}`; bills `P{id}_bill.{ext}`; OCR sidecar `{binary}.{ext}.ocr.txt` (often present for doctor/lab binaries; bill binaries often lack OCR and use JSON companions instead).
- Path/ID conflict with FA5 examples — see conflict §16 row 4; prefer aligning MCP Roots to the actual incoming folder unless told otherwise.

**Runtime Mock EHR seed:** [`mock_ehr/seed.py`](../mock_ehr/seed.py) (promoted from `Documentation/mock_ehr/data.py`). Dicts: `PATIENTS`, `ALLERGIES`, `MED_ORDERS`, `LABS`, `CARE_PLANS`, plus unused-by-routes `GUIDELINES`. Comments in that file are the **validation test oracle** — preserve planted mismatches; do not "fix" them when implementing Rules Engine / EHR Validation / risk scoring.

### 12.1 Expected outcomes — patients with sample files (P1019–P1024)

| Patient | Profile | Seed / intake drivers | Expected Outcome |
| --- | --- | --- | --- |
| P1019 | EN text; fully reconciled; paid; complete | Meds match; allergies empty; abnormal labs have `action_in_ehr`; care plan Endocrinology 30d (documented in discharge) | Low risk, **auto-approve**, no HITL |
| P1020 | ES PDF; reconciled; paid | **Only address missing** (soft weight 1); Spanish med spellings in EHR (`Metformina`/`Atorvastatina`/`Aspirina`) must canonicalize to match discharge | Low risk, **auto-approve**, no HITL |
| P1021 | HI JSON; clinically OK | Bill **UNPAID**; **address + follow-up missing** in discharge (care plan still requires Endocrinology 30d → `followup_missing`); Penicillin on file but discharge does **not** prescribe conflicting med; low Hindi translation confidence | **HITL** (financial + data-entry + translation) |
| P1022 | NL PNG | **HARD allergy:** Penicillin on file vs discharge **Amoxicilline** (canonicalize Amoxicilline→Amoxicillin); missing age + doctor details; low NL confidence; follow-up **is** documented (no followup_missing); CRP/Leukocytes `abnormal: False` | **HARD HITL** — allergy + High tier |
| P1023 | EN handwritten PNG | Fully reconciled; paid; labs normal (`abnormal: False`) | Low risk, **auto-approve**, no HITL |
| P1024 | NL TXT | Same allergy pattern as P1022 (Penicillin vs Amoxicilline); missing age + attending/consulting; low NL confidence; follow-up documented; CRP 38 in **source** marked NORMAAL but ref `<5` — EHR has `abnormal: False` (must honor EHR, not "fix" from ref range) | **HARD HITL** — allergy + High tier |

### 12.2 Seed-only intended mismatches (P1001–P1018 — no incoming files yet)

These live in `mock_ehr/seed.py` for future cases / unit tests of the EHR Validation Tool. **No sample packets** in `data/input/` today (§16 row 10). When building validation, implement the checks so these oracles would pass if files were added.

| Patient | Intended validation driver(s) from seed comments |
| --- | --- |
| P1003 | Discharge **adds Warfarin** not in EHR → `medication_added` + `high_risk_med_missing_in_ehr` (**HARD HITL**) |
| P1004 | Penicillin (+ Latex) on file; discharge Amoxicillin-Clavulanate → **allergy contradiction HARD HITL**; inpatient was Levofloxacin switched to Amox-Clav |
| P1007 | EHR has **Lisinopril** but discharge omits it → `medication_omission`; BNP 845 `abnormal: True` with **empty** `action_in_ehr` → `abnormal_lab_unresolved` |
| P1013 | Clinically clean; bill **UNPAID** → financial HITL only |
| P1014 | EHR has Loperamide + Hyoscine; discharge omits both → `medication_omission` ×2 (Medium HITL) |
| P1015 | Meds reconcile; **low translation confidence** (Hindi) is the HITL driver |
| P1016 | Penicillin on file; German discharge **Amoxicillin** → allergy HARD HITL; meds otherwise reconcile; low DE translation confidence |
| P1017 | EHR has Nitrofurantoin; discharge omits it → `medication_omission`; low FR translation confidence |
| P1011 / P1012 / P1018 | Clean / auto-approve-oriented seed profiles (no planted contradiction) |
| P1001–P1002, P1005–P1006, P1008–P1010 | Baseline EHR rows with labs/care plans; use for general reconciliation tests |

### 12.3 Validation implementation notes taken from seed (MUST honor)

1. **Allergy matching is canonical, not string-equal.** Treat Amoxicillin / Amoxicilline / Amoxicillin-Clavulanate as conflicting with documented **Penicillin** allergy (P1004, P1016, P1022, P1024).
2. **Med reconciliation is canonical.** Spanish EHR spellings (P1020: Metformina, Atorvastatina, Aspirina) and NL/EN pairs (Amoxicilline→Amoxicillin, Paracetamol→acetaminophen) must match after normalization — otherwise false `medication_omission` / `medication_added`.
3. **Lab unresolved check uses EHR `abnormal` + `action_in_ehr`, not raw source ref ranges.** If `abnormal: True` and `action_in_ehr` is empty → `abnormal_lab_unresolved` (e.g. P1007 BNP). If `abnormal: False`, do **not** flag even if the intake PDF/TXT looks odd (P1022/P1024 CRP trap).
4. **`follow_up_missing_check` uses `CARE_PLANS`**, not `GUIDELINES`. Compare discharge follow-up text against `followup_required` / `speciality` / `window_days`. P1021 care plan requires Endocrinology but discharge omits follow-up → missing. P1022/P1024 document follow-up → no followup_missing from care plan.
5. **`GUIDELINES`** (ICD → required_followup / essential_meds) is supplementary only — not wired to FA5 Table 4. Do not build Table 4 logic on `GUIDELINES` unless explicitly extending scope.
6. **Bills are not in the Mock EHR seed.** Payment status comes from intake bill documents. Unpaid bill HITL (P1021, and seed-note P1013) is `bill_settlement_check` / `bill_unpaid_with_discharge_ok` against extracted bill data, not an EHR field.
7. **High-risk med added only on discharge** (P1003 Warfarin): fire `high_risk_med_missing_in_ehr` (weight 9, hard HITL) — EHR has no Warfarin order.
8. Do **not** silently correct planted traps when harvesting/extracting; validation must surface them.

**Planted data-quality traps (summary):**
- P1024 labs source: CRP 38 marked NORMAAL vs ref `<5`; EHR `abnormal: False` wins.
- Allergy spelling variants (Amoxicillin / Amoxicilline).
- P1001–P1018: seed mismatches with no corpus files yet.

---

## 13. End-to-End Workflow (Conceptual)

1. Files land under the incoming folders (doctor / lab / bill).
2. Monitor discovers them via the Roots-scoped Watcher (§3.8).
3. Harvester extracts text/tables/images (OCR optional; sidecars preferred when present).
4. Extractor structures clinical fields using MCP prompts/resources (§5.2).
5. Normalizer translates and expands abbreviations via Sampling, emitting a confidence score (§5.3).
6. Validator runs Rules Engine completeness (+ elicit if needed) and EHR cross-validation; Secondary MCP may contribute a risk score (§5.4, §6).
7. Reporter emits the JSON + HTML audit/risk report with a recommendation (§5.5).
8. Gate: blocked or High risk → mandatory HITL; Low risk may auto-approve per §6.3.
9. When allowed, Summary Generator streams patient → meds → labs → bill → instructions (§5.7).
10. RAG indexes the chart into FAISS; admins ask grounded questions or receive the exact "I don't know…" refusal (§5.6).
11. Every step is traced in LangFuse (§9); RAI guardrails intervene as configured (§8).

---

## 14. Non-Functional Requirements & Constraints

| Area | Stated | Gap |
| --- | --- | --- |
| Security | A2A `X-Agent-Auth-Token`; Roots path-traversal prevention | Broader auth/encryption **NOT SPECIFIED** |
| Privacy | PII/PHI redaction (name, phone, Aadhaar, PAN) | Full PHI inventory/retention **NOT SPECIFIED** |
| Performance | SLAs in `rules.yaml` (§6.3); streaming UI | Broader LLM latency SLOs **NOT SPECIFIED** |
| Compliance | Audit trails, `rules_version` SHA-256 | Specific regulation (e.g. HIPAA) **NOT SPECIFIED** |
| Deployment | NuvePro Lab | — |
| HITL feedback persistence | "Save feedback" UI feature | Storage mechanism **NOT SPECIFIED** |

---

## 15. Explicit Non-Goals

- No live hospital EHR integration — Mock EHR only.
- File-system simulation is sufficient for document intake.
- Never hardcode the RAG generation prompt (must come from MCP).
- Never pass raw filesystem paths as Watcher tool parameters (must use Roots).
- Never auto-approve when risk is High or `discharge_blocked` is true.
- Never invent an answer to an out-of-context RAG question.

---

## 16. Known Conflicts & Ambiguities (master list)

Every FA5-vs-`rules.yaml`/sample discrepancy found so far, consolidated here. None have been silently resolved — implementation must represent both sides or make an explicit, recorded choice at design time.

| # | Topic | FA5 says | Other source says | Where detailed |
| --- | --- | --- | --- | --- |
| 1 | Field naming | Table 3: `doctors`, `adr_allergy_info`, `follow_up_appointments`, `discharge_approved*` | `rules.yaml`: `attending_physician`, `consulting_doctors`, `allergies`, `follow_up_appointment` | §6.1 |
| 2 | Recommendation wording | Approve / Edit / Reject | `rules.yaml`: "Approve — Auto-release" / "...Standard HITL" / "...Block release" | §5.5, §6.5 |
| 3 | Language list | EN / HI / ES / DE (§1.2 overview) | `rules.yaml` + samples add FR / NL | §1, §6.2 |
| 4 | Input path layout | Diagram: `data/input/P001/` | Actual corpus: `Documentation/Data/incoming/`, patients P1019–P1024 | §12 |
| 5 | Faithfulness/groundedness threshold | RAI Table 12: faithfulness < 0.7 | `rules.yaml`: `rag_groundedness_min: 0.75` | §8, §6.4 |
| 6 | Report format | FA5 requires PDF | `rules.yaml` `formats: [json, html]` only | §5.5, §6.5 |
| 7 | Mock EHR data shape | FA5: 5 JSON data files | `mock_ehr/seed.py`: Python dicts + extra `GUIDELINES` dict; REST schemas implementer-designed (Phase 1 routes) | §5.9, §12 |
| 8 | Missing config bodies | `prompts.yaml` / `agent_config.yaml` named in stack | Neither file's contents provided | §10 |
| 9 | A2A Push Notifications | Required in stack/cover | Behavior **NOT SPECIFIED** | §4 |
| 10 | P1001–P1018 scope | Exist in Mock EHR seed with intended mismatches | No incoming sample files provided for them | §12 |
| 11 | Secondary MCP tool count | Table 7 ("Agent Tools") lists only **2** Secondary tools (Risk Score, Population Benchmarks) | Table 8 / Table 15 list **3** (adds `generate_risk_heatmap`) | §3.5 — SSoT already lists all 3; this row just records that the FA5 doc is internally inconsistent between its own tables |
| 12 | `follow_up_missing_check` enforcement | Table 4: **Critical → Block discharge** (absolute, like `allergy_contradiction_check`) | `rules.yaml` only has `risk_scoring_matrix.weights.followup_missing: 2` — a soft score contributor, **not** a hard block or guardrail | §5.4, §6.1, §6.3 — **resolved: FA5 wins** (source-priority order, §0). Implementation MUST treat a failed `follow_up_missing_check` as an absolute `blocked`/Mandatory-HITL condition, the same as the other 3 Critical rules — it must NOT be left as just a 2-point score weight, or a low-risk case with a missing follow-up could wrongly auto-approve. |

---

## 17. Deliverables Checklist

- [x] Three frameworks (LangGraph, ADK, Agno) coordinated by Host Orchestrator
- [x] Dual MCP servers; all 6 primitives demonstrable
- [x] A2A streaming + non-streaming + shared-secret auth
- [x] Full pipeline: monitor → extract → normalize → validate → report → summary
- [x] Streamlit HITL, 5 pages, with elicitation + re-run
- [x] Agentic RAG with FAISS + RAG Triad reflection + exact refusal string
- [x] RAI guardrails + LangFuse observability
- [x] Mock EHR FastAPI built from the provided seed
- [x] Config-driven validation via `rules.yaml`
- [ ] Deployable on NuvePro Lab

---

## 18. Quick-Reference Gotchas (do not forget)

- Sampling separates LLM ownership (client) from tool logic (server) — never collapse this (§3.6).
- Elicitation is only for non-blocking gaps; blocking fields always stop auto-summary (§3.7).
- The RAG refusal string must match **exactly**; the RAG prompt must always come via MCP, never hardcoded (§5.6).
- Agno RAG session memory = last 3 turns only (§5.6).
- Summary streaming section order is fixed: patient → meds → labs → bill → instructions (§4).
- Trace ID must propagate through all agents via A2A message metadata (§9).
- `rules_version` = SHA-256 of `rules.yaml`, stamped on every audit report (§5.5, §6).
- P1022 and P1024 are the deliberate hard-HITL allergy cases (Penicillin vs. Amoxicilline).
- P1020's missing address is an intentionally soft gap (weight 1) — it still auto-approves.
- P1021 combines an unpaid bill with a null address/follow-up and Hindi source text.
- Bill source binaries often lack an `.ocr.txt` sidecar; prefer the JSON companion file when present.
- `follow_up_missing_check` MUST be coded as an absolute block (like the other 3 Critical Table 4 rules), even though `rules.yaml` only gives it a 2-point score weight — do not trust the weight alone (§16 row 12).
- Elicitation is exactly **one** batched `ctx.elicit()` call per case covering all non-blocking gaps — never one call per field; decline/cancel on that one call forces Mandatory HITL, it never gets averaged away by a low risk score.
- Before implementing EHR Validation / Rules Engine: re-read **§12.1–§12.3** (`mock_ehr/seed.py` oracle) — allergy/med canonicalization, `abnormal`+`action_in_ehr` for labs, `CARE_PLANS` for follow-up, bills from intake not EHR.

---

## 19. Image Review Log

All screenshots reviewed so far were **visual excerpts of the FA5 document itself** (cover, §§1–10, Tables 1–15, Figure 1). Every one of them matched the FA5 text already captured above — **none introduced a new or modified requirement.** Their content has been merged into the numbered sections of this reference (not kept as separate per-image notes) to avoid duplication.

| # | Topic Confirmed | Section Now Living In |
| --- | --- | --- |
| 1 | Cover / tech pillars (frameworks, 6 MCP primitives, A2A modes, observability) | §1, §2, §3, §4, §10 |
| 2 | §1 Project Overview (description, business context, 12 objectives) | §1 |
| 3 | §2.1 Discharge Monitor + mandatory MCP Roots | §5.1, §3.8 |
| 4 | §2.2 Clinical Extractor + Tables 1–2 (Resources, Prompts) | §5.2, §3.3, §3.4 |
| 5 | §2.3 Clinical Normalizer + MCP Sampling contract | §5.3, §3.6 |
| 6 | §2.4.1 Completeness + MCP Elicitation contract + Table 3 | §5.4, §3.7, §6.1 |
| 7 | §2.4.2 Cross-validation Table 4 | §6.1 |
| 8 | §2.5 Audit & Risk Report Generation | §5.5 |
| 9 | §2.6 Agentic RAG + Table 5 (five Agno agents) | §5.6 |
| 10 | §3 Tables 6–7 (agent roster, agent tools) | §2, §3.5 |
| 11 | §4 Tables 8–9 (dual MCP servers, six primitives APIs) | §3.1, §3.2 |
| 12 | §5 Table 10 (A2A streaming contracts) | §4 |
| 13 | §6 Architecture diagram + Table 11 (colour legend) | §11 |
| 14 | §7 Table 12 (RAI guardrails) + §7.2 (LangFuse events) | §8, §9 |
| 15 | §8 Table 13 (HITL 5-page dashboard) | §7 |
| 16 | §9–10 Tables 14–15 (tech stack, port map) | §10, §2 |

**Clarified along the way (not new requirements, just settled naming):** A2A discovery/transport = `a2a-sdk`; Google ADK is a separate agent-building framework used for Monitor/Summary/Host; FastAPI is scoped to Mock EHR only; the HITL/orchestrator UI is Streamlit + Gradio (never Svelte).

---

*End of Requirements Reference. Implementation must not begin until all documentation and screenshots are confirmed reviewed and any open items in §16 have an explicit resolution.*
