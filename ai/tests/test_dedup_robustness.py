from ai.services.dedup import deduplicate, enforce_temporal_diversity


def test_deduplicate_returns_empty_for_non_list_inputs():
    assert deduplicate(None) == []
    assert deduplicate("not candidates") == []
    assert deduplicate({"start": 0, "end": 1, "score": 100}) == []


def test_deduplicate_drops_malformed_rows_without_crashing():
    result = deduplicate([
        None,
        "bad row",
        {"start": "bad", "end": 3, "score": 90},
        {"start": 0, "end": 4, "score": 70},
    ])
    assert len(result) == 1
    assert result[0]["score"] == 70


def test_enforce_temporal_diversity_returns_empty_on_invalid_input():
    assert enforce_temporal_diversity(None) == []
    assert enforce_temporal_diversity("invalid") == []
    assert enforce_temporal_diversity([]) == []


def test_enforce_temporal_diversity_promotes_spread_across_video():
    candidates = [
        {"start": 10.0, "end": 25.0, "score": 95.0},
        {"start": 40.0, "end": 55.0, "score": 94.0},
        {"start": 70.0, "end": 85.0, "score": 93.0},
        {"start": 90.0, "end": 105.0, "score": 92.0},
        {"start": 300.0, "end": 320.0, "score": 88.0},
    ]
    # With max_per_window=2 in 120s windows:
    # 10s and 40s fit in window 0 (0-120s). 70s and 90s exceed max_per_window=2, so they are deferred.
    # 300s is in window 2 (240-360s), so it is selected into the primary diverse tier.
    diversified = enforce_temporal_diversity(
        candidates,
        min_spacing_seconds=15.0,
        max_per_window=2,
        window_size_seconds=120.0,
    )
    assert len(diversified) == 5
    scores = [c["score"] for c in diversified]
    assert scores[:3] == [95.0, 94.0, 88.0]
    assert scores[3:] == [93.0, 92.0]


def test_enforce_temporal_diversity_respects_min_spacing():
    candidates = [
        {"start": 10.0, "end": 25.0, "score": 95.0},
        {"start": 14.0, "end": 28.0, "score": 90.0},  # spacing only 4s (< 15s)
        {"start": 50.0, "end": 65.0, "score": 85.0},
    ]
    diversified = enforce_temporal_diversity(candidates, min_spacing_seconds=15.0)
    scores = [c["score"] for c in diversified]
    assert scores == [95.0, 85.0, 90.0]


def test_enforce_temporal_diversity_handles_malformed_items():
    candidates = [
        None,
        {"start": "bad", "end": 10, "score": 90.0},
        {"start": 20.0, "end": 35.0, "score": 80.0},
    ]
    result = enforce_temporal_diversity(candidates)
    assert len(result) == 2  # one valid candidate and one malformed interval candidate preserved in deferred
