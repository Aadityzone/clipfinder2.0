from ai.scripts.smoke_pipeline import _captions_for_clip, _number


def test_smoke_caption_cues_are_clipped_and_made_relative_to_clip():
    segments = [
        {"start": 2, "end": 5, "text": "starts before clip"},
        {"start": 4, "end": 7, "text": "crosses clip"},
        {"start": 9, "end": 11, "text": "outside clip"},
        {"start": 8, "end": 8, "text": "invalid interval"},
        {"start": 4, "end": 6, "text": ""},
    ]

    assert _captions_for_clip(segments, 4, 8) == [
        {"start": 0.0, "end": 1.0, "text": "starts before clip"},
        {"start": 0.0, "end": 3.0, "text": "crosses clip"},
    ]


def test_smoke_number_rejects_nan_and_invalid_values():
    assert _number("12.5") == 12.5
    assert _number("nan", 7) == 7
    assert _number("invalid", 3) == 3
