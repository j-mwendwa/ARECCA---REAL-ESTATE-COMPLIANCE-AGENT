from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Any


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str


class AuditResult(BaseModel):
    document_id: str
    filename: str
    status: str
    extraction: dict[str, Any] | None = None
    math_validation: dict[str, Any] | None = None
    compliance_report: dict[str, Any] | None = None
    error: str | None = None


class AuditStatusResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(description="Search query for lease clause retrieval")
    top_k: int = Field(default=5, description="Number of results to return")
    alpha: float = Field(default=0.3, description="Hybrid search alpha (0=dense, 1=sparse)")


class SearchResult(BaseModel):
    section_title: str
    content: str
    score: float
    page_number: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
