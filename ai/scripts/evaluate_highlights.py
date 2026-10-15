"""Evaluate one benchmark or a directory of human-labelled highlight benchmarks.

Each JSON file contains predictions and ground_truth timestamp ranges, with an
optional genre field. Directory mode reports per-file, per-genre, and aggregate
metrics; it never creates synthetic labels or claims accuracy without labels.

Run from repository root:
  PYTHONPATH=. python ai/scripts/evaluate_highlights.py benchmark.json
  PYTHONPATH=. python ai/scripts/evaluate_highlights.py benchmarks/ --recursive
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai.services.evaluation import aggregate_evaluation_reports, evaluate_ranked_candidates


def _load_benchmark(path: Path, *, top_k: int, iou: float) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: benchmark root must be a JSON object")
    predictions = payload.get("predictions")
    ground_truth = payload.get("ground_truth")
    if not isinstance(predictions, list) or not isinstance(ground_truth, list):
        raise ValueError(f"{path}: expected predictions and ground_truth arrays")
    if not all(isinstance(item, dict) for item in predictions + ground_truth):
        raise ValueError(f"{path}: predictions and ground_truth entries must be objects")

    report = evaluate_ranked_candidates(
        predictions, ground_truth, top_k=top_k, iou_threshold=iou
    )
    report["benchmark"] = str(path)
    genre = payload.get("genre")
    report["genre"] = str(genre).strip().lower() if genre else "unspecified"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "benchmark",
        type=Path,
        help="JSON benchmark file or directory containing benchmark JSON files",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="search benchmark directories recursively",
    )
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not 0 <= args.iou <= 1:
        parser.error("--iou must be between 0 and 1")
    if not args.benchmark.exists():
        parser.error(f"benchmark path does not exist: {args.benchmark}")

    if args.benchmark.is_file():
        paths = [args.benchmark]
    elif args.benchmark.is_dir():
        paths = sorted(
            args.benchmark.rglob("*.json")
            if args.recursive
            else args.benchmark.glob("*.json")
        )
    else:
        parser.error("benchmark path must be a JSON file or directory")
        return 2

    if not paths:
        parser.error(f"no JSON benchmark files found in {args.benchmark}")

    try:
        reports = [
            _load_benchmark(path, top_k=args.top_k, iou=args.iou)
            for path in paths
        ]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    # Preserve the original single-file output contract for existing workflows.
    if args.benchmark.is_file():
        print(json.dumps(reports[0], indent=2, sort_keys=True))
        return 0

    by_genre: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        by_genre.setdefault(report["genre"], []).append(report)
    genre_reports = {
        genre: aggregate_evaluation_reports(items)
        for genre, items in sorted(by_genre.items())
    }
    output = {
        "benchmarkCount": len(reports),
        "topK": args.top_k,
        "iouThreshold": args.iou,
        "benchmarks": reports,
        "byGenre": genre_reports,
        "overall": aggregate_evaluation_reports(reports),
        "notes": [
            "Metrics are meaningful only when ground_truth ranges are human-labelled.",
            "Overall metrics are micro-aggregated; byGenre metrics include macro averages.",
            "A benchmark's genre is read from its JSON genre field, or marked unspecified.",
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
