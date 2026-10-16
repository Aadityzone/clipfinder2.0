from ai.services.dedup import deduplicate


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
