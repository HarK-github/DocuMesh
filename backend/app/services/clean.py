"""Text cleaning and normalization pipeline for extracted PDF text."""

import math
from collections import Counter
import re
from typing import List, Dict, Union, Tuple, Optional, Set

_DICTIONARY_WORDS: Optional[Set[str]] = None


def _get_english_dictionary() -> Set[str]:
    """Lazy-load local system dictionary or fallback set for hyphen resolution."""
    global _DICTIONARY_WORDS
    if _DICTIONARY_WORDS is None:
        words = set()
        dict_path = "/usr/share/dict/words"
        try:
            with open(dict_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        words.add(w)
        except Exception:
            words = {
                "computational", "universal", "system", "machine", "algorithm",
                "parameter", "representation", "optimization", "information",
            }
        _DICTIONARY_WORDS = words
    return _DICTIONARY_WORDS


def remove_page_numbers(text: str) -> str:
    """Remove standalone page number lines."""
    pattern = re.compile(r'^\s*(?:page\s*)?-?\s*\d+\s*-?\s*$', re.IGNORECASE | re.MULTILINE)
    return pattern.sub('', text)


def fix_hyphenated_breaks(text: str, doc_lexicon: Optional[Set[str]] = None) -> str:
    """Rejoin words split by hyphens across line breaks using context and dictionary."""
    if doc_lexicon is None:
        doc_lexicon = set(re.findall(r'\b[a-zA-Z]+(?:-[a-zA-Z]+)?\b', text.lower()))

    dict_words = _get_english_dictionary()

    def replace_hyphen(match: re.Match) -> str:
        w1, w2 = match.group(1), match.group(2)
        compound = f"{w1.lower()}-{w2.lower()}"
        merged = f"{w1.lower()}{w2.lower()}"

        if compound in doc_lexicon:
            return f"{w1}-{w2}"
        if merged in doc_lexicon:
            return f"{w1}{w2}"
        if merged in dict_words and compound not in dict_words:
            return f"{w1}{w2}"
        if compound in dict_words:
            return f"{w1}-{w2}"
        return f"{w1}-{w2}"

    pattern = re.compile(r'(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)')
    return pattern.sub(replace_hyphen, text)


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
    """Detect and remove normalized repeated header/footer lines across pages."""
    if len(page_texts) < 2:
        return page_texts

    def normalize_line(line: str) -> str:
        return re.sub(r'\b\d+\b', '<NUM>', line.strip())

    top_patterns = []
    bot_patterns = []
    for pt in page_texts:
        non_empty = [l.strip() for l in pt.splitlines() if l.strip()]
        if non_empty:
            top_patterns.append(normalize_line(non_empty[0]))
            bot_patterns.append(normalize_line(non_empty[-1]))

    # Dynamic threshold: at least 20% of pages, minimum 2
    threshold = max(2, math.ceil(0.20 * len(page_texts)))

    repeated_top = {pat for pat, count in Counter(top_patterns).items() if count >= threshold}
    repeated_bot = {pat for pat, count in Counter(bot_patterns).items() if count >= threshold}

    cleaned_pages = []
    for pt in page_texts:
        lines = pt.splitlines()
        non_empty_indices = [idx for idx, l in enumerate(lines) if l.strip()]
        if not non_empty_indices:
            cleaned_pages.append(pt)
            continue

        first_idx = non_empty_indices[0]
        last_idx = non_empty_indices[-1]

        filtered = []
        for idx, l in enumerate(lines):
            stripped = l.strip()
            if not stripped:
                filtered.append(l)
                continue
            norm = normalize_line(stripped)
            if idx == first_idx and norm in repeated_top:
                continue
            if idx == last_idx and norm in repeated_bot:
                continue
            filtered.append(l)
        cleaned_pages.append('\n'.join(filtered))

    return cleaned_pages


def clean_page_text(text: str, doc_lexicon: Optional[Set[str]] = None) -> str:
    """Clean a single page text string."""
    t = remove_page_numbers(text)
    t = fix_hyphenated_breaks(t, doc_lexicon=doc_lexicon)
    return rejoin_paragraphs(t)


def clean_extracted_pages(pages: List[Dict[str, Union[int, str]]]) -> List[Dict[str, Union[int, str]]]:
    """Clean all extracted pages, stripping repeated headers and footers."""
    raw_texts = [str(p["text"]) for p in pages]
    no_headers = remove_repeated_headers_footers(raw_texts)

    doc_text = " ".join(raw_texts)
    doc_lexicon = set(re.findall(r'\b[a-zA-Z]+(?:-[a-zA-Z]+)?\b', doc_text.lower()))

    results = []
    for p, cleaned in zip(pages, no_headers):
        results.append({
            "page": p["page"],
            "text": clean_page_text(cleaned, doc_lexicon=doc_lexicon),
        })
    return results


def snap_to_word_boundaries(text: str, start: int, end: int) -> Tuple[int, int]:
    """Adjust start and end character offsets to the nearest word boundaries in text."""
    if not text or start >= end:
        return start, end

    start = max(0, min(start, len(text)))
    end = max(0, min(end, len(text)))
    if start >= end:
        return start, end

    words = list(re.finditer(r'\w+', text))
    if not words:
        return start, end

    new_start = start
    new_end = end

    # Snap start: if inside a word, choose the closer boundary (start or end of word)
    for w in words:
        w_s, w_e = w.start(), w.end()
        if w_s < start < w_e:
            if (start - w_s) <= (w_e - start):
                new_start = w_s
            else:
                new_start = w_e
            break
        elif start == w_s or start == w_e:
            new_start = start
            break

    # Snap end: if inside a word, choose the closer boundary (end or start of word)
    for w in words:
        w_s, w_e = w.start(), w.end()
        if w_s < end < w_e:
            if (w_e - end) <= (end - w_s):
                new_end = w_e
            else:
                new_end = w_s
            break
        elif end == w_s or end == w_e:
            new_end = end
            break

    # Strip any leading or trailing whitespace so highlights never start/end on whitespace
    while new_start < new_end and text[new_start].isspace():
        new_start += 1
    while new_end > new_start and text[new_end - 1].isspace():
        new_end -= 1

    if new_start >= new_end:
        return start, end

    return new_start, new_end

