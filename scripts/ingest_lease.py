#!/usr/bin/env python3
"""CLI script to ingest a lease PDF, run extraction + math validation + compliance,
and print the results. Uses LlamaIndex PDFReader + SemanticSplitterNodeParser."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from src.ingestion.llamaindex_pipeline import ingest_and_chunk
from src.graph.tools import validate_rent_schedule
from src.extraction.hf_extractor import extract_lease_terms
from src.compliance.engine import run_compliance_check
from src.extraction.schemas import LeaseTerms

logger = structlog.get_logger()


async def main(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    print(f"Ingesting: {path.name}")
    result = ingest_and_chunk(str(path))
    print(f"  Pages: {result.page_count}")
    print(f"  Hash: {result.content_hash[:16]}...")
    print(f"  Semantic chunks: {len(result.nodes)}")
    print()

    section_dicts = result.nodes

    print("Extracting lease terms...")
    extraction = extract_lease_terms(section_dicts)
    print(json.dumps(extraction.lease_terms.model_dump(mode="json"), indent=2))
    print(f"  Confidence: {extraction.confidence_score:.2f}\n")

    print("Validating rent math (deterministic, no LLM)...")
    terms = extraction.lease_terms
    math_result = validate_rent_schedule.invoke({
        "base_rent_monthly": terms.base_rent_monthly or 0,
        "lease_term_months": terms.lease_term_months or 12,
        "escalation_type": terms.escalation_type or "none",
        "escalation_rate": terms.escalation_rate or 0.0,
        "escalation_cap": terms.escalation_cap,
        "stated_schedule": [rs.model_dump() for rs in terms.rent_schedule] if terms.rent_schedule else None,
    })
    print(f"  Valid: {math_result['is_valid']}")
    for d in math_result.get("discrepancies", []):
        print(f"  DISCREPANCY: {d}")
    print()

    print("Running compliance checks...")
    compliance = run_compliance_check("cli", extraction.lease_terms)
    print(f"  Overall risk: {compliance.overall_risk_level}")
    for flag in compliance.flags:
        print(f"  [{flag.risk_level.upper()}] {flag.rule_name}: {flag.description}")
    if not compliance.flags:
        print("  No issues found.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_lease.py <path-to-pdf>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
