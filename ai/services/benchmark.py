"""CLI to evaluate saved Clip Finder candidates against curated temporal labels.

Manifest format:
{
  "version": 1,
  "cases": [
    {
      "id": "gaming-session-01",
      "genre": "gaming",
      "predictions": [{"start": 12.0, "end": 35.0, "score": 84.0}],
      "groundTruth": [{"start": 16.0, "end": 31.0}]
    }
  ]
}

The runner reports the provided scores and scores after the deterministic ranker.
It never invents labels or treats sample data as evidence of model quality.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from ai.services.evaluation import evaluate_by_genre, evaluate_candidates
    from ai.services.temporal_ranking import rank_candidates
except ImportError:  # Support running from ai/ as the working directory.
    from services.evaluation import evaluate_by_genre, evaluate_candidates
    from services.temporal_ranking import rank_candidates


def _valid_interval(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    try:
        start, end = float(item["start"]), float(item["end"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(start) and math.isfinite(end) and start >= 0 and end > start


def load_manifest(path: str | Path) -> dict:
    """Load and validate a benchmark manifest without silently dropping cases."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read benchmark manifest: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("manifest must be an object with version: 1")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain a non-empty cases array")

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"cases[{index}].id must be a non-empty string")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(case.get("genre"), str) or not case["genre"].strip():
            raise ValueError(f"cases[{index}].genre must be a non-empty string")
        for field in ("predictions", "groundTruth"):
            items = case.get(field)
            if not isinstance(items, list):
                raise ValueError(f"cases[{index}].{field} must be an array")
            invalid = [j for j, item in enumerate(items) if not _valid_interval(item)]
            if invalid:
                raise ValueError(
                    f"cases[{index}].{field} contains invalid intervals at indexes {invalid}"
                )
        if not case["groundTruth"]:
            raise ValueError(f"cases[{index}].groundTruth must contain at least one labelled moment")
    return data


def run_benchmark(manifest: dict, top_k: int = 10, iou_threshold: float = 0.5) -> dict:
    """Compare saved ranking scores with deterministic reranking, by case and genre."""
    cases_out = []
    before_predictions: list[dict] = []
    after_predictions: list[dict] = []
    all_truth: list[dict] = []
    genre_truth: dict[str, list[dict]] = {}

    for case in manifest["cases"]:
        genre = case["genre"].strip().lower()
        original = copy.deepcopy(case["predictions"])
        reranked = rank_candidates(copy.deepcopy(original))
        truth = copy.deepcopy(case["groundTruth"])
        before_metrics = evaluate_candidates(original, truth, top_k, iou_threshold)
        after_metrics = evaluate_candidates(reranked, truth, top_k, iou_threshold)
        cases_out.append({
            "id": case["id"],
            "genre": genre,
            "before": before_metrics,
            "after": after_metrics,
        })
        before_predictions.extend({**p, "genre": genre} for p in original)
        after_predictions.extend({**p, "genre": genre} for p in reranked)
        all_truth.extend({**t, "genre": genre} for t in truth)
        genre_truth.setdefault(genre, []).extend(truth)

    before_by_genre = evaluate_by_genre(before_predictions, all_truth, top_k, iou_threshold)
    after_by_genre = evaluate_by_genre(after_predictions, all_truth, top_k, iou_threshold)
    return {
        "manifestVersion": manifest["version"],
        "caseCount": len(cases_out),
        "topK": top_k,
        "iouThreshold": iou_threshold,
        "baseline": {
            "perGenre": before_by_genre["perGenreRecallAtK"],
            "macroRecallAtK": before_by_genre["macroRecallAtK"],
        },
        "reranked": {
            "perGenre": after_by_genre["perGenreRecallAtK"],
            "macroRecallAtK": after_by_genre["macroRecallAtK"],
        },
        "cases": cases_out,
        "interpretation": (
            "Offline metrics on supplied human-curated labels only. A positive or negative "
            "difference is not generalizable without a representative, held-out dataset."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Path to a version-1 JSON benchmark manifest")
    parser.add_argument("--top-k", type=int, default=10, help="Ranked candidates evaluated per case (default: 10)")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="Temporal IoU match threshold (default: 0.5)")
    parser.add_argument("--output", help="Optional path to write JSON results; stdout otherwise")
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not math.isfinite(args.iou_threshold) or not 0 <= args.iou_threshold <= 1:
        parser.error("--iou-threshold must be between 0 and 1")
    try:
        manifest = load_manifest(args.manifest)
        report = run_benchmark(manifest, args.top_k, args.iou_threshold)
    except ValueError as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        try:
            Path(args.output).write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"benchmark error: could not write output: {exc}", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
