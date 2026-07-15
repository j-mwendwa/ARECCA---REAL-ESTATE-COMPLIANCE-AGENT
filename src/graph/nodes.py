"""
LangGraph nodes for the ARECCA audit pipeline.

Each node is a callable that receives AgentState and returns a partial state update.
Reference: LLM-RAG-PIPELINE / src/graph/nodes.py
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from src.graph.state import AgentState
from src.graph.guardrails import check_input_security, check_output_security
from src.graph.tools import validate_rent_schedule
from src.config import cfg

from src.ingestion.llamaindex_pipeline import ingest_and_chunk
from src.extraction.hf_extractor import extract_lease_terms
from src.compliance.engine import run_compliance_check

from llama_index.core import Settings, Document as LLDocument
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from src.vectordb.qdrant_store import get_qdrant_vector_store

import structlog

logger = structlog.get_logger()

_CHUNK_SIZE = cfg.get("chunking", {}).get("chunk_size", 1024)
_CHUNK_OVERLAP = cfg.get("chunking", {}).get("chunk_overlap", 128)
_MAX_FILE_SIZE_MB = cfg.get("storage", {}).get("max_file_size_mb", 50)


def _resolve_local_path(storage_path: str, doc_id: str) -> str:
    return storage_path


def input_guardrail_node(state: AgentState) -> dict:
    logger.info("node.input_guardrail", doc_id=state["document_id"])
    content_bytes = b""
    file_size = 0

    local_path = state.get("storage_path", "")
    file_path = Path(local_path) if local_path else None
    if file_path and file_path.exists():
        file_size = file_path.stat().st_size
        content_bytes = file_path.read_bytes()[:4096]

    sec = check_input_security(
        filename=state["filename"],
        content=content_bytes,
        content_hash=state["content_hash"],
        file_size_bytes=file_size,
    )
    return {"input_security": sec, "errors": []}


def rejection_node(state: AgentState) -> dict:
    logger.warning("node.rejection", doc_id=state["document_id"], reason=state.get("input_security"))
    return {
        "audit_result": {
            "document_id": state["document_id"],
            "status": "rejected",
            "error": state.get("input_security", {}).get("issues", ["Input rejected by guardrail"]),
        }
    }


def ingest_node(state: AgentState) -> dict:
    logger.info("node.ingest", doc_id=state["document_id"])
    parsed_path = _resolve_local_path(state["storage_path"], state["document_id"])
    result = ingest_and_chunk(parsed_path)
    return {
        "parsed_doc": {
            "text": result.text,
            "pages": result.pages,
            "page_count": result.page_count,
            "metadata": result.metadata,
        },
        "sections": result.nodes,
    }


def chunk_node(state: AgentState) -> dict:
    logger.info("node.chunk", doc_id=state["document_id"])
    sections = state.get("sections")
    if not sections:
        parsed = state.get("parsed_doc")
        if not parsed:
            return {"errors": ["No parsed document or sections available"]}
        result = ingest_and_chunk(state["storage_path"])
        return {"sections": result.nodes}
    return {}


def extract_node(state: AgentState) -> dict:
    logger.info("node.extract", doc_id=state["document_id"])
    sections = state.get("sections", [])
    if not sections:
        return {"errors": ["No sections to extract from"]}
    result = extract_lease_terms(sections, document_id=state["document_id"])
    return {
        "extraction": result.model_dump(mode="json"),
        "lease_terms": result.lease_terms.model_dump(mode="json"),
    }


def math_validate_node(state: AgentState) -> dict:
    logger.info("node.math_validate", doc_id=state["document_id"])
    lease_terms = state.get("lease_terms")
    if not lease_terms:
        return {"errors": ["No lease terms to validate"]}
    stated = lease_terms.get("rent_schedule")
    tool_result = validate_rent_schedule.invoke({
        "base_rent_monthly": lease_terms.get("base_rent_monthly") or 0,
        "lease_term_months": lease_terms.get("lease_term_months") or 12,
        "escalation_type": lease_terms.get("escalation_type") or "none",
        "escalation_rate": lease_terms.get("escalation_rate") or 0.0,
        "escalation_cap": lease_terms.get("escalation_cap"),
        "stated_schedule": stated,
    })
    return {"math_validation": tool_result}


def compliance_node(state: AgentState) -> dict:
    logger.info("node.compliance", doc_id=state["document_id"])
    lease_terms = state.get("lease_terms")
    if not lease_terms:
        return {"errors": ["No lease terms for compliance check"]}
    from src.extraction.schemas import LeaseTerms
    terms_obj = LeaseTerms(**lease_terms)
    report = run_compliance_check(state["document_id"], terms_obj)
    return {"compliance_report": {
        "overall_risk_level": report.overall_risk_level,
        "flag_count": len(report.flags),
        "flags": [
            {
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "risk_level": f.risk_level,
                "description": f.description,
            }
            for f in report.flags
        ],
        "summary": report.summary,
    }}


def index_node(state: AgentState) -> dict:
    logger.info("node.index", doc_id=state["document_id"])
    sections = state.get("sections", [])
    if not sections:
        return {"warnings": ["No sections to index"]}
    index_docs = []
    for sec in sections:
        doc = LLDocument(
            text=sec.get("content", ""),
            metadata={
                "section_title": sec.get("title", "Unknown"),
                "page_number": sec.get("page_number", 0),
                "document_id": state["document_id"],
            },
        )
        index_docs.append(doc)
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP),
            Settings.embed_model,
        ],
        vector_store=get_qdrant_vector_store(),
    )
    pipeline.run(documents=index_docs)
    return {}


def output_guardrail_node(state: AgentState) -> dict:
    logger.info("node.output_guardrail", doc_id=state["document_id"])
    sec = check_output_security(
        extraction=state.get("extraction"),
        compliance_report=state.get("compliance_report"),
    )
    return {"output_security": sec}


def report_node(state: AgentState) -> dict:
    logger.info("node.report", doc_id=state["document_id"])
    report = {
        "document_id": state["document_id"],
        "filename": state["filename"],
        "status": "completed",
        "extraction": state.get("extraction"),
        "math_validation": state.get("math_validation"),
        "compliance_report": state.get("compliance_report"),
        "security": {
            "input": state.get("input_security"),
            "output": state.get("output_security"),
        },
    }
    try:
        from src.memory.conversation import update_summary
        update_summary(state["document_id"], report)
    except Exception as e:
        logger.warning("node.report.summary_failed", doc_id=state["document_id"], error=str(e))
    return {"audit_result": report}
