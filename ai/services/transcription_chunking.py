"""High-performance parallel audio transcription engine for long-form media.

Splits extracted audio into manageable chunks with controlled boundary overlap,
transcribes them concurrently across available hardware resources, preserves
accurate global timestamps, suppresses boundary word duplication, and independently
retries failed chunks.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import re
import time
from typing import Any, Callable

import numpy as np

from ai.transcribe import (
    WHISPER_SAMPLE_RATE,
    decode_audio,
    transcribe,
)

DEFAULT_CHUNK_DURATION_SECONDS = float(os.getenv("TRANSCRIPTION_CHUNK_SECONDS", "180.0"))
DEFAULT_OVERLAP_SECONDS = float(os.getenv("TRANSCRIPTION_CHUNK_OVERLAP_SECONDS", "1.0"))
DEFAULT_MAX_RETRIES = int(os.getenv("TRANSCRIPTION_CHUNK_RETRIES", "2"))


def get_default_concurrency() -> int:
    """Determine safe worker concurrency based on system CPU/hardware."""
    env_concurrency = os.getenv("TRANSCRIPTION_CONCURRENCY")
    if env_concurrency:
        try:
            val = int(env_concurrency)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    cpu_cores = os.cpu_count() or 2
    # Keep concurrency bounded to prevent RAM exhaustion and context-switching overhead
    return max(1, min(4, cpu_cores // 2))


def _normalize_word(word: str) -> str:
    """Normalize a word token for fuzzy boundary matching."""
    return re.sub(r"[^\w]", "", word.lower()).strip()


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
    """Clean duplicate words and duplicate segment fragments at chunk boundaries.

    When adjacent chunks overlap, words spoken in the overlap window can be
    transcribed by both chunks. This function identifies and suppresses duplicate
    words at boundaries while keeping chronological timestamps intact.
    """
    if not all_segments:
        return []

    # Sort segments chronologically
    sorted_segments = sorted(
        all_segments,
        key=lambda s: (float(s.get("start", 0)), float(s.get("end", 0))),
    )

    cleaned_segments: list[dict[str, Any]] = []
    seen_words: list[dict[str, Any]] = []

    for seg in sorted_segments:
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", 0))
        if seg_end <= seg_start:
            continue

        raw_words = seg.get("words") or []
        cleaned_words: list[dict[str, Any]] = []

        if raw_words:
            for w in raw_words:
                w_start = float(w.get("start", 0))
                w_end = float(w.get("end", 0))
                norm_text = _normalize_word(str(w.get("word", "")))
                if not norm_text:
                    continue

                # Check if this exact normalized word was already emitted recently
                # within the boundary tolerance window
                is_duplicate = False
                for prev in seen_words[-15:]:
                    if (
                        prev["norm"] == norm_text
                        and abs(w_start - prev["start"]) <= tolerance_s
                    ):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    cleaned_words.append(w)
                    seen_words.append({"norm": norm_text, "start": w_start, "end": w_end})

            if not cleaned_words:
                # All words in this segment were boundary duplicates
                continue

            # Update segment text and timestamps to match surviving words
            cleaned_text = "".join(str(w.get("word", "")) for w in cleaned_words).strip()
            if not cleaned_text:
                continue

            cleaned_segments.append({
                "start": min(float(cleaned_words[0]["start"]), seg_start),
                "end": max(float(cleaned_words[-1]["end"]), float(cleaned_words[0]["start"]) + 0.05),
                "text": cleaned_text,
                "confidence": seg.get("confidence"),
                "words": cleaned_words,
            })
        else:
            # Word-level timing was not emitted; perform segment-level deduplication
            seg_text = str(seg.get("text", "")).strip()
            norm_seg_text = _normalize_word(seg_text)
            if not norm_seg_text:
                continue

            is_duplicate = False
            for prev_seg in cleaned_segments[-3:]:
                prev_text = _normalize_word(str(prev_seg.get("text", "")))
                prev_end = float(prev_seg.get("end", 0))
                if norm_seg_text == prev_text and abs(seg_start - prev_end) <= (tolerance_s * 2):
                    is_duplicate = True
                    break

            if not is_duplicate:
                cleaned_segments.append(seg)

    return cleaned_segments


def transcribe_single_chunk(
    chunk: dict[str, Any],
    language: str | None = None,
    transcribe_fn: Callable[..., dict] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Transcribe one audio chunk with retry handling and shift timestamps to global space."""
    fn = transcribe_fn or transcribe
    start_offset = float(chunk["start_time"])
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            result = fn(chunk["audio"], language=language)
            segments = result.get("segments", [])

            # Shift segment and word timestamps by chunk global start offset
            shifted_segments: list[dict[str, Any]] = []
            for seg in segments:
                s_start = round(float(seg["start"]) + start_offset, 3)
                s_end = round(float(seg["end"]) + start_offset, 3)
                shifted_words: list[dict[str, Any]] = []
                for w in seg.get("words", []):
                    w_start = round(float(w["start"]) + start_offset, 3)
                    w_end = round(float(w["end"]) + start_offset, 3)
                    shifted_words.append({
                        **w,
                        "start": w_start,
                        "end": w_end,
                    })
                shifted_segments.append({
                    **seg,
                    "start": s_start,
                    "end": s_end,
                    "words": shifted_words,
                })

            return {
                "index": chunk["index"],
                "start_time": start_offset,
                "segments": shifted_segments,
                "language": result.get("language"),
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


def transcribe_chunked(
    media_or_audio: str | np.ndarray,
    language: str | None = None,
    chunk_duration_s: float = DEFAULT_CHUNK_DURATION_SECONDS,
    overlap_s: float = DEFAULT_OVERLAP_SECONDS,
    concurrency: int | None = None,
    transcribe_fn: Callable[..., dict] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Transcribe audio using parallel chunking, global timestamp alignment, and boundary deduplication."""
    if isinstance(media_or_audio, str):
        audio = decode_audio(media_or_audio)
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

    # If the audio is short enough to fit inside a single chunk window,
    # run direct transcription to avoid unnecessary chunking overhead
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
    completed_chunks: list[dict[str, Any]] = []
    detected_language = language or "en"

    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_workers) as executor:
        future_map = {
            executor.submit(
                transcribe_single_chunk,
                chunk,
                language=language,
                transcribe_fn=transcribe_fn,
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

    # Sort chunks by original chunk index
    completed_chunks.sort(key=lambda c: c["index"])

    # Flatten all raw segments
    raw_segments: list[dict[str, Any]] = []
    for c in completed_chunks:
        raw_segments.extend(c.get("segments", []))

    # Apply boundary word and segment deduplication
    deduped_segments = deduplicate_boundary_words(raw_segments, tolerance_s=overlap_s * 0.75)

    # Reconstruct whole text
    full_text = " ".join(
        str(s.get("text", "")).strip() for s in deduped_segments if str(s.get("text", "")).strip()
    )

    return {
        "language": detected_language,
        "text": full_text,
        "segments": deduped_segments,
        "duration": round(total_duration_s, 3),
    }
