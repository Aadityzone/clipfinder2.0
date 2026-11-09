"""Media inspection and compatibility probe using ffprobe."""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path


class MediaProbeError(RuntimeError):
    """Raised when media probing fails."""
    pass


class CorruptedMediaError(MediaProbeError):
    """Raised when media file is corrupted, unreadable, or missing vital streams."""
    pass


def _parse_rational(val: str | None) -> float | None:
    """Safely parse FFmpeg rational fraction string (e.g. '30000/1001' or '30/1')."""
    if not val or not isinstance(val, str) or "/" not in val:
        try:
            num = float(val) if val else None
            return num if num and math.isfinite(num) and num > 0 else None
        except (ValueError, TypeError):
            return None
    try:
        num_s, den_s = val.split("/", 1)
        den = float(den_s)
        num = float(num_s)
        if den > 0 and math.isfinite(num) and math.isfinite(den):
            res = num / den
            return res if res > 0 else None
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return None


def _calculate_aspect_ratio(width: int | None, height: int | None, dar_string: str | None) -> str | None:
    """Determine aspect ratio from display_aspect_ratio tag or pixel dimensions."""
    if dar_string and isinstance(dar_string, str) and ":" in dar_string and dar_string != "0:1":
        return dar_string
    if not width or not height or width <= 0 or height <= 0:
        return None
    # Compute GCD or match common video aspect ratios
    ratio = width / height
    common_ratios = [
        (16 / 9, "16:9"),
        (9 / 16, "9:16"),
        (4 / 3, "4:3"),
        (3 / 4, "3:4"),
        (1 / 1, "1:1"),
        (21 / 9, "21:9"),
    ]
    for target_ratio, label in common_ratios:
        if abs(ratio - target_ratio) < 0.02:
            return label
    divisor = math.gcd(width, height)
    if divisor > 1 and divisor < max(width, height):
        return f"{width // divisor}:{height // divisor}"
    return f"{width}:{height}"


def ffprobe(path: str, timeout: float = 60.0, strict: bool = False) -> dict:
    """
    Run ffprobe against a local media file and return normalized compatibility metadata.
    Preserves all Phase 1 keys while adding full stream, codec, and container diagnostics.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Media file does not exist: {path}")

    # Check zero-byte file immediately
    try:
        file_size = os.path.getsize(path)
        if file_size == 0:
            if strict:
                raise CorruptedMediaError(f"Media file is empty (0 bytes): {path}")
            return {
                "duration": 0.0,
                "width": None,
                "height": None,
                "fps": None,
                "codec": None,
                "hasAudio": False,
                "has_audio": False,
                "audioCodec": None,
                "audio_codec": None,
                "audioStreamsCount": 0,
                "audio_streams_count": 0,
                "videoStreamsCount": 0,
                "video_streams_count": 0,
                "aspectRatio": None,
                "aspect_ratio": None,
                "bitrate": None,
                "isVfr": False,
                "is_vfr": False,
                "formatName": None,
                "format_name": None,
                "sizeBytes": 0,
                "size_bytes": 0,
                "isCorrupted": True,
                "is_corrupted": True,
            }
    except OSError as exc:
        raise MediaProbeError(f"Cannot inspect media file {path}: {exc}") from exc

    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
            text=True,
            timeout=timeout,
        )
        data = json.loads(raw)
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"ffprobe timed out after {timeout} seconds on {path}") from exc
    except subprocess.CalledProcessError as exc:
        if strict:
            raise CorruptedMediaError(f"ffprobe failed for corrupted media {path}: {exc}") from exc
        raise MediaProbeError(f"ffprobe failed for {path}: {exc}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise CorruptedMediaError(f"Invalid ffprobe output for {path}: {exc}") from exc
        raise MediaProbeError(f"ffprobe output invalid for {path}: {exc}") from exc

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    video = video_streams[0] if video_streams else None
    audio = audio_streams[0] if audio_streams else None

    # Duration: check format duration, then stream durations
    duration = 0.0
    try:
        duration = float(format_info.get("duration") or 0.0)
    except (ValueError, TypeError):
        pass
    if duration <= 0.0 and video:
        try:
            duration = float(video.get("duration") or 0.0)
        except (ValueError, TypeError):
            pass
    if duration <= 0.0 and audio:
        try:
            duration = float(audio.get("duration") or 0.0)
        except (ValueError, TypeError):
            pass

    # Frame rate and VFR detection
    fps = None
    is_vfr = False
    if video:
        r_fps = _parse_rational(video.get("r_frame_rate"))
        avg_fps = _parse_rational(video.get("avg_frame_rate"))
        fps = avg_fps or r_fps
        if r_fps and avg_fps and max(r_fps, avg_fps) > 0:
            rel_diff = abs(r_fps - avg_fps) / max(r_fps, avg_fps)
            if rel_diff > 0.01:
                is_vfr = True

    # Dimensions
    width = video.get("width") if video else None
    height = video.get("height") if video else None

    # Aspect Ratio
    aspect_ratio = _calculate_aspect_ratio(
        width, height,
        video.get("display_aspect_ratio") if video else None
    )

    # Bitrate
    bitrate = None
    try:
        raw_bitrate = format_info.get("bit_rate") or (video.get("bit_rate") if video else None)
        if raw_bitrate:
            bitrate = int(raw_bitrate)
    except (ValueError, TypeError):
        pass

    # Codecs
    video_codec = video.get("codec_name") if video else None
    audio_codec = audio.get("codec_name") if audio else None

    # Size bytes
    size_bytes = file_size
    try:
        if format_info.get("size"):
            size_bytes = int(format_info["size"])
    except (ValueError, TypeError):
        pass

    format_name = format_info.get("format_name")

    # Corruption checks
    is_corrupted = False
    if duration <= 0.0 or (not video_streams and not audio_streams):
        is_corrupted = True

    if strict and is_corrupted:
        raise CorruptedMediaError(
            f"Media file {path} is corrupted: duration={duration}, video_streams={len(video_streams)}, audio_streams={len(audio_streams)}"
        )

    return {
        # Original Phase 1 contract fields (DO NOT REMOVE OR CHANGE TYPES)
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": video_codec,
        "hasAudio": bool(audio_streams),
        # Enhanced Media Compatibility fields (both camelCase and snake_case)
        "has_audio": bool(audio_streams),
        "audioCodec": audio_codec,
        "audio_codec": audio_codec,
        "audioStreamsCount": len(audio_streams),
        "audio_streams_count": len(audio_streams),
        "videoStreamsCount": len(video_streams),
        "video_streams_count": len(video_streams),
        "aspectRatio": aspect_ratio,
        "aspect_ratio": aspect_ratio,
        "bitrate": bitrate,
        "isVfr": is_vfr,
        "is_vfr": is_vfr,
        "formatName": format_name,
        "format_name": format_name,
        "sizeBytes": size_bytes,
        "size_bytes": size_bytes,
        "isCorrupted": is_corrupted,
        "is_corrupted": is_corrupted,
    }
