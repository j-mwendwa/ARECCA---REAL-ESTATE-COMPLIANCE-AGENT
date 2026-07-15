from src.ingestion.chunker import chunk_by_sections, detect_section_header


def test_detect_section_header():
    assert detect_section_header("Term") is not None
    assert detect_section_header("Rent Escalation") is not None
    assert detect_section_header("Late Fee") is not None
    assert detect_section_header("Section 3: Term") is not None
    assert detect_section_header("Article 2 - Base Rent") is not None
    assert detect_section_header("§ 4.1 Grace Period") is not None


def test_detect_section_header_case_insensitive():
    assert detect_section_header("TERM") is not None
    assert detect_section_header("rent escalation") is not None
    assert detect_section_header("LATE FEE") is not None


def test_chunk_by_sections():
    pages = [
        "This is a preamble paragraph.\n\nSome more intro text.",
        "Term\nThis lease begins on January 1, 2025 and ends Dec 31, 2027.\n\n"
        "Base Rent\nThe monthly base rent is $5,000.\n\n"
        "Late Fee\nA late fee of 5% applies after 10 days.",
    ]
    sections = chunk_by_sections(pages)
    assert len(sections) >= 3
    assert sections[0].title == "Preamble"
    assert any("Term" in s.title for s in sections)
    assert any("Late Fee" in s.title for s in sections)


def test_chunk_single_page():
    pages = ["Just a simple text without any section headers."]
    sections = chunk_by_sections(pages)
    assert len(sections) == 1
    assert sections[0].title == "Preamble"
