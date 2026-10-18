import math
import os
import subprocess

import numpy as np


def _window_stats(samples: np.ndarray) -> tuple[float | None, float | None, float]:
    if samples.size == 0:
        return None, None, 0.0
    values = np.nan_to_num(samples.astype(np.float64, copy=False), nan=0.0, posinf=0.0, neginf=0.0)
    rms = float(np.sqrt(np.mean(values * values)))
    peak = float(np.max(np.abs(values)))
    mean_db = max(-120.0, 20.0 * math.log10(max(rms, 1e-9)))
    peak_db = max(-120.0, 20.0 * math.log10(max(peak, 1e-9)))
    energy = max(0.0, min(1.0, (mean_db + 45.0) / 45.0))
    return round(mean_db, 2), round(peak_db, 2), round(energy, 3)


def loudness_windows(path: str, window: float = 5.0) -> list[dict]:
    """Measure bounded audio windows with one FFmpeg decode process.

    Audio is downmixed to mono 8 kHz float PCM and streamed window-by-window.
    This avoids spawning a separate FFmpeg process for every interval, which
    made long videos spend most of their analysis time repeatedly seeking.
    """
    if not os.path.isfile(path):
        return []

    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=20,
        )
        if probe.returncode != 0:
            return []
        duration = max(0.0, float(probe.stdout.strip()))
    except (OSError, subprocess.SubprocessError, ValueError, OverflowError):
        return []
    if duration <= 0:
        return []

    sample_rate = 8000
    safe_window = max(0.25, float(window))
    step = max(safe_window, duration / 120.0)
    samples_per_window = max(1, int(round(step * sample_rate)))
    chunk_bytes = samples_per_window * 4
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1",
    ]
    process = None
    rows: list[dict] = []
    elapsed = 0.0
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if process.stdout is None:
            return []
        while elapsed < duration and len(rows) < 120:
            raw = process.stdout.read(chunk_bytes)
            if not raw:
                break
            raw = raw[:len(raw) - (len(raw) % 4)]
            if not raw:
                break
            samples = np.frombuffer(raw, dtype="<f4")
            mean_db, peak_db, energy = _window_stats(samples)
            actual_length = min(duration - elapsed, samples.size / sample_rate)
            if actual_length <= 0:
                break
            rows.append({
                "start": round(elapsed, 3),
                "end": round(elapsed + actual_length, 3),
                "meanDb": mean_db,
                "peakDb": peak_db,
                "energy": energy,
            })
            elapsed += actual_length
        if process.stdout is not None and not getattr(process.stdout, "closed", False):
            process.stdout.close()
        try:
            process.wait(timeout=5)
        except TypeError:
            process.wait()
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=5)
            except (TypeError, subprocess.SubprocessError):
                pass
        if process.returncode and not rows:
            return []
    except (OSError, subprocess.SubprocessError):
        return rows
    finally:
        if process is not None:
            if process.stdout is not None and not getattr(process.stdout, "closed", False):
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=2)
                except (TypeError, subprocess.SubprocessError):
                    pass
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
