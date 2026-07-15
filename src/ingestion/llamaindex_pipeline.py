"""
LlamaIndex-based ingestion and semantic chunking pipeline.

Replaces raw PyMuPDF parsing + regex chunking with:
  - LlamaIndex PDFReader for document ingestion
  - SemanticSplitterNodeParser for embedding-based semantic chunking
"""
import hashlib
from pathlib import Path
from typing import Any

from llama_index.core import Settings
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.readers.file import PDFReader

from src.config import cfg
from src.core.exceptions import IngestionError


class LingestedDocument:
    def __init__(self, text: str, pages: list[str], metadata: dict, nodes: list[dict]) -> None:
        self.text = text
        self.pages = pages
        self.metadata = metadata
        self.nodes = nodes

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def page_count(self) -> int:
        return len(self.pages)


_chunking_cfg = cfg.get("chunking", {})
_SEMANTIC_BUFFER_SIZE = _chunking_cfg.get("semantic_buffer_size", 3)
_SEMANTIC_BREAKPOINT = _chunking_cfg.get("semantic_breakpoint_percentile", 85)
_EMBED_MODEL = cfg.get("embedding", {}).get("model", "nlpaueb/legal-bert-base-uncased")


def _get_semantic_splitter() -> SemanticSplitterNodeParser:
    return SemanticSplitterNodeParser(
        buffer_size=_SEMANTIC_BUFFER_SIZE,
        breakpoint_percentile_threshold=_SEMANTIC_BREAKPOINT,
        embed_model=Settings.embed_model,
    )


def ingest_and_chunk(file_path: str | Path) -> LingestedDocument:
    try:
        reader = PDFReader()
        docs = reader.load_data(file=Path(str(file_path)))
    except Exception as e:
        raise IngestionError(f"LlamaIndex PDF ingestion failed: {e}") from e

    if not docs:
        raise IngestionError("PDFReader returned no documents")

    full_text = "\n\n".join(d.text for d in docs)
    pages: list[str] = []
    for d in docs:
        pages.append(d.text)

    metadata: dict[str, Any] = {}
    if docs:
        first_meta = docs[0].metadata or {}
        metadata = {
            "title": first_meta.get("title", ""),
            "author": first_meta.get("author", ""),
            "subject": first_meta.get("subject", ""),
            "creator": first_meta.get("creator", ""),
            "producer": first_meta.get("producer", ""),
        }
    metadata["page_count"] = len(pages)

    try:
        splitter = _get_semantic_splitter()
        nodes = splitter.get_nodes_from_documents(docs)
    except Exception as e:
        raise IngestionError(f"Semantic chunking failed: {e}") from e

    node_dicts: list[dict] = []
    for i, node in enumerate(nodes):
        title = node.metadata.get("section_title")
        if not title:
            preview = node.get_content().strip()[:60].replace("\n", " ")
            title = f"Section {i + 1}: {preview}..."

        node_dicts.append({
            "title": title,
            "content": node.get_content(),
            "page_number": node.metadata.get("page_number", 0),
            "node_id": node.node_id,
        })

    return LingestedDocument(
        text=full_text,
        pages=pages,
        metadata=metadata,
        nodes=node_dicts,
    )
