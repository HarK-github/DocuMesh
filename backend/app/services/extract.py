"""PDF text extraction service using PyMuPDF."""

from typing import List, Dict, Union
from pathlib import Path
import pymupdf


def extract_pages(pdf_source: Union[str, Path, bytes]) -> List[Dict[str, Union[int, str]]]:
    """Extract plain text from each page of a PDF document."""
    if isinstance(pdf_source, (str, Path)):
        doc = pymupdf.open(str(pdf_source))
    else:
        doc = pymupdf.open(stream=pdf_source, filetype="pdf")

    pages = []
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")
            pages.append({
                "page": page_idx + 1,
                "text": text,
            })
    finally:
        doc.close()

    return pages


def get_pdf_page_count(pdf_source: Union[str, Path, bytes]) -> int:
    """Return the total number of pages in a PDF document."""
    if isinstance(pdf_source, (str, Path)):
        doc = pymupdf.open(str(pdf_source))
    else:
        doc = pymupdf.open(stream=pdf_source, filetype="pdf")
    try:
        return len(doc)
    finally:
        doc.close()
