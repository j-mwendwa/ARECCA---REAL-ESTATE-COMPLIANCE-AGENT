"""
Edges and conditional routing for the ARECCA LangGraph.
Reference: LLM-RAG-PIPELINE / src/graph/edges.py
"""
from src.graph.state import AgentState


def route_after_input_guard(state: AgentState) -> str:
    sec = state.get("input_security", {})
    decision = sec.get("decision", "safe")
    if decision == "blocked":
        return "rejection_node"
    return "ingest_node"


def should_continue(state: AgentState) -> str:
    errors = state.get("errors", [])
    if errors:
        return "rejection_node"
    return "report_node"
