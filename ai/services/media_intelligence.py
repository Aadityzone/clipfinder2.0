import os
import re
import subprocess

from .audio_intelligence import loudness_windows

def audio_features(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True
    )
    text = p.stderr
    mean = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", text)
    peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", text)
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    windows = loudness_windows(path)
    return {
        "meanDb": float(mean.group(1)) if mean else None,
        "peakDb": float(peak.group(1)) if peak else None,
        "durationS": (int(duration.group(1))*3600 + int(duration.group(2))*60 +
                      float(duration.group(3))) if duration else None,
        "windowCount": len(windows),
    }, windows

def scene_features(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path,
         "-vf", "select='gt(scene,0.4)',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True
    )
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", p.stderr)]
    return {"sceneChanges": times[:500], "sceneChangeCount": len(times)}

def face_features(path: str) -> dict:
    try:
        import cv2
    except ImportError:
        return {"available": False, "faces": []}
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frames / fps if fps else 0
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
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
                    "x": round((x + w/2) / max(frame.shape[1], 1), 4),
                    "y": round((y + h/2) / max(frame.shape[0], 1), 4),
                    "w": round(w / max(frame.shape[1], 1), 4),
                    "h": round(h / max(frame.shape[0], 1), 4),
                })
        t += step
    cap.release()
    return {"available": True, "faces": samples, "faceSampleCount": len(samples)}

def analyze_media(path: str) -> dict:
    audio, windows = audio_features(path)
    return {
        "audio": audio,
        "audioWindows": windows,
        "scenes": scene_features(path),
        "vision": face_features(path),
    }
