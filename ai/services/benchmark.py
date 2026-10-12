"""CLI to evaluate saved Clip Finder candidates against curated temporal labels.

Manifest: {"version": 1, "cases": [{"id": "...", "genre": "...",
"predictions": [{"start": 12, "end": 35, "score": 84}],
"groundTruth": [{"start": 16, "end": 31}]}]}

Each case is a separate source video. Metrics are computed per video first, then
averaged by genre; timestamps from different videos are never matched together.
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
    from ai.services.evaluation import evaluate_candidates
    from ai.services.temporal_ranking import rank_candidates
except ImportError:  # Support running from ai/ as the working directory.
    from services.evaluation import evaluate_candidates
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


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def run_benchmark(manifest: dict, top_k: int = 10, iou_threshold: float = 0.5) -> dict:
    """Compare original and deterministic-reranked scores per video and genre."""
    cases_out = []
    genre_before: dict[str, list[float]] = {}
    genre_after: dict[str, list[float]] = {}

    for case in manifest["cases"]:
        genre = case["genre"].strip().lower()
        original = copy.deepcopy(case["predictions"])
        reranked = rank_candidates(copy.deepcopy(original))
        truth = copy.deepcopy(case["groundTruth"])
        before = evaluate_candidates(original, truth, top_k, iou_threshold)
        after = evaluate_candidates(reranked, truth, top_k, iou_threshold)
        genre_before.setdefault(genre, []).append(before["recallAtK"])
        genre_after.setdefault(genre, []).append(after["recallAtK"])
        cases_out.append({
            "id": case["id"],
            "genre": genre,
            "before": before,
            "after": after,
        })

    before_per_genre = {genre: _mean(values) for genre, values in sorted(genre_before.items())}
    after_per_genre = {genre: _mean(genre_after[genre]) for genre in sorted(genre_after)}
    return {
        "manifestVersion": manifest["version"],
        "caseCount": len(cases_out),
        "topK": top_k,
        "iouThreshold": iou_threshold,
        "baseline": {
            "perGenreMeanRecallAtK": before_per_genre,
            "macroRecallAtK": _mean(list(before_per_genre.values())),
        },
        "reranked": {
            "perGenreMeanRecallAtK": after_per_genre,
            "macroRecallAtK": _mean(list(after_per_genre.values())),
        },
        "cases": cases_out,
        "interpretation": (
            "Offline metrics on supplied human-curated labels only. Results are averaged "
            "per video before genre aggregation; timestamps from different videos are not "
            "compared. A difference is not generalizable without a representative held-out set."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Path to a version-1 JSON benchmark manifest")
    parser.add_argument("--top-k", type=int, default=10, help="Ranked candidates evaluated per video (default: 10)")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="Temporal IoU match threshold (default: 0.5)")
    parser.add_argument("--output", help="Optional path to write JSON results; stdout otherwise")
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not math.isfinite(args.iou_threshold) or not 0 <= args.iou_threshold <= 1:
        parser.error("--iou-threshold must be between 0 and 1")
    try:
        report = run_benchmark(load_manifest(args.manifest), args.top_k, args.iou_threshold)
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
