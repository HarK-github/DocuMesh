"""Text cleaning and normalization pipeline for extracted PDF text."""

import re
from typing import List, Dict, Union


def remove_page_numbers(text: str) -> str:
    """Remove standalone page number lines."""
    pattern = re.compile(r'^\s*(?:page\s*)?-?\s*\d+\s*-?\s*$', re.IGNORECASE | re.MULTILINE)
    return pattern.sub('', text)


def fix_hyphenated_breaks(text: str) -> str:
    """Rejoin words split by hyphens across line breaks."""
    pattern = re.compile(r'(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)')
    return pattern.sub(r'\1\2', text)


def rejoin_paragraphs(text: str) -> str:
    """Join broken lines within paragraphs while preserving paragraph breaks."""
    # Split text by two or more newlines (paragraph boundaries)
    raw_paras = re.split(r'\n\s*\n', text)
    cleaned_paras = []

    for para in raw_paras:
        # Rejoin single newlines with space and collapse extra whitespace
        lines = [line.strip() for line in para.split('\n') if line.strip()]
        if lines:
            cleaned_paras.append(' '.join(lines))

    return '\n\n'.join(cleaned_paras)


def remove_repeated_headers_footers(page_texts: List[str]) -> List[str]:
    """Detect and remove identical header/footer lines across pages."""
    if len(page_texts) < 2:
        return page_texts

    # Gather first and last non-empty lines from each page
    header_counts: Dict[str, int] = {}
    footer_counts: Dict[str, int] = {}

    for pt in page_texts:
        lines = [l.strip() for l in pt.splitlines() if l.strip()]
        if lines:
            top_line = lines[0]
            header_counts[top_line] = header_counts.get(top_line, 0) + 1
            bot_line = lines[-1]
            footer_counts[bot_line] = footer_counts.get(bot_line, 0) + 1

    repeated_headers = {k for k, count in header_counts.items() if count >= 2}
    repeated_footers = {k for k, count in footer_counts.items() if count >= 2}

    cleaned_pages = []
    for pt in page_texts:
        lines = pt.splitlines()
        filtered = []
        for l in lines:
            stripped = l.strip()
            if stripped in repeated_headers or stripped in repeated_footers:
                continue
            filtered.append(l)
        cleaned_pages.append('\n'.join(filtered))

    return cleaned_pages


def clean_page_text(text: str) -> str:
    """Clean a single page text string."""
    t = remove_page_numbers(text)
    t = fix_hyphenated_breaks(t)
    return rejoin_paragraphs(t)


def clean_extracted_pages(pages: List[Dict[str, Union[int, str]]]) -> List[Dict[str, Union[int, str]]]:
    """Clean all extracted pages, stripping repeated headers and footers."""
    raw_texts = [str(p["text"]) for p in pages]
    no_headers = remove_repeated_headers_footers(raw_texts)

    results = []
    for p, cleaned in zip(pages, no_headers):
        results.append({
            "page": p["page"],
            "text": clean_page_text(cleaned),
        })
    return results
