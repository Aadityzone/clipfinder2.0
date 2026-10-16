"""Run a real local Clip Finder pipeline smoke test against a source video.

This command exercises source probing, transcription, multimodal analysis,
ranking, and actual MP4 rendering. It deliberately does not use mocked model
outputs. A configured LLM provider is optional; deterministic ranking remains
available without one.

Examples (run from repository root):
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --source sample.mp4
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --url "https://www.youtube.com/watch?v=..." --genre gaming
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --source sample.mp4 --out-dir ./artifacts/ai-smoke --top 3

Requirements: AI Python dependencies, FFmpeg/ffprobe, and model weights for
faster-whisper. Video URLs must be from supported providers and usage must
comply with the source platform's terms and rights.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from ai.main import AnalyzeRequest, analyze
from ai.services.download import download
from ai.services.media import ffprobe
from ai.services.render import render
from ai.transcribe import transcribe


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return result if math.isfinite(result) else fallback


def _captions_for_clip(segments: list[dict], start: float, end: float) -> list[dict]:
    cues = []
    for segment in segments:
        seg_start = _number(segment.get("start"), -1)
        seg_end = _number(segment.get("end"), -1)
        text = str(segment.get("text") or "").strip()
        if not text or seg_start < 0 or seg_end <= seg_start:
            continue
        clip_start = max(start, seg_start)
        clip_end = min(end, seg_end)
        if clip_end <= clip_start:
            continue
        cues.append({
            "start": round(clip_start - start, 3),
            "end": round(clip_end - start, 3),
            "text": text,
        })
    return cues


def run_pipeline(
    source: Path,
    output_dir: Path,
    *,
    language: str | None = None,
    genre: str = "auto",
    top: int = 3,
    source_label: str | None = None,
) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Source video does not exist: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = ffprobe(str(source))
    duration = _number(metadata.get("duration"))
    if duration <= 0:
        raise RuntimeError("Source video has no valid duration.")
    if not metadata.get("width") or not metadata.get("height"):
        raise RuntimeError("Source does not contain a valid video stream.")

    transcript_result = transcribe(str(source), language)
    segments = transcript_result.get("segments") or []
    transcript_text = str(transcript_result.get("text") or "")
    (output_dir / "transcript.json").write_text(
        json.dumps(transcript_result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    analysis_result = analyze(AnalyzeRequest(
        segments=segments,
        media_path=str(source),
        genre=genre,
    ))
    candidates = analysis_result.get("candidates") or []
    rendered = []
    for index, candidate in enumerate(candidates[:max(1, min(top, 10))], start=1):
        start = max(0.0, _number(candidate.get("start"), -1))
        end = min(duration, _number(candidate.get("end"), -1))
        if end <= start:
            continue
        filename = f"clip-{index:02d}.mp4"
        output_path = output_dir / filename
        render(
            str(source),
            str(output_path),
            start=start,
            end=end,
            aspect="9:16",
            segments=[{"start": start, "end": end}],
            captions=_captions_for_clip(segments, start, end),
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Renderer did not produce a valid file: {output_path}")
        rendered.append({
            "file": filename,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "score": _number(candidate.get("score")),
            "title": str(candidate.get("title") or "Untitled highlight"),
            "category": str(candidate.get("category") or "AI Detect"),
            "rationale": str(candidate.get("rationale") or ""),
            "features": candidate.get("features") or {},
            "bytes": output_path.stat().st_size,
        })

    report = {
        "status": "passed" if rendered else "no_candidates",
        "source": source_label or str(source.resolve()),
        "media": {
            "duration": duration,
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "hasAudio": metadata.get("hasAudio"),
        },
        "transcription": {
            "language": transcript_result.get("language"),
            "segmentCount": len(segments),
            "characterCount": len(transcript_text),
        },
        "analysis": {
            "genre": genre,
            "candidateCount": len(candidates),
            "renderedCount": len(rendered),
        },
        "clips": rendered,
        "limitations": [
            "A successful smoke test proves the tested source completed the local pipeline; it does not prove highlight quality across all genres.",
            "Use human-labelled benchmarks to measure precision and recall.",
        ],
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path, help="path to a local video file")
    source_group.add_argument("--url", help="supported public video URL")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/ai-smoke"))
    parser.add_argument("--language", help="optional Whisper language code, e.g. en")
    parser.add_argument("--genre", default="auto", help="content genre for ranking")
    parser.add_argument("--top", type=int, default=3, help="number of clips to render (1-10)")
    args = parser.parse_args()
    if not 1 <= args.top <= 10:
        parser.error("--top must be between 1 and 10")

    try:
        if args.url:
            with tempfile.TemporaryDirectory(prefix="clipfinder-ai-smoke-") as temporary:
                source = Path(download(args.url, temporary))
                report = run_pipeline(
                    source, args.out_dir, language=args.language, genre=args.genre, top=args.top,
                    source_label=args.url,
                )
        else:
            report = run_pipeline(
                args.source, args.out_dir, language=args.language, genre=args.genre, top=args.top
            )
    except Exception as exc:
        failure = {
            "status": "failed",
            "stage": "download" if args.url else "pipeline",
            "source": args.url or str(args.source),
            "errorType": type(exc).__name__,
            "error": str(exc),
        }
        # Keep a machine-readable failure artifact so CI failures are diagnosable
        # even when transcription, analysis, or rendering fails before report.json.
        try:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            (args.out_dir / "report.json").write_text(
                json.dumps(failure, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as artifact_error:
            failure["artifactError"] = str(artifact_error)
        print(json.dumps(failure, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
