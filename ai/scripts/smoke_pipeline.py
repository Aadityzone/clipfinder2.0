"""Run a real local Clip Finder pipeline smoke test or progressive benchmark against a source video.

This command exercises source probing, transcription, multimodal analysis,
ranking, and actual MP4 rendering. It deliberately does not use mocked model
outputs. A configured LLM provider is optional; deterministic ranking remains
available without one.

Examples (run from repository root):
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --source sample.mp4
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --source sample.mp4 --progressive
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --url "https://www.youtube.com/watch?v=..." --genre gaming --progressive
  PYTHONPATH=. python ai/scripts/smoke_pipeline.py --source sample.mp4 --out-dir ./artifacts/ai-smoke --top 3

Requirements: AI Python dependencies, FFmpeg/ffprobe, and model weights for
faster-whisper. Video URLs must be from supported providers and usage must
comply with the source platform's terms and rights.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ai.main import AnalyzeRequest, analyze
from ai.services.download import download, download_range, get_video_metadata
from ai.services.evaluation import selection_diagnostics
from ai.services.media import ffprobe
from ai.services.progressive import _ResourceMonitor, run_progressive_pipeline
from ai.services.render import render
from ai.transcribe import model as get_whisper_model, transcribe, transcription_capabilities


class SmokeStageError(RuntimeError):
    """Attach a stable pipeline stage name to a smoke-test failure."""

    def __init__(self, stage: str, error: Exception):
        super().__init__(str(error))
        self.stage = stage
        self.error_type = type(error).__name__


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
    progressive: bool = False,
    chunk_seconds: float | None = None,
    ingestion_metrics: dict[str, Any] | None = None,
    model_warm: bool | None = None,
) -> dict:
    if progressive:
        return run_progressive_pipeline(
            source,
            output_dir,
            language=language,
            genre=genre,
            top=top,
            chunk_duration_s=chunk_seconds,
            ingestion_metrics=ingestion_metrics,
            source_label=source_label,
        )

    pipeline_started = time.perf_counter()
    timings: dict[str, float] = {}
    if not source.is_file():
        raise SmokeStageError("source", FileNotFoundError(f"Source video does not exist: {source}"))
    output_dir.mkdir(parents=True, exist_ok=True)
    monitor = _ResourceMonitor()
    monitor.start()

    first_render_start_s: float | None = None
    first_playable_s: float | None = None
    third_playable_s: float | None = None

    try:
        stage_started = time.perf_counter()
        try:
            metadata = ffprobe(str(source))
        except Exception as exc:
            raise SmokeStageError("media_probe", exc) from exc
        duration = _number(metadata.get("duration"))
        if duration <= 0:
            raise SmokeStageError("media_probe", RuntimeError("Source video has no valid duration."))
        if not metadata.get("width") or not metadata.get("height"):
            raise SmokeStageError("media_probe", RuntimeError("Source does not contain a valid video stream."))
        timings["ffprobeSeconds"] = round(time.perf_counter() - stage_started, 3)

        stage_started = time.perf_counter()
        try:
            transcript_result = transcribe(str(source), language)
        except Exception as exc:
            raise SmokeStageError("transcription", exc) from exc
        segments = transcript_result.get("segments") or []
        transcript_text = str(transcript_result.get("text") or "")
        timings["transcriptionSeconds"] = round(time.perf_counter() - stage_started, 3)
        (output_dir / "transcript.json").write_text(
            json.dumps(transcript_result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        stage_started = time.perf_counter()
        try:
            analysis_result = analyze(AnalyzeRequest(
                segments=segments,
                media_path=str(source),
                genre=genre,
            ))
        except Exception as exc:
            raise SmokeStageError("analysis", exc) from exc
        timings["analysisAndRankingSeconds"] = round(time.perf_counter() - stage_started, 3)
        candidates = analysis_result.get("candidates") or []
        rendered = []
        for index, candidate in enumerate(candidates[:max(1, min(top, 10))], start=1):
            start = max(0.0, _number(candidate.get("start"), -1))
            end = min(duration, _number(candidate.get("end"), -1))
            if end <= start:
                continue
            filename = f"clip-{index:02d}.mp4"
            output_path = output_dir / filename
            if first_render_start_s is None:
                first_render_start_s = round(time.perf_counter() - pipeline_started, 3)
            stage_started = time.perf_counter()
            try:
                render(
                    str(source),
                    str(output_path),
                    start=start,
                    end=end,
                    aspect="9:16",
                    segments=[{"start": start, "end": end}],
                    captions=_captions_for_clip(segments, start, end),
                    single_pass=True,
                )
                if not output_path.is_file() or output_path.stat().st_size == 0:
                    raise RuntimeError(f"Renderer did not produce a valid file: {output_path}")
                rendered_metadata = ffprobe(str(output_path))
                if (
                    _number(rendered_metadata.get("duration")) <= 0
                    or not rendered_metadata.get("width")
                    or not rendered_metadata.get("height")
                ):
                    raise RuntimeError(f"Rendered output is not a playable video: {output_path}")
            except Exception as exc:
                raise SmokeStageError("render", exc) from exc
            elapsed_now = round(time.perf_counter() - pipeline_started, 3)
            if first_playable_s is None:
                first_playable_s = elapsed_now
            if len(rendered) + 1 >= 3 and third_playable_s is None:
                third_playable_s = elapsed_now
            timings[f"render{index}Seconds"] = round(time.perf_counter() - stage_started, 3)
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

        total_seconds = round(time.perf_counter() - pipeline_started, 3)
        resources = monitor.stop()
        caps = transcription_capabilities()
        ingest_info = ingestion_metrics or {}
        end_to_end_s = round(
            total_seconds
            + _number(ingest_info.get("metadataLookupSeconds"))
            + _number(ingest_info.get("sourceDownloadSeconds")),
            3,
        )

        report = {
            "status": "passed" if rendered else "no_candidates",
            "mode": "batch",
            "source": source_label or str(source.resolve()),
            "media": {
                "duration": duration,
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "hasAudio": metadata.get("hasAudio"),
                "format": metadata.get("format"),
                "sourceBytes": source.stat().st_size,
            },
            "milestones": {
                "metadataLookupSeconds": ingest_info.get("metadataLookupSeconds"),
                "sourceDownloadSeconds": ingest_info.get("sourceDownloadSeconds"),
                "sourceBytesDownloaded": ingest_info.get("sourceBytesDownloaded"),
                "ffprobeSeconds": timings.get("ffprobeSeconds"),
                "transcriptionSeconds": timings.get("transcriptionSeconds"),
                "analysisAndRankingSeconds": timings.get("analysisAndRankingSeconds"),
                "firstRenderStartSeconds": first_render_start_s,
                "firstPlayableClipSeconds": first_playable_s,
                "thirdPlayableClipSeconds": third_playable_s,
                "totalPipelineSeconds": total_seconds,
            },
            "performance": {
                "stageSeconds": timings,
                "pipelineSeconds": total_seconds,
                "endToEndWithIngestionSeconds": end_to_end_s,
                "realTimeFactor": round(duration / total_seconds, 3) if total_seconds > 0 else None,
                "runMode": "url_to_clip" if source_label else "local_file",
                "modelWarm": model_warm if model_warm is not None else bool(caps.get("loaded")),
                "host": platform.platform(),
                "processor": platform.processor() or None,
                "python": platform.python_version(),
                "transcriptionCapabilities": caps,
                "resources": resources,
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
                "selection": selection_diagnostics(candidates, media_duration=duration),
                # Why the selector kept or dropped each row, straight from the pipeline.
                "pipelineSelection": analysis_result.get("selection"),
            },
            "clips": rendered,
            "limitations": [
                "A successful smoke test proves the tested source completed the local pipeline; it does not prove highlight quality across all genres.",
                "The analysis.selection block measures structural shape (duplicate rate, temporal coverage, clustering) in the delivered order. It is not a quality score.",
                "Use human-labelled benchmarks to measure precision and recall.",
            ],
        }
        (output_dir / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report
    finally:
        monitor.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path, help="path to a local video file")
    source_group.add_argument("--url", help="supported public video URL")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/ai-smoke"))
    parser.add_argument("--language", help="optional Whisper language code, e.g. en")
    parser.add_argument("--genre", default="auto", help="content genre for ranking")
    parser.add_argument("--top", type=int, default=3, help="number of clips to render (1-10)")
    parser.add_argument("--progressive", action="store_true", help="run progressive incremental chunk pipeline")
    parser.add_argument("--chunk-seconds", type=float, default=None, help="override progressive audio chunk duration")
    parser.add_argument("--start-seconds", type=float, default=None, help="optional source range start in seconds")
    parser.add_argument("--end-seconds", type=float, default=None, help="optional source range end in seconds")
    parser.add_argument("--warmup", action="store_true", help="pre-load Whisper model before timing pipeline")
    args = parser.parse_args()
    if not 1 <= args.top <= 10:
        parser.error("--top must be between 1 and 10")
    if (args.start_seconds is None) != (args.end_seconds is None):
        parser.error("--start-seconds and --end-seconds must be specified together")

    try:
        model_warm = False
        if args.warmup:
            get_whisper_model()
            model_warm = True

        if args.url:
            with tempfile.TemporaryDirectory(prefix="clipfinder-ai-smoke-") as temporary:
                meta_s: float | None = None
                if args.start_seconds is not None or args.progressive:
                    meta_t0 = time.perf_counter()
                    try:
                        get_video_metadata(args.url)
                    except Exception:
                        if args.start_seconds is not None:
                            raise
                    meta_s = round(time.perf_counter() - meta_t0, 3)

                dl_t0 = time.perf_counter()
                if args.start_seconds is not None and args.end_seconds is not None:
                    source = Path(download_range(args.url, temporary, args.start_seconds, args.end_seconds))
                else:
                    source = Path(download(args.url, temporary))
                dl_s = round(time.perf_counter() - dl_t0, 3)
                dl_bytes = source.stat().st_size if source.is_file() else 0

                report = run_pipeline(
                    source,
                    args.out_dir,
                    language=args.language,
                    genre=args.genre,
                    top=args.top,
                    source_label=args.url,
                    progressive=args.progressive,
                    chunk_seconds=args.chunk_seconds,
                    ingestion_metrics={
                        "metadataLookupSeconds": meta_s,
                        "sourceDownloadSeconds": dl_s,
                        "sourceBytesDownloaded": dl_bytes,
                    },
                    model_warm=model_warm,
                )
        else:
            report = run_pipeline(
                args.source,
                args.out_dir,
                language=args.language,
                genre=args.genre,
                top=args.top,
                progressive=args.progressive,
                chunk_seconds=args.chunk_seconds,
                model_warm=model_warm,
            )
    except Exception as exc:
        failure = {
            "status": "failed",
            "stage": getattr(exc, "stage", "download" if args.url else "pipeline"),
            "source": args.url or str(args.source),
            "errorType": getattr(exc, "error_type", type(exc).__name__),
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
