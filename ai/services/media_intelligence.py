import math
import os
import re
import subprocess

from .audio_intelligence import loudness_windows
from .visual_intelligence import sample_visual_features
from .action_intelligence import analyze_on_screen

import time


def _finite(value) -> float | None:
    """Coerce an optional measurement to a finite float without raising."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def audio_features(path: str) -> tuple[dict, list]:
    """Summarize loudness from the same single decode used for window energy.

    This used to run a separate full-file `volumedetect` pass and then a second
    full-file windowed decode. On long sources the duplicated decode dominated
    analysis time. The windowed pass already reports per-window RMS (meanDb) and
    peak (peakDb), so the redundant decode is removed. Values describe measured
    loudness only; they are not evidence that a moment is funny or exciting.
    """
    if not os.path.isfile(path):
        return {"meanDb": None, "peakDb": None, "durationS": None, "windowCount": 0}, []
    windows = loudness_windows(path)
    if not windows:
        return {"meanDb": None, "peakDb": None, "durationS": None, "windowCount": 0}, []

    means = [value for value in (_finite(row.get("meanDb")) for row in windows) if value is not None]
    peaks = [value for value in (_finite(row.get("peakDb")) for row in windows) if value is not None]
    measured = [_finite(row.get("end")) for row in windows]
    duration = max((value for value in measured if value is not None), default=None)
    return {
        "meanDb": round(sum(means) / len(means), 2) if means else None,
        "peakDb": round(max(peaks), 2) if peaks else None,
        "durationS": round(duration, 3) if duration else None,
        "windowCount": len(windows),
    }, windows

def scene_features(path: str) -> dict:
    """Detect scene changes on a bounded, downscaled 2-fps analysis stream."""
    if not os.path.isfile(path):
        return {}
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "info", "-i", path,
             "-vf", "fps=2,scale=320:-2,select='gt(scene,0.4)',showinfo",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {}
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", p.stderr)]
    return {"sceneChanges": times[:500], "sceneChangeCount": len(times)}

def face_features(path: str) -> dict:
    """Detect faces as an optional framing signal.

    Face detection must never fail the whole analysis: a missing OpenCV runtime,
    a missing Haar cascade data file, or an unreadable stream degrades to an
    unavailable result with a reason instead of raising into the API layer.
    """
    if not os.path.isfile(path):
        return {"available": False, "faces": [], "reason": "media not found"}
    try:
        import cv2
    except Exception as exc:
        return {"available": False, "faces": [], "reason": f"OpenCV is unavailable ({type(exc).__name__})"}

    capture = None
    try:
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            return {"available": False, "faces": [], "reason": "video could not be opened"}
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frames / fps if fps else 0
        if duration <= 0:
            return {"available": False, "faces": [], "reason": "invalid video duration"}

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return {"available": False, "faces": [], "reason": "face cascade data is unavailable"}

        samples, t = [], 0.0
        step = max(1.0, min(3.0, duration / 60 if duration else 3.0))
        start_time = time.time()
        while t < duration and len(samples) < 180:
            if time.time() - start_time > 60:
                break
            capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = capture.read()
            if ok:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
                for x, y, w, h in faces[:8]:
                    samples.append({
                        "time": round(t, 3),
                        "x": round((x + w/2) / max(frame.shape[1], 1), 4),
                        "y": round((y + h/2) / max(frame.shape[0], 1), 4),
                        "w": round(w / max(frame.shape[1], 1), 4),
                        "h": round(h / max(frame.shape[0], 1), 4),
                    })
            t += step
        return {"available": True, "faces": samples, "faceSampleCount": len(samples)}
    except Exception as exc:
        # Optional signal: report the failure, keep transcript/audio ranking usable.
        return {"available": False, "faces": [], "reason": f"face detection failed ({type(exc).__name__})"}
    finally:
        if capture is not None:
            capture.release()

def _isolate(producer, fallback):
    """Run one optional signal producer; a failure degrades only that signal."""
    try:
        return producer()
    except Exception:
        return fallback


def analyze_media(path: str) -> dict:
    """Collect multimodal evidence, isolating every optional signal.

    Audio, scene detection, faces, visual sampling and OCR may each be unavailable
    on a given host (missing native library, no OCR binary, unreadable stream).
    One failing signal must not fail the whole analysis: each block is collected
    independently and an absent block is simply omitted rather than being treated
    as negative evidence for that modality.
    """
    audio, windows = _isolate(lambda: audio_features(path), ({}, []))
    return {
        "audio": audio,
        "audioWindows": windows,
        "scenes": _isolate(lambda: scene_features(path), {}),
        "vision": _isolate(lambda: face_features(path), {}),
        "visual": _isolate(lambda: sample_visual_features(path), {}),
        "onScreen": _isolate(lambda: analyze_on_screen(path), {}),
    }
