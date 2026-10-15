"""PDF text extraction service using PyMuPDF."""

from typing import List, Dict, Union
from pathlib import Path
import pymupdf


def _open(pdf_source: Union[str, Path, bytes]) -> pymupdf.Document:
    if isinstance(pdf_source, (str, Path)):
        return pymupdf.open(str(pdf_source))
    return pymupdf.open(stream=pdf_source, filetype="pdf")


def extract_pages(pdf_source: Union[str, Path, bytes]) -> List[Dict[str, Union[int, str]]]:
    """Extract plain text from each page of a PDF document."""
    with _open(pdf_source) as doc:
        return [
            {
                "page": page_idx + 1,
                "text": doc[page_idx].get_text("text"),
            }
            for page_idx in range(len(doc))
        ]


def get_pdf_page_count(pdf_source: Union[str, Path, bytes]) -> int:
    """Return the total number of pages in a PDF document."""
    with _open(pdf_source) as doc:
        return len(doc)

