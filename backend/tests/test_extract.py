"""Test PDF extraction service with sample PDF."""

from pathlib import Path
from backend.app.services.extract import extract_pages, get_pdf_page_count


def test_extract_pages_from_sample() -> None:
    """Verify that sample PDF pages are extracted correctly."""
    sample_path = Path("sample/sample.pdf")
    assert sample_path.exists(), "sample/sample.pdf must exist"

    pages = extract_pages(sample_path)
    assert len(pages) == 2
    assert pages[0]["page"] == 1
    assert "COMPUTING MACHINERY AND INTELLIGENCE" in pages[0]["text"]
    assert "imitation game" in pages[0]["text"]

    assert pages[1]["page"] == 2
    assert "Digital Computers" in pages[1]["text"]


def test_get_pdf_page_count() -> None:
    """Verify page count extraction."""
    sample_path = Path("sample/sample.pdf")
    count = get_pdf_page_count(sample_path)
    assert count == 2


def test_extract_pages_from_bytes_and_str() -> None:
    """Verify extraction from str and bytes sources."""
    sample_path = Path("sample/sample.pdf")
    pages_from_str = extract_pages(str(sample_path))
    assert len(pages_from_str) == 2

    with open(sample_path, "rb") as f:
        pdf_bytes = f.read()
    pages_from_bytes = extract_pages(pdf_bytes)
    assert len(pages_from_bytes) == 2
    assert pages_from_bytes[0]["text"] == pages_from_str[0]["text"]
    assert get_pdf_page_count(pdf_bytes) == 2

