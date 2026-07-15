from pathlib import Path
from src.ingestion.llamaindex_pipeline import ingest_and_chunk, LingestedDocument
from src.core.exceptions import IngestionError


def test_ingest_nonexistent():
    try:
        ingest_and_chunk("/nonexistent/file.pdf")
        assert False, "Expected IngestionError"
    except IngestionError:
        pass


def test_lingested_document():
    doc = LingestedDocument(
        text="lease content",
        pages=["page 1"],
        metadata={"page_count": 1},
        nodes=[{"title": "Section 1", "content": "lease content", "page_number": 1, "node_id": "n1"}],
    )
    assert doc.page_count == 1
    assert isinstance(doc.content_hash, str) and len(doc.content_hash) == 64
    assert len(doc.nodes) == 1
    assert doc.nodes[0]["title"] == "Section 1"


def test_ingested_document_no_nodes():
    doc = LingestedDocument(text="", pages=[], metadata={}, nodes=[])
    assert doc.page_count == 0
    assert len(doc.nodes) == 0
