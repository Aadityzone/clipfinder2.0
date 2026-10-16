import json

import pytest

from ai.scripts.evaluate_highlights import _load_cases, evaluate_dataset


def test_dataset_evaluator_reports_per_case_and_aggregate_metrics():
    cases = [
        {
            "id": "stream-a",
            "predictions": [
                {"start": 10, "end": 20, "score": 90},
                {"start": 50, "end": 60, "score": 80},
            ],
            "ground_truth": [{"start": 11, "end": 19}],
        },
        {
            "id": "stream-b",
            "predictions": [{"start": 100, "end": 110, "score": 75}],
            "ground_truth": [{"start": 101, "end": 109}],
        },
    ]

    report = evaluate_dataset(cases, top_k=1, iou_threshold=0.5)

    assert report["schemaVersion"] == 1
    assert report["topK"] == 1
    assert [case["id"] for case in report["cases"]] == ["stream-a", "stream-b"]
    assert report["aggregate"]["benchmarkCount"] == 2
    assert report["aggregate"]["matchedCount"] == 2
    assert report["aggregate"]["precisionAtK"] == 1.0
    assert report["aggregate"]["recallAtK"] == 1.0


def test_load_cases_accepts_wrapped_and_bare_lists(tmp_path):
    for payload in [
        {"cases": [{"predictions": [], "ground_truth": []}]},
        [{"predictions": [], "ground_truth": []}],
    ]:
        path = tmp_path / "cases.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert len(_load_cases(path)) == 1


@pytest.mark.parametrize("payload", [
    {},
    {"cases": []},
    {"cases": [{"predictions": []}]},
    {"cases": [None]},
])
def test_load_cases_rejects_invalid_dataset_shapes(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        _load_cases(path)


def test_load_cases_reports_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not read benchmark JSON"):
        _load_cases(path)
