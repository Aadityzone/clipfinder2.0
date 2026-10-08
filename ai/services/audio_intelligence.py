import math
import os
import re
import subprocess

def _duration(path: str) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True
    )
    try:
        return max(0.0, float(p.stdout.strip()))
    except ValueError:
        return 0.0

def loudness_windows(path: str, window: float = 2.0) -> list[dict]:
    if not os.path.isfile(path):
        return []
    duration = _duration(path)
    if duration <= 0:
        return []
    out = []
    t = 0.0
    while t < duration and len(out) < 2000:
        length = min(window, duration - t)
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", f"{t:.3f}", "-t", f"{length:.3f}",
             "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True
        )
        m = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", p.stderr)
        peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", p.stderr)
        out.append({
            "start": round(t, 3),
            "end": round(t + length, 3),
            "meanDb": float(m.group(1)) if m else None,
            "peakDb": float(peak.group(1)) if peak else None,
        })
        t += window
    return out

def summarize_window(audio: list[dict], start: float, end: float) -> dict:
    rows = [x for x in audio if float(x["end"]) > start and float(x["start"]) < end]
    means = [float(x["meanDb"]) for x in rows if x.get("meanDb") is not None]
    peaks = [float(x["peakDb"]) for x in rows if x.get("peakDb") is not None]
    if not means:
        return {"meanDb": None, "peakDb": None, "energy": 0.0}
    mean_db = sum(means) / len(means)
    peak_db = max(peaks) if peaks else mean_db
    energy = max(0.0, min(1.0, (mean_db + 45.0) / 45.0))
    return {"meanDb": round(mean_db, 2), "peakDb": round(peak_db, 2), "energy": round(energy, 3)}
