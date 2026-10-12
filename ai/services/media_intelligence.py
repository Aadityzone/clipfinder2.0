"""Orchestrate inexpensive audio, visual, scene and on-screen media signals.

Each optional analysis stage degrades independently: unavailable media or a failed
FFmpeg/OpenCV stage should not prevent transcript-based candidate generation.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from .audio_intelligence import loudness_windows
from .visual_intelligence import sample_visual_features
from .action_intelligence import analyze_on_screen


def audio_features(path: str) -> tuple[dict[str, Any], list[dict]]:
    """Return summary and windows consistently, including missing/unreadable media."""
    if not os.path.isfile(path):
        return {}, []

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        text = result.stderr or ""
    except (OSError, subprocess.SubprocessError):
        text = ""

    mean = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", text)
    peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", text)
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\\.\d+)?)", text)

    try:
        windows = loudness_windows(path)
    except (OSError, subprocess.SubprocessError, ValueError):
        windows = []

    summary = {
        "meanDb": float(mean.group(1)) if mean else None,
        "peakDb": float(peak.group(1)) if peak else None,
        "durationS": (
            int(duration.group(1)) * 3600
            + int(duration.group(2)) * 60
            + float(duration.group(3))
        ) if duration else None,
        "windowCount": len(windows),
    }
    return summary, windows


def scene_features(path: str) -> dict:
    if not os.path.isfile(path):
        return {"sceneChanges": [], "sceneChangeCount": 0, "available": False}
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-i", path,
                "-vf", "select='gt(scene,0.4)',showinfo", "-an", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"sceneChanges": [], "sceneChangeCount": 0, "available": False}

    times = [
        float(match.group(1))
        for match in re.finditer(r"pts_time:([0-9.]+)", result.stderr or "")
    ]
    times = times[:500]
    return {
        "sceneChanges": times,
        "sceneChangeCount": len(times),
        "available": result.returncode == 0,
    }


def face_features(path: str) -> dict:
    try:
        import cv2
    except ImportError:
        return {"available": False, "faces": []}
    if not os.path.isfile(path):
        return {"available": False, "faces": [], "reason": "media not found"}

    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return {"available": False, "faces": [], "reason": "video could not be opened"}
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frames / fps if fps else 0
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if cascade.empty():
            return {"available": False, "faces": [], "reason": "face detector unavailable"}
        samples, t = [], 0.0
        step = max(1.0, min(3.0, duration / 60 if duration else 3.0))
        while t < duration and len(samples) < 180:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
                for x, y, w, h in faces[:8]:
                    samples.append({
                        "time": round(t, 3),
                        "x": round((x + w / 2) / max(frame.shape[1], 1), 4),
                        "y": round((y + h / 2) / max(frame.shape[0], 1), 4),
                        "w": round(w / max(frame.shape[1], 1), 4),
                        "h": round(h / max(frame.shape[0], 1), 4),
                    })
            t += step
        return {"available": True, "faces": samples, "faceSampleCount": len(samples)}
    except Exception as exc:
        # Face detection is auxiliary; report its failure without aborting analysis.
        return {"available": False, "faces": [], "reason": type(exc).__name__}
    finally:
        cap.release()


def analyze_media(path: str) -> dict:
    """Run each media intelligence stage independently and preserve partial results."""
    audio, windows = audio_features(path)
    try:
        visual = sample_visual_features(path)
    except Exception as exc:
        visual = {"available": False, "samples": [], "reason": type(exc).__name__}
    try:
        on_screen = analyze_on_screen(path)
    except Exception as exc:
        on_screen = {"available": False, "samples": [], "reason": type(exc).__name__}
    try:
        scenes = scene_features(path)
    except Exception as exc:
        scenes = {"available": False, "sceneChanges": [], "sceneChangeCount": 0,
                  "reason": type(exc).__name__}
    try:
        vision = face_features(path)
    except Exception as exc:
        vision = {"available": False, "faces": [], "reason": type(exc).__name__}
    return {
        "audio": audio,
        "audioWindows": windows,
        "scenes": scenes,
        "vision": vision,
        "visual": visual,
        "onScreen": on_screen,
    }
