"""Bounded audio activity features used for candidate proposal and ranking."""
from __future__ import annotations

import os
import re
import subprocess


def loudness_windows(path: str, window: float = 5.0) -> list[dict]:
    """Approximate per-window loudness with capped samples and subprocess timeouts."""
    if not os.path.isfile(path):
        return []
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    try:
        duration = max(0.0, float(probe.stdout.strip()))
    except (ValueError, AttributeError):
        return []
    if not duration or not window or window < 0:
        return []

    # Analyze at most 120 windows; very long videos are sampled coarsely.
    step = max(window, duration / 120.0)
    rows = []
    t = 0.0
    while t < duration and len(rows) < 120:
        length = min(step, duration - t)
        mean = peak_db = None
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                 "-t", f"{length:.3f}", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            text = result.stderr or ""
            match = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", text)
            peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", text)
            mean = float(match.group(1)) if match else None
            peak_db = float(peak.group(1)) if peak else mean
        except (OSError, subprocess.SubprocessError, ValueError):
            # Keep the time grid intact when one segment fails; never invent energy.
            pass
        energy = max(0.0, min(1.0, (mean + 45.0) / 45.0)) if mean is not None else 0.0
        rows.append({
            "start": round(t, 3),
            "end": round(t + length, 3),
            "meanDb": mean,
            "peakDb": peak_db,
            "energy": round(energy, 3),
        })
        t += step
    return rows


def summarize_window(audio: list[dict], start: float, end: float) -> dict:
    rows = [
        item for item in audio
        if float(item["end"]) > start and float(item["start"]) < end
    ]
    means = [float(item["meanDb"]) for item in rows if item.get("meanDb") is not None]
    peaks = [float(item["peakDb"]) for item in rows if item.get("peakDb") is not None]
    if not means:
        return {"meanDb": None, "peakDb": None, "energy": 0.0}
    mean_db = sum(means) / len(means)
    peak_db = max(peaks) if peaks else mean_db
    energy = max(0.0, min(1.0, (mean_db + 45.0) / 45.0))
    return {"meanDb": round(mean_db, 2), "peakDb": round(peak_db, 2), "energy": round(energy, 3)}
