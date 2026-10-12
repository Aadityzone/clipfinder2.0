from ai.services.evaluation import evaluate_by_genre, evaluate_candidates, temporal_iou


def test_temporal_iou_uses_intersection_over_union():
    assert temporal_iou({"start": 0, "end": 10}, {"start": 5, "end": 15}) == 1 / 3


def test_evaluation_rewards_top_ranked_ground_truth_and_ignores_invalid_intervals():
    truth = [
        {"start": 10, "end": 20, "genre": "gaming"},
        {"start": 40, "end": 50, "genre": "podcast"},
    ]
    predictions = [
        {"start": 11, "end": 19, "score": 90},
        {"start": 70, "end": 80, "score": 80},
        {"start": float("nan"), "end": 90, "score": 100},
    ]

    result = evaluate_candidates(predictions, truth, top_k=2, iou_threshold=0.5)

    assert result["predictionCount"] == 2
    assert result["groundTruthCount"] == 2
    assert result["truePositivesAtK"] == 1
    assert result["precisionAtK"] == 0.5
    assert result["recallAtK"] == 0.5


def test_duplicate_predictions_cannot_claim_the_same_ground_truth_twice():
    truth = [{"start": 10, "end": 20}]
    predictions = [
        {"start": 10, "end": 20, "score": 90},
        {"start": 11, "end": 19, "score": 80},
    ]

    result = evaluate_candidates(predictions, truth, top_k=2)

    assert result["truePositivesAtK"] == 1
    assert result["recallAtK"] == 1.0


def test_genre_report_exposes_macro_recall_for_cross_genre_benchmarks():
    truth = [
        {"start": 10, "end": 20, "genre": "gaming"},
        {"start": 40, "end": 50, "genre": "podcast"},
    ]
    predictions = [
        {"start": 10, "end": 20, "score": 90, "genre": "gaming"},
        {"start": 100, "end": 110, "score": 80, "genre": "gaming"},
    ]

    result = evaluate_by_genre(predictions, truth, top_k=2)

    assert result["perGenreRecallAtK"]["gaming"] == 1.0
    assert result["perGenreRecallAtK"]["podcast"] == 0.0
    assert result["macroRecallAtK"] == 0.5


def test_genre_report_does_not_let_one_genres_predictions_claim_another_genres_truth():
    truth = [
        {"start": 10, "end": 20, "genre": "gaming"},
        {"start": 10, "end": 20, "genre": "podcast"},
    ]
    predictions = [{"start": 10, "end": 20, "score": 99, "genre": "gaming"}]

    result = evaluate_by_genre(predictions, truth, top_k=1)

    assert result["perGenreRecallAtK"]["gaming"] == 1.0
    assert result["perGenreRecallAtK"]["podcast"] == 0.0


def test_evaluation_rejects_invalid_k_and_threshold():
    import pytest

    with pytest.raises(ValueError):
        evaluate_candidates([], [], top_k=0)
    with pytest.raises(ValueError):
        evaluate_candidates([], [], iou_threshold=float("nan"))
