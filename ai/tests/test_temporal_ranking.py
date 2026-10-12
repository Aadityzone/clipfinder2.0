from ai.services.temporal_ranking import rank_candidates


def test_multimodal_agreement_is_recorded_and_can_help_equal_candidates():
    candidates = [
        {"start": 10, "end": 25, "score": 70, "text": "A normal spoken sentence.",
         "features": {"audioEnergy": 0.2}},
        {"start": 30, "end": 45, "score": 70, "text": "A normal spoken sentence.",
         "features": {"audioEnergy": 0.8, "visualChange": 0.9, "motion": 0.7,
                      "onScreenActionLabels": ["combat"]}},
    ]

    ranked = rank_candidates(candidates)

    assert ranked[0]["start"] == 30
    diagnostics = ranked[0]["features"]["temporalRanking"]
    assert diagnostics["version"] == 1
    assert diagnostics["modalityCount"] == 3
    assert diagnostics["modalities"] == ["audio", "on_screen", "visual"]
    assert ranked[0]["score"] <= 100


def test_silent_visual_candidate_is_not_penalized_for_missing_transcript_or_audio():
    candidates = [{
        "start": 0, "end": 12, "score": 60, "text": "",
        "features": {"visualChange": 0.9, "motion": 0.8,
                     "onScreenActionLabels": ["victory"]},
    }]

    ranked = rank_candidates(candidates)

    assert len(ranked) == 1
    diagnostics = ranked[0]["features"]["temporalRanking"]
    assert "transcript" not in diagnostics["signals"]
    assert "audio" not in diagnostics["modalities"]
    assert diagnostics["modalityCount"] == 2


def test_story_signal_and_original_score_both_contribute():
    candidates = [
        {"start": 0, "end": 15, "score": 80, "text": "wait what happened?!",
         "features": {"story": {"hook": 0.9, "tension": 0.8, "payoff": 0.9,
                                "completeness": 0.8, "conversational": 0.8}}},
        {"start": 20, "end": 35, "score": 80, "text": "ordinary words here",
         "features": {"story": {"hook": 0.1, "tension": 0.1, "payoff": 0.1,
                                "completeness": 0.1, "conversational": 0.1}}},
    ]

    ranked = rank_candidates(candidates)

    assert ranked[0]["start"] == 0
    assert ranked[0]["features"]["temporalRanking"]["signals"]["story"] > 0.7


def test_invalid_candidates_are_dropped_and_non_finite_scores_are_safe():
    ranked = rank_candidates([
        {"start": 0, "end": 0, "score": 100},
        {"start": -1, "end": 2, "score": 100},
        {"start": 2, "end": 5, "score": float("nan"), "text": ""},
    ])

    assert len(ranked) == 1
    assert ranked[0]["score"] == 0
    assert ranked[0]["features"]["temporalRanking"]["finalScore"] == 0


def test_ranking_is_deterministic_for_equal_scores():
    candidates = [
        {"start": 0, "end": 10, "score": 50, "text": ""},
        {"start": 20, "end": 30, "score": 50, "text": ""},
    ]

    ranked = rank_candidates(candidates)

    assert [item["start"] for item in ranked] == [0, 20]
