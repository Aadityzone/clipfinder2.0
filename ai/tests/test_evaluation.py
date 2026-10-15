from ai.services.evaluation import evaluate_ranked_candidates, interval_iou


def test_interval_iou_for_overlapping_and_disjoint_ranges():
    assert interval_iou({"start": 0, "end": 10}, {"start": 5, "end": 15}) == 1 / 3
    assert interval_iou({"start": 0, "end": 3}, {"start": 5, "end": 8}) == 0


def test_ranked_evaluation_matches_each_label_at_most_once():
    predictions = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 1, "end": 9, "score": 80},
        {"start": 30, "end": 40, "score": 70},
    ]
    labels = [{"start": 0, "end": 10}, {"start": 30, "end": 40}]
    result = evaluate_ranked_candidates(predictions, labels, top_k=3, iou_threshold=0.5)
    assert result["matchedCount"] == 2
    assert result["precisionAtK"] == round(2 / 3, 4)
    assert result["recallAtK"] == 1.0
    assert result["f1AtK"] == round(0.8, 4)


def test_evaluation_handles_empty_and_invalid_inputs():
    result = evaluate_ranked_candidates(
        [{"start": 2, "end": 2, "score": 100}, {"start": 0, "end": 5, "score": 20}],
        [],
    )
    assert result["validPredictionCount"] == 1
    assert result["groundTruthCount"] == 0
    assert result["precisionAtK"] == 0
    assert result["recallAtK"] == 0
