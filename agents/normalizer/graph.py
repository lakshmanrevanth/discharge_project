"""Normalizer LangGraph StateGraph + checkpointer (SSoT §2 row 3, §5.3).

prepare (Prompt + Resource) → bridge (Sampling tool) → assemble (confidence).

Accepts ANY patient_id and ANY source language (or auto-detect).
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.normalizer.nodes import assemble_node, bridge_node, prepare_node
from agents.normalizer.state import NormalizerState
from shared.language import detect_source_language, normalize_lang_code


def build_normalizer_graph():
    """Compile prepare → bridge → assemble."""
    builder = StateGraph(NormalizerState)
    builder.add_node("prepare", prepare_node)
    builder.add_node("bridge", bridge_node)
    builder.add_node("assemble", assemble_node)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "bridge")
    builder.add_edge("bridge", "assemble")
    builder.add_edge("assemble", END)
    return builder.compile(checkpointer=InMemorySaver())


normalizer_graph = build_normalizer_graph()


async def run_normalization(
    patient_id: str,
    extraction: dict,
    source_language: str | None = None,
) -> dict:
    """Run the Normalizer once for any patient_id.

    source_language: short code (hi/es/…) or None/'auto' to detect from extraction.
    Returns NormalizationResult as a dict.
    """
    from shared.tracing.langfuse import get_current_trace_id, observation, start_case_trace

    if source_language:
        lang = normalize_lang_code(source_language)
    else:
        lang = detect_source_language(extraction or {})

    tid = get_current_trace_id() or start_case_trace(str(patient_id))
    initial_state: NormalizerState = {
        "patient_id": str(patient_id),
        "extraction": extraction or {},
        "source_language": lang,
        "prompt_text": "",
        "abbreviations_yaml": "",
        "bridge_raw": "",
        "result": None,
        "errors": [],
    }
    # Thread id is per-run — works for any patient_id string
    config = {"configurable": {"thread_id": f"normalizer-{patient_id}"}}
    with observation(
        "normalize_clinical_record",
        kind="chain",
        input_payload={"patient_id": patient_id, "source_language": lang},
        metadata={"agent": "Normalizer Agent"},
        trace_id=tid,
    ) as norm:
        final_state = await normalizer_graph.ainvoke(initial_state, config=config)
        result = final_state["result"]
        norm.set_output(
            {
                "translation_confidence": (result or {}).get("translation_confidence"),
                "source_language": (result or {}).get("source_language"),
            }
        )
    from shared.tracing.langfuse import record_span

    record_span(
        "Agent Output",
        kind="span",
        input_payload={"patient_id": patient_id},
        output_payload=result,
        metadata={"agent": "Normalizer Agent"},
        trace_id=tid,
    )
    return result
