"""Validator LangGraph StateGraph + checkpointer (SSoT §2 row 4, §5.4).

completeness (Rules Engine + Elicitation) -> ehr (cross-validation) ->
risk (Secondary MCP + quality threshold) -> report (Reporter tool).

Accepts ANY patient_id with a NormalizationResult (from Normalizer or A2A).
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.validator.nodes import completeness_node, ehr_node, report_node, risk_node
from agents.validator.state import ValidatorState


def build_validator_graph():
    """Compile completeness -> ehr -> risk -> report."""
    builder = StateGraph(ValidatorState)
    builder.add_node("completeness", completeness_node)
    builder.add_node("ehr", ehr_node)
    builder.add_node("risk", risk_node)
    builder.add_node("report", report_node)
    builder.add_edge(START, "completeness")
    builder.add_edge("completeness", "ehr")
    builder.add_edge("ehr", "risk")
    builder.add_edge("risk", "report")
    builder.add_edge("report", END)
    return builder.compile(checkpointer=InMemorySaver())


validator_graph = build_validator_graph()


async def run_validation(patient_id: str, normalization: dict) -> dict:
    """Run the Validator once for any patient_id.

    normalization: a NormalizationResult dict (from Normalizer or A2A caller),
    must include normalized_extraction and translation_confidence.
    Returns the audit report dict (from clinical_insight_reporter).
    """
    from shared.tracing.langfuse import (
        flush,
        get_current_trace_id,
        observation,
        start_case_trace,
    )

    # Adopt Host trace when present — never open a nested Trace.
    tid = get_current_trace_id() or start_case_trace(str(patient_id))
    initial_state: ValidatorState = {
        "patient_id": str(patient_id),
        "normalization": normalization or {},
        "extraction": (normalization or {}).get("normalized_extraction") or {},
        "completeness_findings": [],
        "missing_fields": [],
        "elicitation_outcome": None,
        "ehr_findings": [],
        "all_findings": [],
        "risk_score": 0,
        "risk_tier": "low",
        "discharge_blocked": False,
        "release_gate": {},
        "report": None,
        "errors": [],
    }
    config = {"configurable": {"thread_id": f"validator-{patient_id}-{tid[:8]}"}}
    with observation(
        "validate_clinical_record",
        kind="chain",
        input_payload={"patient_id": patient_id},
        metadata={"agent": "Validator Agent"},
        trace_id=tid,
    ) as val:
        final_state = await validator_graph.ainvoke(initial_state, config=config)
        report = final_state.get("report") or {}
        val.set_output(
            {
                "risk_tier": final_state.get("risk_tier"),
                "discharge_blocked": final_state.get("discharge_blocked"),
                "findings": len(final_state.get("all_findings") or []),
            }
        )
    from shared.tracing.langfuse import record_span

    record_span(
        "Agent Output",
        kind="span",
        input_payload={"patient_id": patient_id},
        output_payload={
            "risk_tier": final_state.get("risk_tier"),
            "discharge_blocked": final_state.get("discharge_blocked"),
            "recommendation": (report if isinstance(report, dict) else {}).get("recommendation"),
            "findings": len(final_state.get("all_findings") or []),
        },
        metadata={"agent": "Validator Agent"},
        trace_id=tid,
    )
    flush()
    # Report alone used to drop elicitation fills — attach post-callback extraction
    # so HITL / RAG can index attending / age / etc. the Rules Engine just applied.
    if not isinstance(report, dict):
        report = {"report": report}
    else:
        report = dict(report)
    report["extraction_after_elicitation"] = final_state.get("extraction") or {}
    if final_state.get("elicitation_outcome") is not None:
        report.setdefault("elicitation_outcome", final_state.get("elicitation_outcome"))
    if final_state.get("missing_fields") is not None:
        report["validator_missing_fields"] = list(final_state.get("missing_fields") or [])
    return report
