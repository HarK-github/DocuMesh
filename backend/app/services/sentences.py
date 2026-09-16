"""Sentence segmentation and offset tracking using pysbd."""

from typing import List, Dict, Tuple, Union
import pysbd


def segment_sentences(
    clean_pages: List[Dict[str, Union[int, str]]]
) -> Tuple[str, List[Dict[str, Union[int, str]]]]:
    """Segment cleaned pages into sentences and compute exact character offsets in clean_text."""
    doc_text_parts: List[str] = []
    page_offsets: List[Tuple[int, int, str]] = []
    current_len = 0

    for page_item in clean_pages:
        page_num = int(page_item["page"])
        page_text = str(page_item["text"]).strip()
        if not page_text:
            continue
        if doc_text_parts:
            doc_text_parts.append("\n\n")
            current_len += 2
        page_offsets.append((page_num, current_len, page_text))
        doc_text_parts.append(page_text)
        current_len += len(page_text)

    clean_text = "".join(doc_text_parts)
    segmenter = pysbd.Segmenter(language="en", clean=False)
    sentence_records: List[Dict[str, Union[int, str]]] = []
    sent_idx = 0

    for page_num, page_start_offset, page_text in page_offsets:
        segments = segmenter.segment(page_text)
        if isinstance(segments, str):
            segments = [segments]

        search_pos = 0
        for raw_s in segments:
            s_text = raw_s.strip()
            if not s_text:
                continue

            found_idx = page_text.find(s_text, search_pos)
            if found_idx == -1:
                found_idx = page_text.find(s_text)

            if found_idx != -1:
                start = page_start_offset + found_idx
                end = start + len(s_text)
                sentence_records.append({
                    "idx": sent_idx,
                    "start": start,
                    "end": end,
                    "page": page_num,
                    "text": s_text,
                })
                sent_idx += 1
                search_pos = found_idx + len(s_text)

    return clean_text, sentence_records
