import math

from ai.highlights import candidates
from ai.services.dedup import deduplicate
from ai.services.story_intelligence import optimize_candidates

def test_candidates_keep_text_and_context_features():
    segments = [
        {"start": 10, "end": 14, "text": "Wait, you are telling me this actually happened? No way!"},
        {"start": 15, "end": 20, "text": "And then everyone started laughing because it was completely unexpected."},
    ]
    result = candidates(segments, "find surprising funny moments", ["ai_detect"], {
        "audio": {},
        "scenes": {"sceneChanges": [13.0]},
        "vision": {"faces": [{"time": 12, "x": .7}]},
    })
    assert result
    assert result[0]["text"]
    assert result[0]["features"]["faceHits"] == 1
    assert result[0]["features"]["sceneHits"] == 1

def test_dedup_prefers_highest_score():
    items = [
        {"start": 0, "end": 10, "score": 60},
        {"start": 1, "end": 9, "score": 90},
        {"start": 30, "end": 40, "score": 50},
    ]
    result = deduplicate(items, threshold=.55)
    assert [x["score"] for x in result] == [90, 50]


def test_candidate_times_are_finite_and_capped_to_media_duration():
    segments = [
        {"start": 0, "end": 10, "text": "This surprising story actually happened to everyone."},
        {"start": math.nan, "end": 12, "text": "Invalid transcript timestamps should be skipped."},
        {"start": True, "end": 12, "text": "Boolean timestamps should also be skipped."},
        {"start": 11, "end": 14, "text": "This segment extends past the actual media duration."},
    ]

    result = candidates(segments, media={"durationS": 12})

    assert result
    assert all(math.isfinite(item["start"]) and math.isfinite(item["end"]) for item in result)
    assert all(0 <= item["start"] < item["end"] <= 12 for item in result)


def test_dedup_collapses_same_moment_when_iou_is_low_but_shorter_window_is_covered():
    items = [
        {"start": 0, "end": 10, "score": 80, "text": "strong moment"},
        {"start": 4, "end": 14, "score": 70, "text": "same moment with shifted context"},
        {"start": 20, "end": 30, "score": 60, "text": "separate moment"},
    ]

    result = deduplicate(items, threshold=.55)

    assert [item["text"] for item in result] == ["strong moment", "separate moment"]


def test_dedup_keeps_short_distinct_moment_inside_longer_candidate():
    items = [
        {"start": 18, "end": 30, "score": 80, "text": "long context"},
        {"start": 20, "end": 25, "score": 70, "text": "short distinct moment"},
    ]

    result = deduplicate(items, threshold=.55)

    assert [item["text"] for item in result] == ["long context", "short distinct moment"]


def test_dedup_discards_invalid_intervals_and_nonfinite_scores():
    invalid = {"start": math.nan, "end": 10, "score": 100}
    boolean_time = {"start": True, "end": 10, "score": 100}
    nonfinite_score = {"start": 0, "end": 5, "score": math.inf}
    result = deduplicate([invalid, boolean_time, nonfinite_score])

    assert result == [nonfinite_score]


def test_story_optimization_uses_only_normalized_transcript_segments():
    segments = [
        {"start": float("nan"), "end": 40, "text": "invalid"},
        {"start": 2, "end": 20, "text": "A valid story has a beginning and a clear payoff."},
    ]
    items = [{"start": 2, "end": 20, "score": 70, "features": {}}]

    result = optimize_candidates(segments, items)

    assert len(result) == 1
    assert result[0]["start"] == 2
    assert result[0]["end"] == 20
