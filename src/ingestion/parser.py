import hashlib
from pathlib import Path
from typing import BinaryIO

import fitz  # type: ignore[import-untyped]

from src.core.exceptions import IngestionError


class ParsedDocument:
    def __init__(self, text: str, pages: list[str], metadata: dict) -> None:
        self.text = text
        self.pages = pages
        self.metadata = metadata

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def page_count(self) -> int:
        return len(self.pages)


def parse_pdf(file_path: str | Path | BinaryIO) -> ParsedDocument:
    try:
        doc = fitz.open(stream=file_path, filetype="pdf") if isinstance(file_path, (BinaryIO,)) else fitz.open(file_path)
    except Exception as e:
        raise IngestionError(f"Failed to open PDF: {e}") from e

    pages: list[str] = []
    metadata: dict = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages.append(text)

    if doc.metadata:
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
        }

    metadata["page_count"] = len(doc)
    full_text = "\n\n".join(pages)
    doc.close()

    return ParsedDocument(text=full_text, pages=pages, metadata=metadata)
