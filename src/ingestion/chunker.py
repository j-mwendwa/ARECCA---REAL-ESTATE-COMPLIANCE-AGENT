import re
from typing import Any



_PREFIX = r"(?:#+\s*)?(?:section\s+[\d.]+\s*[.:–—-]?\s*)?(?:article\s+[\d.]+\s*[.:–—-]?\s*)?(?:§\s+[\d.]+\s*[.:–—-]?\s*)?"

LEASE_SECTION_PATTERNS = [
    rf"(?i)^{_PREFIX}(term|duration|lease\s*term|commencement|expiration)",
    rf"(?i)^{_PREFIX}(rent|base\s*rent|minimum\s*rent|annual\s*rent|monthly\s*rent)",
    rf"(?i)^{_PREFIX}(rent\s*escalation|escalation|rent\s*increase|annual\s*increase|cpi\s*adjustment)",
    rf"(?i)^{_PREFIX}(security\s*deposit|deposit)",
    rf"(?i)^{_PREFIX}(late\s*fee|late\s*charge|default\s*interest)",
    rf"(?i)^{_PREFIX}(grace\s*period|notice\s*period|cure\s*period)",
    rf"(?i)^{_PREFIX}(maintenance|repairs|utilities|operating\s*expenses)",
    rf"(?i)^{_PREFIX}(insurance|liability|indemnity|indemnification)",
    rf"(?i)^{_PREFIX}(sublease|sublet|assignment)",
    rf"(?i)^{_PREFIX}(termination|early\s*termination|break\s*clause|cancellation)",
    rf"(?i)^{_PREFIX}(renewal|extension|option\s*to\s*renew)",
    rf"(?i)^{_PREFIX}(governing\s*law|jurisdiction|venue|arbitration|dispute\s*resolution)",
    rf"(?i)^{_PREFIX}(signature|execution|counterpart|notices)",
]

COMPILED_PATTERNS = [re.compile(p) for p in LEASE_SECTION_PATTERNS]


class DocumentSection:
    def __init__(self, title: str, content: str, page_number: int, section_type: str | None = None) -> None:
        self.title = title
        self.content = content
        self.page_number = page_number
        self.section_type = section_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "page_number": self.page_number,
            "section_type": self.section_type,
        }


def detect_section_header(line: str) -> str | None:
    stripped = line.strip()
    lower = stripped.lower()
    for pattern in COMPILED_PATTERNS:
        if pattern.match(lower):
            return stripped
    return None


def chunk_by_sections(pages: list[str]) -> list[DocumentSection]:
    sections: list[DocumentSection] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    current_page = 1

    for page_idx, page_text in enumerate(pages):
        lines = page_text.split("\n")
        for line in lines:
            header = detect_section_header(line)
            if header:
                if current_lines:
                    sections.append(DocumentSection(
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                        page_number=current_page,
                    ))
                current_title = header
                current_lines = [line]
                current_page = page_idx + 1
            else:
                current_lines.append(line)
        current_lines.append("")  # page separator

    if current_lines:
        sections.append(DocumentSection(
            title=current_title,
            content="\n".join(current_lines).strip(),
            page_number=current_page,
        ))

    return sections


def chunk_to_llamaindex_documents(sections: list[DocumentSection]) -> list[dict]:
    from llama_index.core import Document as LLDocument
    docs: list[LLDocument] = []
    for sec in sections:
        doc = LLDocument(
            text=sec.content,
            metadata={
                "section_title": sec.title,
                "page_number": sec.page_number,
                "section_type": sec.section_type or "unknown",
            },
        )
        docs.append(doc)
    return docs
