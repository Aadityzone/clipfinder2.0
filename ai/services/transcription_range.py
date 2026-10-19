"""Bounded source-range transcription for long-form media."""

from __future__ import annotations

import math
import os
import subprocess
import tempfile

from ai.transcribe import transcribe

MAX_TRANSCRIPTION_RANGE_SECONDS = 60 * 60


def validate_transcription_range(start: float, end: float, source_duration: float) -> tuple[float, float]:
    """Validate a half-open source interval and cap each request at one hour."""
    try:
        start_value = float(start)
        end_value = float(end)
        duration_value = float(source_duration)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Source range timestamps and media duration must be numeric.") from exc
    if not all(math.isfinite(value) for value in (start_value, end_value, duration_value)):
        raise ValueError("Source range timestamps and media duration must be finite.")
    if start_value < 0:
        raise ValueError("Source range cannot start before zero.")
    if end_value <= start_value:
        raise ValueError("Source range end must be after its start.")
    if duration_value <= 0 or end_value > duration_value + 0.05:
        raise ValueError("Source range extends beyond the available media duration.")
    if end_value - start_value > MAX_TRANSCRIPTION_RANGE_SECONDS:
        raise ValueError("Each transcription request is limited to one hour. Split the remaining source into queued ranges.")
    return start_value, min(end_value, duration_value)


def transcribe_range(
    media_path: str,
    start: float,
    end: float,
    source_duration: float,
    language: str | None = None,
) -> dict:
    """Extract a bounded audio range, transcribe it, and restore source timestamps."""
    start_value, end_value = validate_transcription_range(start, end, source_duration)
    duration = end_value - start_value
    with tempfile.TemporaryDirectory(prefix="clipfinder-transcribe-range-") as temporary:
        audio_path = os.path.join(temporary, "range.wav")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(start_value), "-i", media_path, "-t", str(duration),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                    audio_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Audio extraction timed out for the requested source range.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "FFmpeg could not extract audio for this source range.").strip()
            raise RuntimeError(detail[-1200:]) from exc

        result = transcribe(audio_path, language)
    for segment in result.get("segments", []):
        segment["start"] = round(float(segment["start"]) + start_value, 3)
        segment["end"] = round(float(segment["end"]) + start_value, 3)
        for word in segment.get("words", []):
            word["start"] = round(float(word["start"]) + start_value, 3)
            word["end"] = round(float(word["end"]) + start_value, 3)
    result["duration"] = round(min(duration, float(result.get("duration") or duration)), 3)
    result["sourceStartS"] = start_value
    result["sourceEndS"] = end_value
    return result
