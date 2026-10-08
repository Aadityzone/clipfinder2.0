from ai.services.story_intelligence import _punctuated_word_bounds


def test_word_boundary_snaps_to_sentence_end():
    segments = [{
        "start": 0,
        "end": 8,
        "text": "Hello world. Next thought",
        "words": [
            {"start": 0, "end": 1, "word": "Hello"},
            {"start": 1, "end": 2, "word": "world."},
            {"start": 3, "end": 4, "word": "Next"},
            {"start": 4, "end": 5, "word": "thought"},
        ],
    }]
    start, end = _punctuated_word_bounds(segments, 2.0, 4.0)
    assert start == 2.0
    assert end == 3.0
