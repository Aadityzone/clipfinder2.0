"""Progressive streaming AI pipeline for long-form media.

Executes bounded-chunk audio extraction and transcription, begins highlight
discovery as soon as the first transcript chunks arrive, deduplicates across
chunk boundaries, prioritizes highest-scoring candidates onto bounded FFmpeg
render workers using single-pass caption burning, verifies every MP4 with
ffprobe before marking it ready, and surfaces early playable clips while
remaining chunks finish processing in the background.
"""

from __future__ import annotations

import concurrent.futures
import heapq
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil

from ai.main import AnalyzeRequest, analyze
from ai.services.dedup import overlap_ratio
from ai.services.media import ffprobe
from ai.services.render import render
from ai.services.transcription_chunking import (
    DEFAULT_MAX_RETRIES,
    deduplicate_boundary_words,
    get_default_concurrency,
    plan_chunk_windows,
    transcribe_single_chunk,
)
from ai.transcribe import transcription_capabilities


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return result if math.isfinite(result) else fallback


def captions_for_clip(segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    """Build clip-relative caption cues covering [start, end] from chronological segments."""
    cues: list[dict[str, Any]] = []
    for segment in segments:
        seg_start = _number(segment.get("start"), -1.0)
        seg_end = _number(segment.get("end"), -1.0)
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


def merge_progressive_candidates(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    rendered_spans: list[tuple[float, float]] | None = None,
    iou_threshold: float = 0.45,
) -> list[dict[str, Any]]:
    """Merge new chunk candidates into existing pool without duplicating moments.

    - Never replaces or duplicates a moment whose span is already rendered/queued.
    - If a new candidate significantly overlaps an unrendered candidate and has a
      higher score, it refines that candidate in-place.
    - Returns all candidates sorted descending by score.
    """
    pool = [dict(item) for item in existing]
    active_spans = list(rendered_spans or [])

    for cand in incoming:
        c_start = _number(cand.get("start"), -1.0)
        c_end = _number(cand.get("end"), -1.0)
        if c_start < 0 or c_end <= c_start:
            continue
        c_score = _number(cand.get("score"), 0.0)

        # Skip if already covers a rendered or queued span
        if any(overlap_ratio({"start": c_start, "end": c_end}, {"start": r_s, "end": r_e}) >= iou_threshold for r_s, r_e in active_spans):
            continue

        matched_idx: int | None = None
        for idx, prior in enumerate(pool):
            ratio = overlap_ratio(
                {"start": c_start, "end": c_end},
                {"start": _number(prior.get("start")), "end": _number(prior.get("end"))},
            )
            if ratio >= iou_threshold:
                matched_idx = idx
                break

        if matched_idx is not None:
            prior_score = _number(pool[matched_idx].get("score"), 0.0)
            if c_score > prior_score and not pool[matched_idx].get("_rendered"):
                pool[matched_idx] = dict(cand)
        else:
            pool.append(dict(cand))

    pool.sort(key=lambda c: _number(c.get("score"), 0.0), reverse=True)
    return pool


class _ResourceMonitor:
    """Sample process RSS memory and CPU percent during execution."""

    def __init__(self, interval_s: float = 0.5):
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_rss_mb: float = 0.0
        self.cpu_samples: list[float] = []
        self._process = psutil.Process(os.getpid())

    def start(self) -> None:
        self._process.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._run, name="progressive-monitor", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                mem_mb = self._process.memory_info().rss / (1024 * 1024)
                if mem_mb > self.peak_rss_mb:
                    self.peak_rss_mb = mem_mb
                cpu = psutil.cpu_percent(interval=None)
                self.cpu_samples.append(cpu)
            except Exception:
                pass
            self._stop.wait(self._interval_s)

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            mem_mb = self._process.memory_info().rss / (1024 * 1024)
            self.peak_rss_mb = max(self.peak_rss_mb, mem_mb)
        except Exception:
            pass
        avg_cpu = round(sum(self.cpu_samples) / len(self.cpu_samples), 1) if self.cpu_samples else None
        max_cpu = round(max(self.cpu_samples), 1) if self.cpu_samples else None
        return {
            "peakRssMb": round(self.peak_rss_mb, 2),
            "avgSystemCpuPercent": avg_cpu,
            "peakSystemCpuPercent": max_cpu,
        }


def run_progressive_pipeline(
    source_path: Path,
    output_dir: Path,
    *,
    language: str | None = None,
    genre: str = "auto",
    top: int = 3,
    chunk_duration_s: float | None = None,
    overlap_s: float = 1.5,
    transcribe_concurrency: int | None = None,
    render_concurrency: int | None = None,
    lookback_context_s: float = 60.0,
    checkpoint_path: Path | None = None,
    cancel_event: threading.Event | None = None,
    ingestion_metrics: dict[str, Any] | None = None,
    source_label: str | None = None,
    on_clip_ready: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute progressive transcription -> chunked analysis -> priority rendering."""
    pipeline_started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    monitor = _ResourceMonitor()
    monitor.start()

    milestones: dict[str, float | None] = {
        "metadataLookupSeconds": (ingestion_metrics or {}).get("metadataLookupSeconds"),
        "sourceDownloadSeconds": (ingestion_metrics or {}).get("sourceDownloadSeconds"),
        "sourceBytesDownloaded": (ingestion_metrics or {}).get("sourceBytesDownloaded"),
        "ffprobeSeconds": None,
        "firstAudioExtractAndTranscribeSeconds": None,
        "firstCandidateDiscoverySeconds": None,
        "firstRenderStartSeconds": None,
        "firstPlayableClipSeconds": None,
        "thirdPlayableClipSeconds": None,
        "totalPipelineSeconds": None,
    }

    try:
        probe_start = time.perf_counter()
        metadata = ffprobe(str(source_path), strict=True)
        milestones["ffprobeSeconds"] = round(time.perf_counter() - probe_start, 3)

        duration = _number(metadata.get("duration"))
        if duration <= 0 or not metadata.get("width") or not metadata.get("height"):
            raise RuntimeError("Source video has no valid duration or video stream.")

        # Choose sensible progressive chunk window so first chunk completes rapidly.
        effective_chunk_s = float(chunk_duration_s or os.getenv("PROGRESSIVE_CHUNK_SECONDS", "120.0"))
        if duration <= effective_chunk_s:
            windows = plan_chunk_windows(duration, chunk_duration_s=duration, overlap_s=0.0)
        else:
            windows = plan_chunk_windows(duration, chunk_duration_s=effective_chunk_s, overlap_s=overlap_s)

        if not metadata.get("hasAudio") or not windows:
            # No audio: fall back directly to visual analysis & priority rendering.
            windows = []

        # Resume from checkpoint if present
        completed_chunk_map: dict[int, dict[str, Any]] = {}
        restored_candidates: list[dict[str, Any]] = []
        if checkpoint_path and checkpoint_path.is_file():
            try:
                saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                for row in saved.get("completedChunks", []):
                    completed_chunk_map[int(row["index"])] = row
                for cand in saved.get("candidates", []):
                    if isinstance(cand, dict):
                        restored_candidates.append(cand)
            except Exception:
                completed_chunk_map = {}
                restored_candidates = []

        state_lock = threading.Lock()
        all_segments: list[dict[str, Any]] = []
        candidate_pool: list[dict[str, Any]] = []
        rendered_spans: list[tuple[float, float]] = []
        rendered_clips: list[dict[str, Any]] = []
        failed_chunks: list[dict[str, Any]] = []
        render_errors: list[str] = []
        detected_language = language or "en"

        if completed_chunk_map:
            raw_prior: list[dict[str, Any]] = []
            for idx in sorted(completed_chunk_map):
                raw_prior.extend(completed_chunk_map[idx].get("segments") or [])
            all_segments = deduplicate_boundary_words(raw_prior, tolerance_s=overlap_s * 0.75)

        if restored_candidates:
            candidate_pool = merge_progressive_candidates(candidate_pool, restored_candidates, rendered_spans)

        t_workers = transcribe_concurrency or get_default_concurrency()
        r_workers = render_concurrency or max(1, min(2, int(os.getenv("MAX_CONCURRENT_RENDERS", "2"))))
        pending_windows = [w for w in windows if w["index"] not in completed_chunk_map]

        render_pool = concurrent.futures.ThreadPoolExecutor(max_workers=r_workers)
        active_render_futures: dict[concurrent.futures.Future, tuple[int, dict[str, Any]]] = {}
        render_seq = 0
        next_clip_num = 1
        # Priority min-heap of (-score, seq, candidate) for background render dispatching
        render_heap: list[tuple[float, int, dict[str, Any]]] = []

        def _persist_checkpoint() -> None:
            if not checkpoint_path:
                return
            clean_candidates = [
                {k: v for k, v in cand.items() if not str(k).startswith("_")}
                for cand in candidate_pool
            ]
            payload = {
                "source": str(source_path),
                "completedChunks": [completed_chunk_map[i] for i in sorted(completed_chunk_map)],
                "candidates": clean_candidates,
                "updatedAt": time.time(),
            }
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

        def _render_candidate_task(cand: dict[str, Any], clip_num: int, segs_snapshot: list[dict[str, Any]]) -> dict[str, Any]:
            c_start = max(0.0, _number(cand.get("start"), 0.0))
            c_end = min(duration, _number(cand.get("end"), duration))
            filename = f"clip-{clip_num:02d}.mp4"
            out_path = output_dir / filename
            t0 = time.perf_counter()
            cues = captions_for_clip(segs_snapshot, c_start, c_end)
            render(
                str(source_path),
                str(out_path),
                start=c_start,
                end=c_end,
                aspect="9:16",
                segments=[{"start": c_start, "end": c_end}],
                captions=cues,
                focus_x=_number((cand.get("features") or {}).get("faceFocusX"), 0.5),
                single_pass=True,
            )
            r_meta = ffprobe(str(out_path))
            if (
                not out_path.is_file()
                or out_path.stat().st_size < 1024
                or _number(r_meta.get("duration")) <= 0
                or not r_meta.get("width")
                or not r_meta.get("height")
            ):
                raise RuntimeError(f"Rendered clip failed verification: {out_path}")
            return {
                "file": filename,
                "path": str(out_path),
                "start": round(c_start, 3),
                "end": round(c_end, 3),
                "duration": round(c_end - c_start, 3),
                "verifiedDuration": round(_number(r_meta.get("duration")), 3),
                "width": r_meta.get("width"),
                "height": r_meta.get("height"),
                "score": _number(cand.get("score")),
                "title": str(cand.get("title") or "Untitled highlight"),
                "category": str(cand.get("category") or "AI Detect"),
                "rationale": str(cand.get("rationale") or ""),
                "renderSeconds": round(time.perf_counter() - t0, 3),
                "bytes": out_path.stat().st_size,
                "_verifiedAtElapsed": round(time.perf_counter() - pipeline_started, 3),
            }

        verified_count = 0

        def _on_render_done(done_fut: concurrent.futures.Future) -> None:
            nonlocal verified_count
            try:
                res = done_fut.result()
                with state_lock:
                    verified_count += 1
                    elapsed = _number(res.get("_verifiedAtElapsed"), round(time.perf_counter() - pipeline_started, 3))
                    if milestones["firstPlayableClipSeconds"] is None:
                        milestones["firstPlayableClipSeconds"] = elapsed
                    if verified_count >= 3 and milestones["thirdPlayableClipSeconds"] is None:
                        milestones["thirdPlayableClipSeconds"] = elapsed
                if on_clip_ready:
                    try:
                        on_clip_ready({k: v for k, v in res.items() if k != "_verifiedAtElapsed"})
                    except Exception:
                        pass
            except Exception:
                pass

        def _maybe_dispatch_renders(segs_snapshot: list[dict[str, Any]]) -> None:
            nonlocal render_seq, next_clip_num
            with state_lock:
                # Harvest completed renders first
                done_futs = [f for f in active_render_futures if f.done()]
                for fut in done_futs:
                    _clip_idx, _cand = active_render_futures.pop(fut)
                    try:
                        clip_res = fut.result()
                        clip_res_clean = {k: v for k, v in clip_res.items() if k != "_verifiedAtElapsed"}
                        rendered_clips.append(clip_res_clean)
                    except Exception as exc:
                        render_errors.append(str(exc))

                in_flight_plus_done = len(rendered_clips) + len(active_render_futures)
                slots_available = max(0, top - in_flight_plus_done)
                if slots_available <= 0:
                    return

                # Push eligible unrendered candidates from candidate_pool
                for cand in candidate_pool:
                    if cand.get("_queued"):
                        continue
                    c_start = _number(cand.get("start"), -1.0)
                    c_end = _number(cand.get("end"), -1.0)
                    if c_start < 0 or c_end <= c_start:
                        continue
                    if any(overlap_ratio({"start": c_start, "end": c_end}, {"start": s, "end": e}) >= 0.45 for s, e in rendered_spans):
                        continue
                    cand["_queued"] = True
                    render_seq += 1
                    heapq.heappush(render_heap, (-_number(cand.get("score"), 0.0), render_seq, cand))

                while slots_available > 0 and len(active_render_futures) < r_workers and render_heap:
                    if cancel_event and cancel_event.is_set():
                        break
                    _, _, next_cand = heapq.heappop(render_heap)
                    c_start = _number(next_cand.get("start"))
                    c_end = _number(next_cand.get("end"))
                    next_cand["_rendered"] = True
                    rendered_spans.append((c_start, c_end))
                    clip_num = next_clip_num
                    next_clip_num += 1
                    if milestones["firstRenderStartSeconds"] is None:
                        milestones["firstRenderStartSeconds"] = round(time.perf_counter() - pipeline_started, 3)
                    fut = render_pool.submit(_render_candidate_task, next_cand, clip_num, list(segs_snapshot))
                    fut.add_done_callback(_on_render_done)
                    active_render_futures[fut] = (clip_num, next_cand)
                    slots_available -= 1

        try:
            # Immediately dispatch any resumed candidates before waiting on remaining chunks
            if candidate_pool:
                _maybe_dispatch_renders(list(all_segments))
            # Handle visual-only silent media directly
            if not windows:
                res = analyze(AnalyzeRequest(segments=[], media_path=str(source_path), genre=genre))
                cands = res.get("candidates") or []
                if cands and milestones["firstCandidateDiscoverySeconds"] is None:
                    milestones["firstCandidateDiscoverySeconds"] = round(time.perf_counter() - pipeline_started, 3)
                candidate_pool = merge_progressive_candidates(candidate_pool, cands, rendered_spans)
                _maybe_dispatch_renders([])

            # Stream transcription chunks and immediately feed completed chunks into bounded analysis
            with concurrent.futures.ThreadPoolExecutor(max_workers=t_workers) as t_pool:
                t_futures = {
                    t_pool.submit(
                        transcribe_single_chunk,
                        win,
                        language=language,
                        max_retries=DEFAULT_MAX_RETRIES,
                        media_path=str(source_path),
                    ): win
                    for win in pending_windows
                }

                for fut in concurrent.futures.as_completed(t_futures):
                    if cancel_event and cancel_event.is_set():
                        for pf in t_futures:
                            pf.cancel()
                        break

                    win = t_futures[fut]
                    try:
                        chunk_res = fut.result()
                    except Exception as exc:
                        failed_chunks.append({"index": win["index"], "error": str(exc)})
                        continue

                    if milestones["firstAudioExtractAndTranscribeSeconds"] is None:
                        milestones["firstAudioExtractAndTranscribeSeconds"] = round(time.perf_counter() - pipeline_started, 3)

                    if chunk_res.get("language") and not language:
                        detected_language = chunk_res["language"]

                    with state_lock:
                        completed_chunk_map[win["index"]] = chunk_res
                        raw_all: list[dict[str, Any]] = []
                        for idx in sorted(completed_chunk_map):
                            raw_all.extend(completed_chunk_map[idx].get("segments") or [])
                        all_segments = deduplicate_boundary_words(raw_all, tolerance_s=overlap_s * 0.75)
                        segs_snapshot = list(all_segments)
                        _persist_checkpoint()

                    # Analyze this chunk's window (+ lookback context for cross-boundary setup)
                    a_start = max(0.0, float(win["start_time"]) - lookback_context_s)
                    a_end = min(duration, float(win["end_time"]))
                    use_bounded = (a_end - a_start) < (duration - 1.0)
                    analysis_req = AnalyzeRequest(
                        segments=segs_snapshot,
                        media_path=str(source_path),
                        genre=genre,
                        start_seconds=a_start if use_bounded else None,
                        end_seconds=a_end if use_bounded else None,
                    )
                    analysis_out = analyze(analysis_req)
                    new_cands = analysis_out.get("candidates") or []
                    if new_cands and milestones["firstCandidateDiscoverySeconds"] is None:
                        milestones["firstCandidateDiscoverySeconds"] = round(time.perf_counter() - pipeline_started, 3)

                    with state_lock:
                        candidate_pool = merge_progressive_candidates(candidate_pool, new_cands, rendered_spans)
                        _persist_checkpoint()

                    _maybe_dispatch_renders(segs_snapshot)

            # Drain remaining background renders and fill remaining top slots if fewer than `top` completed
            while True:
                if cancel_event and cancel_event.is_set():
                    break
                with state_lock:
                    pending_renders = list(active_render_futures.keys())
                if not pending_renders:
                    _maybe_dispatch_renders(list(all_segments))
                    with state_lock:
                        if not active_render_futures:
                            break
                        pending_renders = list(active_render_futures.keys())
                concurrent.futures.wait(pending_renders, return_when=concurrent.futures.FIRST_COMPLETED)
                _maybe_dispatch_renders(list(all_segments))
        finally:
            render_pool.shutdown(wait=True)

        total_seconds = round(time.perf_counter() - pipeline_started, 3)
        milestones["totalPipelineSeconds"] = total_seconds

        full_text = " ".join(str(s.get("text", "")).strip() for s in all_segments if str(s.get("text", "")).strip())
        (output_dir / "transcript.json").write_text(
            json.dumps({
                "language": detected_language,
                "text": full_text,
                "segments": all_segments,
                "duration": round(duration, 3),
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        rendered_clips.sort(key=lambda c: _number(c.get("score"), 0.0), reverse=True)
        resources = monitor.stop()
        caps = transcription_capabilities()

        total_with_ingest = total_seconds + _number((ingestion_metrics or {}).get("sourceDownloadSeconds")) + _number((ingestion_metrics or {}).get("metadataLookupSeconds"))

        report = {
            "status": "cancelled" if (cancel_event and cancel_event.is_set()) else ("passed" if rendered_clips else "no_candidates"),
            "mode": "progressive",
            "source": source_label or str(source_path.resolve()),
            "media": {
                "duration": round(duration, 3),
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "hasAudio": metadata.get("hasAudio"),
                "format": metadata.get("format"),
                "sourceBytes": source_path.stat().st_size,
            },
            "milestones": milestones,
            "performance": {
                "localPipelineSeconds": total_seconds,
                "endToEndWithIngestionSeconds": round(total_with_ingest, 3),
                "realTimeFactor": round(duration / total_seconds, 3) if total_seconds > 0 else None,
                "resources": resources,
                "transcriptionCapabilities": caps,
            },
            "transcription": {
                "language": detected_language,
                "chunksPlanned": len(windows),
                "chunksCompleted": len(completed_chunk_map),
                "chunksFailed": len(failed_chunks),
                "failedChunks": failed_chunks,
                "segmentCount": len(all_segments),
                "characterCount": len(full_text),
            },
            "analysis": {
                "genre": genre,
                "candidateCount": len(candidate_pool),
                "renderedCount": len(rendered_clips),
                "renderErrors": render_errors,
            },
            "clips": rendered_clips,
        }
        (output_dir / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report
    finally:
        monitor.stop()
