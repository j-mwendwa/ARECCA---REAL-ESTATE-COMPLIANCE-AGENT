import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    UploadResponse, AuditResult, AuditStatusResponse,
    SearchRequest, SearchResponse, SearchResult,
)
from src.ingestion.storage import save_file
from src.retrieval.hybrid_retriever import get_hybrid_retriever
from src.vectordb.qdrant_store import ensure_collection
from src.database.models import (
    LeaseDocument, LeaseExtraction, MathValidation, ComplianceFlag, AuditStatus,
)
from src.database.session import get_session
from src.config import cfg
from src.graph.graph import build_graph
from src.graph.state import AgentState

import structlog

from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["audit"])

_EMBED_MODEL = cfg.get("embedding", {}).get("model", "nlpaueb/legal-bert-base-uncased")
_RETRIEVAL_CFG = cfg.get("retrieval", {})

if not Settings.embed_model:
    Settings.embed_model = HuggingFaceEmbedding(model_name=_EMBED_MODEL)

_app = None


def get_graph_app():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


@router.post("/upload", response_model=UploadResponse)
async def upload_lease(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    blob_name = f"leases/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{file.filename}"

    try:
        storage_path = save_file(content, blob_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {e}")

    doc_id = uuid.uuid4()
    document = LeaseDocument(
        id=doc_id,
        filename=file.filename,
        storage_path=storage_path,
        content_hash=file_hash,
        status=AuditStatus.processing,
    )
    session.add(document)
    await session.commit()

    return UploadResponse(
        document_id=str(doc_id),
        filename=file.filename,
        status=AuditStatus.processing.value,
        message="Document uploaded and queued for audit",
    )


@router.post("/audit/{document_id}", response_model=AuditResult)
async def run_audit(
    document_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await session.execute(
        select(LeaseDocument).where(LeaseDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status == AuditStatus.completed:
        return await _build_audit_result(document, session)

    document.status = AuditStatus.processing
    await session.commit()

    graph = get_graph_app()

    initial_state: AgentState = {
        "document_id": document_id,
        "filename": document.filename,
        "storage_path": document.storage_path,
        "content_hash": document.content_hash,
        "parsed_doc": None,
        "sections": None,
        "extraction": None,
        "lease_terms": None,
        "math_validation": None,
        "compliance_report": None,
        "audit_result": None,
        "errors": [],
        "warnings": [],
        "input_security": None,
        "output_security": None,
    }

    try:
        import asyncio
        final_state = await asyncio.to_thread(graph.invoke, initial_state)

        if final_state.get("errors"):
            document.status = AuditStatus.failed
            await session.commit()
            raise HTTPException(status_code=422, detail=final_state["errors"])

        ext = final_state.get("extraction")
        if ext:
            ext_record = LeaseExtraction(
                document_id=doc_uuid,
                raw_json=ext,
                llm_model=cfg.get("llm", {}).get("model", "legal-model"),
            )
            session.add(ext_record)

        math_val = final_state.get("math_validation")
        if math_val:
            math_record = MathValidation(
                document_id=doc_uuid,
                is_valid=math_val.get("is_valid", False),
                discrepancy_details={
                    "discrepancies": math_val.get("discrepancies", []),
                    "projected_schedule": math_val.get("projected_schedule", []),
                },
            )
            session.add(math_record)

        compliance = final_state.get("compliance_report")
        if compliance:
            for flag in compliance.get("flags", []):
                flag_record = ComplianceFlag(
                    document_id=doc_uuid,
                    rule_id=flag["rule_id"],
                    rule_name=flag["rule_name"],
                    risk_level=flag["risk_level"],
                    description=flag["description"],
                )
                session.add(flag_record)

        document.status = AuditStatus.completed
        document.updated_at = datetime.utcnow()
        await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        document.status = AuditStatus.failed
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")

    return await _build_audit_result(document, session)


async def _build_audit_result(document: LeaseDocument, session: AsyncSession) -> AuditResult:
    ext_row = await session.execute(
        select(LeaseExtraction).where(LeaseExtraction.document_id == document.id)
    )
    ext = ext_row.scalar_one_or_none()

    math_row = await session.execute(
        select(MathValidation).where(MathValidation.document_id == document.id)
    )
    math = math_row.scalar_one_or_none()

    flags_row = await session.execute(
        select(ComplianceFlag).where(ComplianceFlag.document_id == document.id)
    )
    flags = flags_row.scalars().all()

    compliance_report = None
    if flags:
        risk_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_risk = max((f.risk_level for f in flags), key=lambda r: risk_levels.get(r, 0))
        high_count = sum(1 for f in flags if f.risk_level in ("high", "critical"))
        compliance_report = {
            "overall_risk_level": max_risk,
            "flag_count": len(flags),
            "high_risk_count": high_count,
            "flags": [
                {
                    "rule_id": f.rule_id,
                    "rule_name": f.rule_name,
                    "risk_level": f.risk_level,
                    "description": f.description,
                }
                for f in flags
            ],
        }

    return AuditResult(
        document_id=str(document.id),
        filename=document.filename,
        status=document.status.value,
        extraction=ext.raw_json if ext else None,
        math_validation={
            "is_valid": math.is_valid,
            "details": math.discrepancy_details,
        } if math else None,
        compliance_report=compliance_report,
    )


@router.get("/documents", response_model=list[AuditStatusResponse])
async def list_documents(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(LeaseDocument).order_by(LeaseDocument.created_at.desc()).limit(100)
    )
    docs = result.scalars().all()
    return [
        AuditStatusResponse(
            document_id=str(d.id),
            filename=d.filename,
            status=d.status.value,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]


@router.get("/documents/{document_id}", response_model=AuditResult)
async def get_document_status(
    document_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await session.execute(
        select(LeaseDocument).where(LeaseDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return await _build_audit_result(document, session)


@router.post("/search", response_model=SearchResponse)
async def search_clauses(request: SearchRequest):
    ensure_collection()

    retriever = get_hybrid_retriever()
    retriever._alpha = request.alpha
    retriever._similarity_top_k = request.top_k

    nodes = retriever.retrieve(request.query)

    results = []
    for node in nodes:
        results.append(SearchResult(
            section_title=node.metadata.get("section_title", "Unknown"),
            content=node.text[:500],
            score=node.score or 0.0,
            page_number=node.metadata.get("page_number"),
        ))

    return SearchResponse(query=request.query, results=results)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ARECCA"}
