"""High-performance incremental & parallel audio transcription engine.

Splits long media into bounded time windows with overlap, extracts audio per
chunk (avoiding loading full-hour audio arrays into RAM), transcribes chunks
concurrently across bounded hardware threads, suppresses duplicate words across
chunk boundaries, isolates/retries transient chunk failures, and supports
streaming completed chunks immediately downstream.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import re
import time
from typing import Any, Callable, Iterator

import numpy as np

from ai.services.media import ffprobe
from ai.transcribe import (
    WHISPER_SAMPLE_RATE,
    decode_audio,
    transcribe,
)

DEFAULT_CHUNK_DURATION_SECONDS = float(os.getenv("TRANSCRIPTION_CHUNK_SECONDS", "180.0"))
DEFAULT_OVERLAP_SECONDS = float(os.getenv("TRANSCRIPTION_CHUNK_OVERLAP_SECONDS", "1.5"))
DEFAULT_MAX_RETRIES = int(os.getenv("TRANSCRIPTION_CHUNK_RETRIES", "2"))


def get_default_concurrency() -> int:
    """Determine bounded worker concurrency based on system CPU cores."""
    env_concurrency = os.getenv("TRANSCRIPTION_CONCURRENCY")
    if env_concurrency:
        try:
            val = int(env_concurrency)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    cpu_cores = os.cpu_count() or 2
    # Keep bounded to avoid RAM spikes and CTranslate2 thread thrashing.
    return max(1, min(3, cpu_cores // 4)) if cpu_cores >= 8 else max(1, min(2, cpu_cores // 2))


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _normalize_word(word: str) -> str:
    """Normalize a word token for fuzzy boundary matching."""
    return re.sub(r"[^\w]", "", word.lower()).strip()


def _join_word_tokens(words: list[dict[str, Any]]) -> str:
    """Join word tokens cleanly whether providers include leading spaces or not."""
    parts: list[str] = []
    for idx, w in enumerate(words):
        raw = str(w.get("word", ""))
        if not raw:
            continue
        if idx == 0:
            parts.append(raw.lstrip())
        elif raw[0].isspace() or raw[0] in {".", ",", "!", "?", ";", ":", ")", "]", "'"}:
            parts.append(raw)
        else:
            prev = parts[-1] if parts else ""
            if prev.endswith((" ", "\t", "(", "[")):
                parts.append(raw)
            else:
                parts.append(" " + raw)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def plan_chunk_windows(
    duration_s: float,
    chunk_duration_s: float = DEFAULT_CHUNK_DURATION_SECONDS,
    overlap_s: float = DEFAULT_OVERLAP_SECONDS,
    start_s: float = 0.0,
) -> list[dict[str, Any]]:
    """Plan bounded time windows covering [start_s, start_s + duration_s] with overlap."""
    total_dur = _finite(duration_s)
    origin = _finite(start_s)
    if total_dur is None or total_dur <= 0 or origin is None or origin < 0:
        return []
    step = max(1.0, float(chunk_duration_s))
    overlap = max(0.0, float(overlap_s))
    end_limit = origin + total_dur
    windows: list[dict[str, Any]] = []
    cursor = origin
    idx = 0
    while cursor < end_limit - 1e-4:
        # Avoid spinning up an entire Whisper chunk for a sub-second tail slice.
        if (end_limit - (cursor + step)) <= 1.0 and step > 2.0:
            win_end = end_limit
        else:
            win_end = min(end_limit, cursor + step + overlap)
        windows.append({
            "index": idx,
            "start_time": round(cursor, 3),
            "end_time": round(win_end, 3),
            "duration": round(win_end - cursor, 3),
            "is_last": win_end >= end_limit - 1e-4,
        })
        if win_end >= end_limit - 1e-4 and (cursor + step >= end_limit - 1e-4 or (end_limit - (cursor + step)) <= 1.0):
            break
        cursor += step
        idx += 1
    return windows


def split_audio_chunks(
    audio: np.ndarray,
    sample_rate: int = WHISPER_SAMPLE_RATE,
    chunk_duration_s: float = DEFAULT_CHUNK_DURATION_SECONDS,
    overlap_s: float = DEFAULT_OVERLAP_SECONDS,
) -> list[dict[str, Any]]:
    """Split a 1D audio sample array into chronological chunk slices with overlap."""
    if not isinstance(audio, np.ndarray) or audio.ndim != 1:
        raise ValueError("Audio samples must be a 1D numpy array.")
    total_samples = len(audio)
    if total_samples == 0:
        return []

    step_samples = max(1, int(chunk_duration_s * sample_rate))
    overlap_samples = max(0, int(overlap_s * sample_rate))

    chunks: list[dict[str, Any]] = []
    start_sample = 0
    chunk_index = 0

    while start_sample < total_samples:
        end_sample = min(total_samples, start_sample + step_samples + overlap_samples)
        start_time_s = round(start_sample / sample_rate, 3)
        end_time_s = round(end_sample / sample_rate, 3)
        duration_s = round(end_time_s - start_time_s, 3)

        chunk_slice = audio[start_sample:end_sample]
        chunks.append({
            "index": chunk_index,
            "start_time": start_time_s,
            "end_time": end_time_s,
            "duration": duration_s,
            "audio": chunk_slice,
            "is_last": end_sample >= total_samples,
        })

        chunk_index += 1
        start_sample += step_samples

    return chunks


def deduplicate_boundary_words(
    all_segments: list[dict[str, Any]],
    tolerance_s: float = 0.75,
) -> list[dict[str, Any]]:
    """Clean duplicate words and duplicate segment fragments across overlapping chunks.

    Handles both ordered and out-of-order chunk completions, malformed/NaN
    timestamps, empty segments, and both spaced and unspaced word tokens.
    """
    if not all_segments:
        return []

    valid_segments: list[dict[str, Any]] = []
    for seg in all_segments:
        if not isinstance(seg, dict):
            continue
        s = _finite(seg.get("start"))
        e = _finite(seg.get("end"))
        if s is None or e is None or s < 0 or e <= s:
            continue
        valid_segments.append({**seg, "start": s, "end": e})

    sorted_segments = sorted(valid_segments, key=lambda s: (s["start"], s["end"]))

    cleaned_segments: list[dict[str, Any]] = []
    seen_words: list[dict[str, Any]] = []

    for seg in sorted_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        raw_words = seg.get("words") or []
        cleaned_words: list[dict[str, Any]] = []

        if raw_words:
            for w in raw_words:
                if not isinstance(w, dict):
                    continue
                w_start = _finite(w.get("start"))
                w_end = _finite(w.get("end"))
                if w_start is None or w_end is None or w_start < 0 or w_end <= w_start:
                    continue
                norm_text = _normalize_word(str(w.get("word", "")))
                if not norm_text:
                    continue

                is_duplicate = False
                for prev in seen_words[-20:]:
                    if (
                        prev["norm"] == norm_text
                        and abs(w_start - prev["start"]) <= tolerance_s
                    ):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    cleaned_words.append({**w, "start": w_start, "end": w_end})
                    seen_words.append({"norm": norm_text, "start": w_start, "end": w_end})

            if not cleaned_words:
                continue

            cleaned_text = _join_word_tokens(cleaned_words)
            if not cleaned_text:
                continue

            c_start = min(float(cleaned_words[0]["start"]), seg_start)
            c_end = max(float(cleaned_words[-1]["end"]), c_start + 0.05)
            cleaned_segments.append({
                "start": round(c_start, 3),
                "end": round(c_end, 3),
                "text": cleaned_text,
                "confidence": seg.get("confidence"),
                "words": cleaned_words,
            })
        else:
            seg_text = str(seg.get("text", "")).strip()
            norm_seg_text = _normalize_word(seg_text)
            if not norm_seg_text:
                continue

            is_duplicate = False
            for prev_seg in cleaned_segments[-4:]:
                prev_text = _normalize_word(str(prev_seg.get("text", "")))
                prev_end = float(prev_seg.get("end", 0))
                if norm_seg_text == prev_text and abs(seg_start - prev_end) <= (tolerance_s * 2):
                    is_duplicate = True
                    break

            if not is_duplicate:
                cleaned_segments.append({
                    "start": round(seg_start, 3),
                    "end": round(seg_end, 3),
                    "text": seg_text,
                    "confidence": seg.get("confidence"),
                    "words": [],
                })

    return cleaned_segments


def _shift_chunk_segments(
    segments: list[dict[str, Any]],
    start_offset: float,
) -> list[dict[str, Any]]:
    """Shift valid local chunk segment and word timestamps by start_offset."""
    shifted: list[dict[str, Any]] = []
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        raw_s = _finite(seg.get("start"))
        raw_e = _finite(seg.get("end"))
        if raw_s is None or raw_e is None or raw_s < 0 or raw_e <= raw_s:
            continue
        s_start = round(raw_s + start_offset, 3)
        s_end = round(raw_e + start_offset, 3)
        shifted_words: list[dict[str, Any]] = []
        for w in seg.get("words") or []:
            if not isinstance(w, dict):
                continue
            ws = _finite(w.get("start"))
            we = _finite(w.get("end"))
            if ws is None or we is None or ws < 0 or we <= ws:
                continue
            shifted_words.append({
                **w,
                "start": round(ws + start_offset, 3),
                "end": round(we + start_offset, 3),
            })
        shifted.append({
            **seg,
            "start": s_start,
            "end": s_end,
            "words": shifted_words,
        })
    return shifted


def transcribe_single_chunk(
    chunk: dict[str, Any],
    language: str | None = None,
    transcribe_fn: Callable[..., dict] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    media_path: str | None = None,
) -> dict[str, Any]:
    """Transcribe one audio chunk (from memory slice or bounded media range) with retries."""
    fn = transcribe_fn or transcribe
    start_offset = float(chunk["start_time"])
    end_time = float(chunk.get("end_time", start_offset + float(chunk.get("duration", 0))))
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            audio = chunk.get("audio")
            if audio is None and media_path is not None:
                audio = decode_audio(
                    media_path,
                    sample_rate=WHISPER_SAMPLE_RATE,
                    start_seconds=start_offset,
                    end_seconds=end_time,
                )
            if audio is None or (isinstance(audio, np.ndarray) and len(audio) == 0):
                return {
                    "index": chunk["index"],
                    "start_time": start_offset,
                    "end_time": end_time,
                    "segments": [],
                    "language": language or "unknown",
                    "failed": False,
                    "error": None,
                }
            result = fn(audio, language=language)
            shifted_segments = _shift_chunk_segments(result.get("segments", []), start_offset)
            return {
                "index": chunk["index"],
                "start_time": start_offset,
                "end_time": end_time,
                "segments": shifted_segments,
                "language": result.get("language"),
                "failed": False,
                "error": None,
            }
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue

    raise RuntimeError(
        f"Failed to transcribe chunk {chunk['index']} (at {start_offset}s) "
        f"after {max_retries + 1} attempts: {last_error}"
    ) from last_error


def iter_transcribe_chunks(
    media_path: str,
    *,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    language: str | None = None,
    chunk_duration_s: float = DEFAULT_CHUNK_DURATION_SECONDS,
    overlap_s: float = DEFAULT_OVERLAP_SECONDS,
    concurrency: int | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    transcribe_fn: Callable[..., dict] | None = None,
    fail_fast: bool = True,
    completed_indices: set[int] | None = None,
) -> Iterator[dict[str, Any]]:
    """Incrementally decode, transcribe, and yield completed chunks for streaming pipelines.

    Bounded-memory design: each chunk extracts only its [start_time, end_time]
    audio interval via FFmpeg rather than holding the full source audio in RAM.
    Chunks in `completed_indices` are skipped to support checkpoint resume without
    retranscribing completed work.
    """
    meta = ffprobe(media_path)
    source_duration = _finite(meta.get("duration")) or 0.0
    if not meta.get("hasAudio") or source_duration <= 0:
        return

    origin = max(0.0, float(start_seconds))
    limit = min(source_duration, float(end_seconds)) if end_seconds is not None else source_duration
    if limit <= origin:
        return

    windows = plan_chunk_windows(
        limit - origin,
        chunk_duration_s=chunk_duration_s,
        overlap_s=overlap_s,
        start_s=origin,
    )
    if completed_indices:
        windows = [w for w in windows if w["index"] not in completed_indices]
    if not windows:
        return

    pool_workers = concurrency if (concurrency and concurrency > 0) else get_default_concurrency()
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_workers) as executor:
        future_map = {
            executor.submit(
                transcribe_single_chunk,
                win,
                language=language,
                transcribe_fn=transcribe_fn,
                max_retries=max_retries,
                media_path=media_path,
            ): win
            for win in windows
        }

        for future in concurrent.futures.as_completed(future_map):
            win = future_map[future]
            try:
                yield future.result()
            except Exception as exc:
                if fail_fast:
                    for pending in future_map:
                        pending.cancel()
                    raise
                yield {
                    "index": win["index"],
                    "start_time": win["start_time"],
                    "end_time": win["end_time"],
                    "segments": [],
                    "language": language,
                    "failed": True,
                    "error": str(exc),
                }


def transcribe_chunked(
    media_or_audio: str | np.ndarray,
    language: str | None = None,
    chunk_duration_s: float = DEFAULT_CHUNK_DURATION_SECONDS,
    overlap_s: float = DEFAULT_OVERLAP_SECONDS,
    concurrency: int | None = None,
    transcribe_fn: Callable[..., dict] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Transcribe audio using parallel chunking, global timestamp alignment, and boundary deduplication."""
    if isinstance(media_or_audio, str):
        meta = ffprobe(media_or_audio)
        total_duration_s = _finite(meta.get("duration")) or 0.0
        if not meta.get("hasAudio") or total_duration_s <= 0:
            return {
                "language": language or "unknown",
                "text": "",
                "segments": [],
                "duration": round(total_duration_s, 3),
            }
        if total_duration_s <= (chunk_duration_s + overlap_s):
            fn = transcribe_fn or transcribe
            return fn(media_or_audio, language=language)

        windows = plan_chunk_windows(
            total_duration_s,
            chunk_duration_s=chunk_duration_s,
            overlap_s=overlap_s,
            start_s=0.0,
        )
        completed_chunks: list[dict[str, Any]] = []
        detected_language = language or "en"
        completed_count = 0
        total_chunks = len(windows)

        for chunk_result in iter_transcribe_chunks(
            media_or_audio,
            start_seconds=0.0,
            end_seconds=total_duration_s,
            language=language,
            chunk_duration_s=chunk_duration_s,
            overlap_s=overlap_s,
            concurrency=concurrency,
            max_retries=max_retries,
            transcribe_fn=transcribe_fn,
            fail_fast=True,
        ):
            completed_chunks.append(chunk_result)
            if chunk_result.get("language") and not language:
                detected_language = chunk_result["language"]
            completed_count += 1
            if progress_callback:
                try:
                    progress_callback(completed_count, total_chunks)
                except Exception:
                    pass
    else:
        audio = media_or_audio
        if not isinstance(audio, np.ndarray) or len(audio) == 0:
            return {
                "language": language or "unknown",
                "text": "",
                "segments": [],
                "duration": 0.0,
            }

        total_duration_s = len(audio) / WHISPER_SAMPLE_RATE
        if total_duration_s <= (chunk_duration_s + overlap_s):
            fn = transcribe_fn or transcribe
            return fn(audio, language=language)

        chunks = split_audio_chunks(
            audio,
            sample_rate=WHISPER_SAMPLE_RATE,
            chunk_duration_s=chunk_duration_s,
            overlap_s=overlap_s,
        )
        if not chunks:
            return {
                "language": language or "unknown",
                "text": "",
                "segments": [],
                "duration": round(total_duration_s, 3),
            }

        pool_workers = concurrency if (concurrency and concurrency > 0) else get_default_concurrency()
        completed_chunks = []
        detected_language = language or "en"

        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_workers) as executor:
            future_map = {
                executor.submit(
                    transcribe_single_chunk,
                    chunk,
                    language=language,
                    transcribe_fn=transcribe_fn,
                    max_retries=max_retries,
                ): chunk["index"]
                for chunk in chunks
            }
            completed_count = 0
            total_chunks = len(chunks)
            for future in concurrent.futures.as_completed(future_map):
                chunk_result = future.result()
                completed_chunks.append(chunk_result)
                if chunk_result.get("language") and not language:
                    detected_language = chunk_result["language"]
                completed_count += 1
                if progress_callback:
                    try:
                        progress_callback(completed_count, total_chunks)
                    except Exception:
                        pass

    completed_chunks.sort(key=lambda c: c["index"])
    raw_segments: list[dict[str, Any]] = []
    for c in completed_chunks:
        raw_segments.extend(c.get("segments", []))

    deduped_segments = deduplicate_boundary_words(raw_segments, tolerance_s=overlap_s * 0.75)
    full_text = " ".join(
        str(s.get("text", "")).strip() for s in deduped_segments if str(s.get("text", "")).strip()
    )

    return {
        "language": detected_language,
        "text": full_text,
        "segments": deduped_segments,
        "duration": round(total_duration_s, 3),
    }
