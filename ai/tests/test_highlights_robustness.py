import math

from ai.highlights import _window_text, candidates, score


def test_window_text_skips_malformed_transcript_rows():
    segments = [
        None,
        {"start": "bad", "end": 4, "text": "broken"},
        {"start": 5, "end": 2, "text": "reversed"},
        {"start": 1, "end": 3, "text": "valid transcript words"},
    ]
    assert _window_text(segments, 0, 4) == "valid transcript words"


def test_window_text_restores_chronological_order_for_unsorted_transcript_rows():
    segments = [
        {"start": 8, "end": 10, "text": "the payoff"},
        {"start": 2, "end": 4, "text": "the setup"},
        {"start": 5, "end": 7, "text": "then the turn"},
    ]
    assert _window_text(segments, 0, 12) == "the setup then the turn the payoff"


def test_candidates_ignore_invalid_transcript_and_media_rows():
    segments = [
        None,
        {"start": "nan", "end": 4, "text": "bad timestamp"},
        {"start": 1, "end": 5, "text": "Wow, this is a genuinely crazy moment with a surprising payoff!"},
        {"start": 2, "end": 6, "text": "Bro, that was hilarious and absolutely unexpected!"},
    ]
    media = {
        "vision": {"faces": [None, {"time": "bad", "x": "nan"}]},
        "scenes": {"sceneChanges": [None, "invalid", 3]},
        "audioWindows": [None, {"start": 0, "end": 5, "energy": "nan"}],
        "visual": {"samples": [None, {"time": 3, "visualChange": "nan", "motion": 0.2}]},
        "onScreen": {"samples": [None, {"time": 3, "actionLabels": ["combat"]}]},
        "visualSemantic": [None, {"time": 3, "score": "invalid"}],
    }
    result = candidates(segments, media=media)
    assert result
    assert all(math.isfinite(item["score"]) for item in result)
    assert all(item["end"] > item["start"] for item in result)


def test_score_handles_empty_text_and_zero_length_windows():
    assert math.isfinite(score("", 2, 2))
