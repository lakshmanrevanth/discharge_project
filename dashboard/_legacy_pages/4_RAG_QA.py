"""Page 4 — RAG Q&A (SSoT §7)."""

from __future__ import annotations

import asyncio

import streamlit as st

from dashboard.components.ui import page_header, require_patient

pid = require_patient()
page_header("RAG Q&A", "Ask grounded questions about this patient's discharge chart.")

if not pid:
    st.stop()

EXAMPLES = [
    "What medications were prescribed at discharge?",
    "What is the discharge diagnosis?",
    "Is the hospital bill paid?",
    "What follow-up is recommended?",
]

st.markdown("#### Example queries")
cols = st.columns(len(EXAMPLES))
for i, example in enumerate(EXAMPLES):
    if cols[i].button(example, key=f"ex_{i}"):
        st.session_state["rag_question"] = example

question = st.text_input(
    "Your question",
    value=st.session_state.get("rag_question", ""),
    placeholder="Ask about medications, labs, bill, follow-up…",
)

if st.button("Ask", type="primary") and question.strip():
    with st.spinner("Indexing / retrieving / generating…"):
        try:
            from rag.pipeline import ask

            result = asyncio.run(ask(pid, question.strip()))
            st.session_state["last_rag"] = result
        except Exception as exc:
            st.error(f"RAG failed: {exc}")
            st.info("Ensure Primary MCP is running if Generation needs rag-answer-prompt.")
            st.stop()

result = st.session_state.get("last_rag")
if not result:
    st.caption("Ask a question to see the answer, sources, and RAG Triad metrics.")
    st.stop()

# Prompt injection indicator
notes = result.get("notes") or []
injected = any("prompt_injection" in str(n) for n in notes) or (
    result.get("refused") and "injection" in (result.get("answer") or "").lower()
)
if injected:
    st.markdown('<span class="badge bad">Prompt injection indicator: flagged</span>', unsafe_allow_html=True)
else:
    st.markdown('<span class="badge good">Prompt injection indicator: clear</span>', unsafe_allow_html=True)

st.markdown("#### Answer")
answer = result.get("answer") or ""
# Simple progressive display
placeholder = st.empty()
acc = ""
chunk = 24
for i in range(0, len(answer), chunk):
    acc += answer[i : i + chunk]
    placeholder.write(acc)

if result.get("refused"):
    st.warning("Refused / out-of-context (exact FA5 string when applicable).")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Source docs")
    sources = result.get("sources") or []
    if not sources:
        st.write("No sources.")
    for src in sources:
        with st.expander(src.get("source_path") or src.get("doc_type") or "chunk"):
            st.caption(
                f"doc_type={src.get('doc_type')} · score={src.get('score')} · "
                f"keyword={src.get('keyword_score')}"
            )
            st.write(src.get("preview") or "")
with c2:
    st.markdown("#### RAG Triad quality metrics")
    triad = result.get("triad") or {}
    if triad:
        st.metric("Faithfulness", f"{float(triad.get('faithfulness', 0)):.2f}")
        st.metric("Answer relevance", f"{float(triad.get('answer_relevance', 0)):.2f}")
        st.metric("Context relevance", f"{float(triad.get('context_relevance', 0)):.2f}")
    else:
        st.caption("No Triad scores (refused / no generation).")

with st.expander("Raw RAG result"):
    st.json(result)
