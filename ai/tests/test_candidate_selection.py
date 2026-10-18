from ai.services.candidate_selection import select_temporally_diverse


def test_temporal_selection_spreads_top_results_across_long_video():
    candidates = [
        {"start": 1, "end": 11, "score": 99, "id": "near-a"},
        {"start": 5, "end": 15, "score": 97, "id": "near-b"},
        {"start": 9, "end": 19, "score": 95, "id": "near-c"},
        {"start": 120, "end": 130, "score": 90, "id": "later"},
    ]

    result = select_temporally_diverse(candidates, limit=3, min_center_distance=30)

    assert [row["id"] for row in result] == ["near-a", "near-b", "later"]
    assert "near-c" not in [row["id"] for row in result]


def test_temporal_selection_backfills_when_video_has_few_distinct_moments():
    candidates = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 2, "end": 12, "score": 80},
        {"start": 4, "end": 14, "score": 70},
    ]

    result = select_temporally_diverse(candidates, limit=3, min_center_distance=100)

    assert len(result) == 3
    assert [row["score"] for row in result] == [90, 80, 70]


def test_temporal_selection_ignores_malformed_intervals_and_non_finite_scores():
    candidates = [
        {"start": 0, "end": 10, "score": 90, "id": "valid"},
        {"start": float("nan"), "end": 20, "score": 100, "id": "nan-start"},
        {"start": 10, "end": 10, "score": 99, "id": "zero-duration"},
        {"start": 20, "end": 30, "score": float("inf"), "id": "infinite-score"},
    ]

    result = select_temporally_diverse(candidates, limit=10)

    assert [row["id"] for row in result] == ["valid"]


def test_temporal_selection_does_not_mutate_input_and_handles_limits():
    candidates = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 60, "end": 70, "score": 80},
    ]
    original = [dict(row) for row in candidates]

    assert select_temporally_diverse(candidates, limit=0) == []
    assert select_temporally_diverse(candidates, limit=1) == [candidates[0]]
    assert candidates == original
    assert select_temporally_diverse(None) == []
