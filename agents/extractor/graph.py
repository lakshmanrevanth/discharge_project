"""Extractor LangGraph StateGraph + checkpointer (SSoT §2 row 2, §5.2).

StateGraph + MemorySaver (company style: InMemorySaver — same role).
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.extractor.nodes import extract_node, harvest_node
from agents.extractor.state import ExtractorState

_DEFAULT_DOC_TYPES = ["discharge", "lab", "bill"]


def build_extractor_graph():
    """Compile the two-node Extractor graph: harvest -> extract."""
    builder = StateGraph(ExtractorState)
    builder.add_node("harvest", harvest_node)
    builder.add_node("extract", extract_node)
    builder.add_edge(START, "harvest")
    builder.add_edge("harvest", "extract")
    builder.add_edge("extract", END)
    return builder.compile(checkpointer=InMemorySaver())


extractor_graph = build_extractor_graph()


async def run_extraction(patient_id: str, doc_types: list[str] | None = None) -> dict:
    """Run the graph once for one patient_id. Returns the final ExtractionResult dict."""
    initial_state: ExtractorState = {
        "patient_id": patient_id,
        "doc_types": doc_types or list(_DEFAULT_DOC_TYPES),
        "harvested": {},
        "resources": {},
        "extraction": None,
        "errors": [],
    }
    config = {"configurable": {"thread_id": f"extractor-{patient_id}"}}
    final_state = await extractor_graph.ainvoke(initial_state, config=config)
    return final_state["extraction"]
