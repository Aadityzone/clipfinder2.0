"""Evaluate ranked highlight predictions against a small human-labelled JSON dataset.

Input JSON format:
{
  "cases": [
    {"id": "video-1", "predictions": [{"start": 12, "end": 25, "score": 87}],
     "ground_truth": [{"start": 14, "end": 24}]}
  ]
}

An optional per-case `media_duration` (seconds) enables label-free coverage and
clustering diagnostics. Ground truth is required for precision/recall; the
diagnostics block is descriptive and must not be reported as accuracy.

Run from repository root:
  python -m ai.scripts.evaluate_highlights --input ai/benchmarks/example.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from ai.services.evaluation import (
    aggregate_evaluation_reports,
    aggregate_selection_diagnostics,
    evaluate_ranked_candidates,
    selection_diagnostics,
)


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read benchmark JSON at {path}: {exc}") from exc
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark input must be a non-empty list or an object with a non-empty 'cases' list.")
    valid = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Benchmark case {index} must be an object.")
        predictions, labels = case.get("predictions"), case.get("ground_truth")
        if not isinstance(predictions, list) or not isinstance(labels, list):
            raise ValueError(f"Benchmark case {index} must include 'predictions' and 'ground_truth' lists.")
        valid.append({
            "id": str(case.get("id") or case.get("name") or f"case-{index + 1}"),
            "genre": str(case.get("genre") or "unknown").strip().lower() or "unknown",
            "media_duration": _positive_float(case.get("media_duration", case.get("duration"))),
            "predictions": predictions,
            "ground_truth": labels,
        })
    return valid


def evaluate_dataset(
    cases: list[dict[str, Any]], *, top_k: int = 10, iou_threshold: float = 0.5
) -> dict[str, Any]:
    reports = []
    diagnostics = []
    genre_reports: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        metrics = evaluate_ranked_candidates(
            case["predictions"], case["ground_truth"],
            top_k=top_k, iou_threshold=iou_threshold,
        )
        genre = str(case.get("genre") or "unknown").strip().lower() or "unknown"
        # Structural diagnostics describe the whole ranked candidate set (not just
        # top_k) and need no labels. They are reported alongside, never as quality.
        structural = selection_diagnostics(
            case["predictions"],
            media_duration=_positive_float(case.get("media_duration")),
        )
        case_report = {"id": case["id"], "genre": genre, **metrics, "diagnostics": structural}
        reports.append(case_report)
        diagnostics.append(structural)
        genre_reports.setdefault(genre, []).append(metrics)
    aggregate = aggregate_evaluation_reports(reports)
    by_genre = {
        genre: aggregate_evaluation_reports(metrics)
        for genre, metrics in sorted(genre_reports.items())
    }
    return {
        "schemaVersion": 1,
        "method": "greedy interval-IoU matching; one prediction per ground-truth moment",
        "topK": max(1, int(top_k)),
        "requestedIoUThreshold": iou_threshold if math.isfinite(iou_threshold) else 0.5,
        "cases": reports,
        "aggregate": aggregate,
        "structural": aggregate_selection_diagnostics(diagnostics),
        "structuralNote": (
            "Label-free shape metrics (duplication, coverage, clustering) measured over "
            "predictions in the listed (delivered) order. They measure the selection's "
            "structure, not whether the chosen moments are good highlights."
        ),
        "byGenre": by_genre,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON file with ranked predictions and human-labelled intervals")
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report (stdout if omitted)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of highest-scoring predictions to evaluate")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="Minimum temporal intersection-over-union for a match")
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not math.isfinite(args.iou_threshold) or not 0 <= args.iou_threshold <= 1:
        parser.error("--iou-threshold must be finite and between 0 and 1")
    try:
        report = evaluate_dataset(_load_cases(args.input), top_k=args.top_k, iou_threshold=args.iou_threshold)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
