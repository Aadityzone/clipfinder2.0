from ai.services.visual_candidates import multimodal_event_candidates


def test_proposes_candidate_for_visual_event_with_no_speech():
    result = multimodal_event_candidates(
        [],
        {"visual": {"samples": [
            {"time": 20, "visualChange": 0.2, "motion": 0.1},
            {"time": 25, "visualChange": 0.91, "motion": 0.7},
        ]}},
        duration=60,
    )
    assert len(result) == 1
    assert result[0]["start"] == 13
    assert result[0]["end"] == 43
    assert result[0]["text"] == ""
    assert result[0]["features"]["multimodalProposal"] is True
    assert result[0]["features"]["eventKind"] == "visual_change"


def test_proposals_are_bounded_and_respect_source_duration():
    result = multimodal_event_candidates(
        [],
        {"scenes": {"sceneChanges": [1, 3, 30, 50, 70]}},
        duration=55,
        max_candidates=3,
    )
    assert len(result) <= 3
    assert all(row["start"] >= 0 and row["end"] <= 55 for row in result)


def test_ignores_weak_or_missing_media_evidence():
    assert multimodal_event_candidates([], {}, duration=10) == []
    assert multimodal_event_candidates(
        [], {"visual": {"samples": [{"time": 1, "visualChange": 0.1, "motion": 0.2}]}},
        duration=10,
    ) == []
