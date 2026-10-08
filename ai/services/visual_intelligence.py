"""Visual intelligence for clip discovery.

The default path is lightweight and local: sampled frames, perceptual change,
motion, brightness and composition. An optional CLIP backend can add semantic
frame/text similarity when its local model runtime is installed. No API key is
required and unavailable models are reported instead of faking results.
"""
from __future__ import annotations

import os
from functools import lru_cache

import cv2
import numpy as np


def _frame_signature(frame: np.ndarray) -> np.ndarray:
    small = cv2.resize(frame, (64, 36))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    return np.concatenate([hist, edges.mean(axis=1) / 255.0])


def _motion(prev: np.ndarray | None, current: np.ndarray) -> float:
    if prev is None:
        return 0.0
    a = cv2.resize(prev, (160, 90))
    b = cv2.resize(current, (160, 90))
    flow = cv2.calcOpticalFlowFarneback(
        cv2.cvtColor(a, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(b, cv2.COLOR_BGR2GRAY),
        None, 0.5, 3, 15, 3, 5, 1.2, 0,
    )
    magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    return float(min(1.0, np.percentile(magnitude, 75) / 8.0))


def sample_visual_features(path: str, max_samples: int = 180) -> dict:
    if not os.path.isfile(path):
        return {"available": False, "samples": [], "reason": "media not found"}

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps else 0.0
    if duration <= 0:
        cap.release()
        return {"available": False, "samples": [], "reason": "invalid video duration"}

    step = max(0.5, duration / max_samples)
    samples = []
    previous = None
    previous_sig = None
    t = 0.0
    while t < duration and len(samples) < max_samples:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            t += step
            continue

        signature = _frame_signature(frame)
        visual_change = 0.0
        if previous_sig is not None:
            visual_change = float(min(1.0, np.mean(np.abs(signature - previous_sig)) * 3.0))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray) / 255.0)
        motion = _motion(previous, frame)

        h, w = frame.shape[:2]
        center_crop = frame[int(h * .2):int(h * .8), int(w * .2):int(w * .8)]
        center_energy = float(cv2.Laplacian(cv2.cvtColor(center_crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        samples.append({
            "time": round(t, 3),
            "visualChange": round(visual_change, 4),
            "motion": round(motion, 4),
            "brightness": round(brightness, 4),
            "centerDetail": round(min(1.0, center_energy / 1200.0), 4),
        })
        previous = frame
        previous_sig = signature
        t += step

    cap.release()
    return {
        "available": True,
        "durationS": round(duration, 3),
        "sampleCount": len(samples),
        "samples": samples,
    }


@lru_cache(maxsize=1)
def _clip_model():
    if os.getenv("VISUAL_SEMANTIC_BACKEND", "").lower() != "clip":
        return None
    try:
        from transformers import CLIPModel, CLIPProcessor
    except Exception:
        return None
    model_name = os.getenv("VISUAL_CLIP_MODEL", "openai/clip-vit-base-patch32")
    try:
        return CLIPProcessor.from_pretrained(model_name), CLIPModel.from_pretrained(model_name)
    except Exception:
        return None


def visual_capabilities() -> dict:
    return {
        "local_features": True,
        "semantic_backend": "clip" if _clip_model() is not None else None,
        "clip_model": os.getenv("VISUAL_CLIP_MODEL", "openai/clip-vit-base-patch32"),
    }


def semantic_frame_scores(path: str, query: str, max_samples: int = 60) -> list[dict]:
    backend = _clip_model()
    if backend is None or not query.strip():
        return []

    processor, model = backend
    import torch
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frames / fps if fps else 0.0
    step = max(1.0, duration / max_samples)
    result = []
    with torch.no_grad():
        text_inputs = processor(text=[query], return_tensors="pt", padding=True)
        text_features = model.get_text_features(**text_inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        t = 0.0
        while t < duration and len(result) < max_samples:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                inputs = processor(images=image, return_tensors="pt")
                image_features = model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                similarity = float((image_features @ text_features.T)[0, 0].item())
                result.append({"time": round(t, 3), "score": round((similarity + 1) * 50, 3)})
            t += step
    cap.release()
    return result
