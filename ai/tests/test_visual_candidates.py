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



def test_nonpositive_candidate_limit_returns_no_proposals():
    media = {"scenes": {"sceneChanges": [5, 15]}}
    assert multimodal_event_candidates([], media, duration=30, max_candidates=0) == []
    assert multimodal_event_candidates([], media, duration=30, max_candidates=-2) == []


def test_malformed_media_rows_are_ignored_instead_of_crashing():
    result = multimodal_event_candidates(
        [],
        {
            "visual": {"samples": [None, {"time": 10, "visualChange": 0.95, "motion": 0.1}]},
            "audioWindows": [None, {"start": 11, "end": 12, "energy": 0.9}],
            "scenes": {"sceneChanges": [None, 12]},
            "onScreen": {"samples": [None, {"time": 13, "actionLabels": ["combat"]}]},
            "vision": {"faces": [None, {"time": 14, "x": 0.5}]},
        },
        duration=30,
    )
    assert result
    assert all(row["start"] >= 0 and row["end"] <= 30 for row in result)


def test_events_after_source_duration_are_ignored():
    result = multimodal_event_candidates(
        [],
        {"scenes": {"sceneChanges": [100]}},
        duration=30,
    )
    assert result == []
