"""Test sentence segmentation and character offset accuracy."""

from backend.app.services.sentences import segment_sentences


def test_segment_sentences_offset_equality() -> None:
    """Verify that for every sentence, clean_text[start:end] strictly equals the sentence text."""
    pages = [
        {
            "page": 1,
            "text": "Can machines think? This should begin with definitions. The new form is a game.",
        },
        {
            "page": 2,
            "text": "Digital computers can simulate any discrete state machine. They are universal machines.",
        },
    ]

    clean_text, sentences = segment_sentences(pages)
    assert len(sentences) == 5

    for s in sentences:
        start = s["start"]
        end = s["end"]
        assert start < end
        assert clean_text[start:end] == s["text"]
        assert s["page"] in (1, 2)
