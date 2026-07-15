from src.ingestion.parser import parse_pdf, ParsedDocument
from src.core.exceptions import IngestionError


def test_parse_pdf_nonexistent():
    try:
        parse_pdf("/nonexistent/file.pdf")
        assert False, "Expected IngestionError"
    except IngestionError:
        pass


def test_parsed_document_properties():
    doc = ParsedDocument(
        text="lease content here",
        pages=["page 1 text", "page 2 text"],
        metadata={"page_count": 2},
    )
    assert doc.page_count == 2
    assert isinstance(doc.content_hash, str) and len(doc.content_hash) == 64
