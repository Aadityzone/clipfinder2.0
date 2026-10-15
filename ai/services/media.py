"""Bounded FFprobe metadata extraction shared by ingestion and rendering."""

import json
import math
import subprocess


FFPROBE_TIMEOUT_SECONDS = 30


def ffprobe(path: str):
    """Return normalized media metadata, failing promptly for unreadable inputs."""
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", path,
        ],
        text=True,
        timeout=FFPROBE_TIMEOUT_SECONDS,
    )
    data = json.loads(raw)
    streams = data.get("streams", [])
    if not isinstance(streams, list):
        streams = []
    video = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    audio = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"),
        None,
    )

    fps = None
    if video:
        rate = str(video.get("r_frame_rate", ""))
        if "/" in rate:
            numerator, denominator = rate.split("/", 1)
            try:
                numerator_value = float(numerator)
                denominator_value = float(denominator)
                candidate = numerator_value / denominator_value if denominator_value else 0.0
                if math.isfinite(candidate) and candidate > 0:
                    fps = candidate
            except (TypeError, ValueError, OverflowError):
                fps = None

    try:
        duration = float((data.get("format") or {}).get("duration") or 0)
    except (AttributeError, TypeError, ValueError, OverflowError):
        duration = 0.0
    if not math.isfinite(duration) or duration < 0:
        duration = 0.0

    return {
        "duration": duration,
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": fps,
        "codec": video.get("codec_name") if video else None,
        "hasAudio": audio is not None,
    }
