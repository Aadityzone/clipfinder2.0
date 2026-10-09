from ai.services.creator_feedback import apply_creator_preferences


def test_creator_preferences_boost_matching_features_with_bounded_adjustment():
    candidates = [
        {"score": 60, "features": {"gameplayLikeRatio": 1.0}},
        {"score": 60, "features": {"gameplayLikeRatio": 0.0}},
    ]

    ranked = apply_creator_preferences(candidates, {"gameplay": 1.0})

    assert ranked[0]["score"] > 60
    assert ranked[1]["score"] < 60
    assert ranked[0]["features"]["creatorFeedback"]["applied"] is True
    assert ranked[0]["features"]["creatorFeedback"]["signalsUsed"] == 1


def test_creator_preferences_are_bounded_and_scores_stay_in_range():
    candidates = [{"score": 99, "features": {"gameplayLikeRatio": 1.0}}]

    ranked = apply_creator_preferences(candidates, {"gameplay": 1.0})

    assert ranked[0]["score"] <= 100
    assert ranked[0]["features"]["creatorFeedback"]["scoreAdjustment"] <= 5


def test_empty_creator_profile_does_not_change_scores_or_claim_learning():
    candidates = [{"score": 42, "features": {"gameplayLikeRatio": 1.0}}]

    ranked = apply_creator_preferences(candidates, {})

    assert ranked[0]["score"] == 42
    assert "creatorFeedback" not in ranked[0]["features"]


def test_unknown_or_non_numeric_preference_is_ignored():
    candidates = [{"score": 42, "features": {"gameplayLikeRatio": 1.0}}]

    ranked = apply_creator_preferences(candidates, {"made_up": 1, "gameplay": "not-a-number"})

    assert ranked[0]["score"] == 42
