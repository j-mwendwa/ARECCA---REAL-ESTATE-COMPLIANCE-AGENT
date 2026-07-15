"""
LangGraph pipeline compiler for ARECCA.

Builds a StateGraph that executes the full audit pipeline:
input_guardrail → ingest → chunk → extract → math_validate → compliance → index → output_guardrail → report

Reference: LLM-RAG-PIPELINE / src/graph/graph.py
"""
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from src.graph.state import AgentState
from src.graph.nodes import (
    input_guardrail_node,
    rejection_node,
    ingest_node,
    chunk_node,
    extract_node,
    math_validate_node,
    compliance_node,
    index_node,
    output_guardrail_node,
    report_node,
)
from src.graph.edges import route_after_input_guard, should_continue


def build_graph() -> CompiledStateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("rejection_node", rejection_node)
    workflow.add_node("ingest_node", ingest_node)
    workflow.add_node("chunk_node", chunk_node)
    workflow.add_node("extract_node", extract_node)
    workflow.add_node("math_validate_node", math_validate_node)
    workflow.add_node("compliance_node", compliance_node)
    workflow.add_node("index_node", index_node)
    workflow.add_node("output_guardrail", output_guardrail_node)
    workflow.add_node("report_node", report_node)

    workflow.set_entry_point("input_guardrail")

    workflow.add_conditional_edges(
        "input_guardrail",
        route_after_input_guard,
        {
            "rejection_node": "rejection_node",
            "ingest_node": "ingest_node",
        },
    )

    workflow.add_edge("ingest_node", "chunk_node")
    workflow.add_edge("chunk_node", "extract_node")
    workflow.add_edge("extract_node", "math_validate_node")
    workflow.add_edge("math_validate_node", "compliance_node")
    workflow.add_edge("compliance_node", "index_node")
    workflow.add_edge("index_node", "output_guardrail")
    workflow.add_edge("output_guardrail", "report_node")

    workflow.add_conditional_edges(
        "report_node",
        should_continue,
        {
            "rejection_node": "rejection_node",
            "report_node": END,
        },
    )

    workflow.add_edge("rejection_node", END)

    return workflow.compile()
