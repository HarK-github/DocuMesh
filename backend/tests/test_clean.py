"""Test text cleaning functions on small test strings."""

from backend.app.services.clean import (
    remove_page_numbers,
    fix_hyphenated_breaks,
    rejoin_paragraphs,
    remove_repeated_headers_footers,
    clean_extracted_pages,
)


def test_remove_page_numbers() -> None:
    """Verify standalone page numbers and labels are stripped."""
    sample = "Title\n1\nSome content.\nPage 42\nMore content.\n- 5 -"
    cleaned = remove_page_numbers(sample)
    assert "Title" in cleaned
    assert "Some content." in cleaned
    assert "More content." in cleaned
    assert "Page 42" not in cleaned
    assert "- 5 -" not in cleaned


def test_fix_hyphenated_breaks() -> None:
    """Verify hyphenated line breaks are properly rejoined into single words."""
    sample = "This is a compu-\n   tational machine and a uni-\nversal system."
    cleaned = fix_hyphenated_breaks(sample)
    assert "computational" in cleaned
    assert "universal" in cleaned


def test_rejoin_paragraphs() -> None:
    """Verify lines in paragraphs are merged with single spaces, preserving double newlines."""
    sample = "First line of paragraph.\nSecond line of paragraph.\n\nNew paragraph starts here.\nContinued."
    cleaned = rejoin_paragraphs(sample)
    assert cleaned == "First line of paragraph. Second line of paragraph.\n\nNew paragraph starts here. Continued."


def test_remove_repeated_headers_footers() -> None:
    """Verify repeated headers and footers across pages are removed."""
    page1 = "Journal of AI Research\nContent of page one.\nPage Footer Copyright 2026"
    page2 = "Journal of AI Research\nContent of page two.\nPage Footer Copyright 2026"
    cleaned_pages = remove_repeated_headers_footers([page1, page2])
    assert "Journal of AI Research" not in cleaned_pages[0]
    assert "Page Footer Copyright 2026" not in cleaned_pages[0]
    assert "Content of page one." in cleaned_pages[0]
    assert "Content of page two." in cleaned_pages[1]


def test_remove_repeated_headers_footers_characterization() -> None:
    """Verify edge cases: blank lines, differing headers, single page."""
    # Blank lines around headers/footers
    p1 = "\n\n  Header Title  \nBody text A\nFooter Note\n  \n"
    p2 = "  Header Title  \nBody text B\nFooter Note"
    p3 = "Different Header\nBody text C\nFooter Note"
    cleaned = remove_repeated_headers_footers([p1, p2, p3])
    # Header Title appears in p1 and p2 (count 2) -> stripped
    assert "Header Title" not in cleaned[0]
    assert "Header Title" not in cleaned[1]
    # Footer Note appears in all 3 -> stripped
    assert "Footer Note" not in cleaned[0]
    assert "Footer Note" not in cleaned[1]
    assert "Footer Note" not in cleaned[2]
    # Unique header in p3 is retained
    assert "Different Header" in cleaned[2]
    # Body texts retained
    assert "Body text A" in cleaned[0]
    assert "Body text B" in cleaned[1]
    assert "Body text C" in cleaned[2]


def test_clean_extracted_pages() -> None:
    """Verify clean_extracted_pages applies all cleaning steps."""
    pages = [
        {"page": 1, "text": "Header\nFirst line.\nSecond line.\n1\nFooter"},
        {"page": 2, "text": "Header\nThird line.\nFourth line.\n2\nFooter"},
    ]
    cleaned = clean_extracted_pages(pages)
    assert len(cleaned) == 2
    assert cleaned[0]["page"] == 1
    assert "First line. Second line." in cleaned[0]["text"]
