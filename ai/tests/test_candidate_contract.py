from ai.services.candidate_contract import validate_candidates


def test_contract_rejects_non_finite_and_invalid_intervals():
    result = validate_candidates([
        {"start": 0, "end": 4, "score": 70, "text": "valid moment"},
        {"start": 5, "end": 5, "score": 60, "text": "zero duration"},
        {"start": float("nan"), "end": 8, "score": 60, "text": "bad start"},
        {"start": 8, "end": 10, "score": float("inf"), "text": "bad score"},
    ])
    assert len(result) == 1
    assert result[0]["duration"] == 4


def test_contract_clamps_interval_to_source_duration_and_score_range():
    result = validate_candidates([
        {"start": -2, "end": 15, "score": 140, "text": "source boundary"},
    ], media_duration=10)
    assert len(result) == 1
    assert result[0]["start"] == 0
    assert result[0]["end"] == 10
    assert result[0]["duration"] == 10
    assert result[0]["score"] == 100


def test_contract_rejects_candidates_starting_after_source_end():
    result = validate_candidates([
        {"start": 11, "end": 15, "score": 70, "text": "outside source"},
    ], media_duration=10)
    assert result == []


def test_contract_allows_visual_only_candidate_with_feature_evidence():
    result = validate_candidates([
        {"start": 3, "end": 8, "score": 62, "text": "",
         "features": {"sceneHits": 2, "visualChange": 0.8}},
    ])
    assert len(result) == 1
    assert result[0]["text"] == ""


def test_contract_returns_empty_for_non_collection_inputs():
    assert validate_candidates(None) == []
    assert validate_candidates("not a candidate list") == []
    assert validate_candidates({"start": 0, "end": 1, "score": 1}) == []


def test_contract_accepts_iterators_and_skips_bad_rows():
    rows = iter([
        None,
        {"start": 1, "end": 3, "score": 80, "text": "real candidate"},
    ])
    result = validate_candidates(rows, media_duration=5)
    assert len(result) == 1
    assert result[0]["start"] == 1
