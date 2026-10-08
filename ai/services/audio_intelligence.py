import os
import re
import subprocess

def loudness_windows(path: str, window: float = 5.0) -> list[dict]:
    """Approximate per-window loudness with bounded FFmpeg sampling.

    This deliberately caps work for long videos. It is an intelligence feature,
    not a render path, so coarse 5-second windows are preferable to spawning
    hundreds of processes.
    """
    if not os.path.isfile(path):
        return []
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        duration = max(0.0, float(probe.stdout.strip()))
    except ValueError:
        return []

    # Analyze at most 120 windows. Long videos are sampled rather than exhaustively scanned.
    step = max(window, duration / 120.0)
    rows = []
    t = 0.0
    while t < duration and len(rows) < 120:
        length = min(step, duration - t)
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
             "-t", f"{length:.3f}", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True
        )
        m = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", p.stderr)
        peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", p.stderr)
        mean = float(m.group(1)) if m else None
        peak_db = float(peak.group(1)) if peak else mean
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
    rows = [x for x in audio if float(x["end"]) > start and float(x["start"]) < end]
    means = [float(x["meanDb"]) for x in rows if x.get("meanDb") is not None]
    peaks = [float(x["peakDb"]) for x in rows if x.get("peakDb") is not None]
    if not means:
        return {"meanDb": None, "peakDb": None, "energy": 0.0}
    mean_db = sum(means) / len(means)
    peak_db = max(peaks) if peaks else mean_db
    energy = max(0.0, min(1.0, (mean_db + 45.0) / 45.0))
    return {"meanDb": round(mean_db, 2), "peakDb": round(peak_db, 2), "energy": round(energy, 3)}
