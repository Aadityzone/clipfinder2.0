import json

import pytest

from ai.services.benchmark import load_manifest, run_benchmark


def _manifest():
    return {
        "version": 1,
        "cases": [
            {
                "id": "gaming-a",
                "genre": "gaming",
                "predictions": [
                    {"start": 10, "end": 20, "score": 20},
                    {"start": 40, "end": 50, "score": 90},
                ],
                "groundTruth": [{"start": 10, "end": 20}],
            },
            {
                "id": "gaming-b",
                "genre": "gaming",
                "predictions": [{"start": 100, "end": 110, "score": 90}],
                "groundTruth": [{"start": 100, "end": 110}],
            },
            {
                "id": "podcast-a",
                "genre": "podcast",
                "predictions": [{"start": 5, "end": 15, "score": 80}],
                "groundTruth": [{"start": 5, "end": 15}],
            },
        ],
    }


def test_manifest_loads_and_benchmark_reports_per_video_and_genre(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")

    report = run_benchmark(load_manifest(path), top_k=1)

    assert report["caseCount"] == 3
    assert report["baseline"]["perGenreMeanRecallAtK"]["gaming"] == 0.5
    assert report["baseline"]["perGenreMeanRecallAtK"]["podcast"] == 1.0
    assert report["baseline"]["macroRecallAtK"] == 0.75
    assert [case["id"] for case in report["cases"]] == [
        "gaming-a", "gaming-b", "podcast-a"
    ]
    assert "timestamps from different videos are not compared" in report["interpretation"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(version=2), "version: 1"),
        (lambda data: data.update(cases=[]), "non-empty cases"),
        (lambda data: data["cases"][0].update(id=""), "non-empty string"),
        (lambda data: data["cases"][0].update(genre=" "), "genre"),
        (lambda data: data["cases"][0].update(groundTruth=[]), "labelled moment"),
        (lambda data: data["cases"][0]["predictions"].append({"start": 5, "end": 5}), "invalid intervals"),
    ],
)
def test_manifest_rejects_invalid_input(tmp_path, mutation, message):
    data = _manifest()
    mutation(data)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_manifest(path)


def test_manifest_rejects_duplicate_video_ids(tmp_path):
    data = _manifest()
    data["cases"][1]["id"] = data["cases"][0]["id"]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate case id"):
        load_manifest(path)
