"""Validation and extraction helpers for bounded multimodal analysis."""

from __future__ import annotations

import math
import os
import subprocess
from typing import Any

MAX_ANALYSIS_RANGE_SECONDS = 60 * 60


def validate_analysis_range(start: float, end: float, source_duration: float) -> tuple[float, float]:
    """Validate a source-media interval, capped to one hour."""
    try:
        start_value, end_value, duration_value = float(start), float(end), float(source_duration)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Analysis range timestamps and media duration must be numeric.") from exc
    if not all(math.isfinite(value) for value in (start_value, end_value, duration_value)):
        raise ValueError("Analysis range timestamps and media duration must be finite.")
    if duration_value <= 0 or start_value < 0 or start_value >= duration_value:
        raise ValueError("Analysis range must start inside the source media.")
    if end_value <= start_value:
        raise ValueError("Analysis range end must be after its start.")
    if end_value - start_value > MAX_ANALYSIS_RANGE_SECONDS:
        raise ValueError("Each multimodal analysis range is limited to one hour.")
    if end_value > duration_value + 0.05:
        raise ValueError("Analysis range extends beyond the source media duration.")
    return start_value, min(end_value, duration_value)


def shift_segments_to_range(segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    """Clip source-timestamped transcript segments to a range and make them local."""
    if not isinstance(segments, list):
        return []
    try:
        range_start, range_end = float(start), float(end)
    except (TypeError, ValueError, OverflowError):
        return []
    if not math.isfinite(range_start) or not math.isfinite(range_end) or range_end <= range_start:
        return []
    result: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            segment_start = float(segment.get("start"))
            segment_end = float(segment.get("end"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(segment_start) or not math.isfinite(segment_end) or segment_end <= segment_start:
            continue
        clipped_start = max(range_start, segment_start)
        clipped_end = min(range_end, segment_end)
        if clipped_end <= clipped_start:
            continue
        local = dict(segment)
        local["start"] = round(clipped_start - start, 3)
        local["end"] = round(clipped_end - start, 3)
        result.append(local)
    return result


def extract_analysis_range(source_path: str, start: float, end: float, output_path: str) -> str:
    """Create a timestamp-zeroed, low-resolution analysis copy of one source range."""
    try:
        start_value, end_value = float(start), float(end)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Analysis range boundaries must be numeric.") from exc
    if not math.isfinite(start_value) or not math.isfinite(end_value):
        raise ValueError("Analysis range boundaries must be finite.")
    duration = end_value - start_value
    if duration <= 0 or duration > MAX_ANALYSIS_RANGE_SECONDS:
        raise ValueError("Analysis range duration must be greater than zero and at most one hour.")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start_value), "-i", source_path, "-t", str(duration),
                "-map", "0:v:0", "-map", "0:a?",
                "-vf", "fps=2,scale=640:-2",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-ac", "1", "-ar", "16000",
                "-movflags", "+faststart", output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg timed out preparing the bounded analysis range.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "FFmpeg could not prepare the bounded analysis range.").strip()
        raise RuntimeError(detail[-1200:]) from exc
    if not os.path.isfile(output_path) or os.path.getsize(output_path) < 1024:
        raise RuntimeError("FFmpeg did not produce a valid bounded analysis file.")
    return output_path
