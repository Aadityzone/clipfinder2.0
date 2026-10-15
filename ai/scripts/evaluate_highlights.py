"""Evaluate ranked Clip Finder candidates against human-labelled timestamp ranges.

Input JSON format:
{
  "predictions": [{"start": 10, "end": 25, "score": 92}],
  "ground_truth": [{"start": 12, "end": 24, "label": "clutch"}]
}

Run from repository root:
  PYTHONPATH=. python ai/scripts/evaluate_highlights.py benchmark.json --top-k 10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.services.evaluation import evaluate_ranked_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path, help="JSON file with predictions and ground_truth")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args()

    payload = json.loads(args.benchmark.read_text(encoding="utf-8"))
    predictions = payload.get("predictions")
    ground_truth = payload.get("ground_truth")
    if not isinstance(predictions, list) or not isinstance(ground_truth, list):
        parser.error("benchmark JSON must contain predictions and ground_truth arrays")

    report = evaluate_ranked_candidates(
        predictions, ground_truth, top_k=args.top_k, iou_threshold=args.iou
    )
    report["benchmark"] = str(args.benchmark)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
