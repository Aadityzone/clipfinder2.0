"""On-screen text and action-oriented visual signals.

OCR is optional (pytesseract plus the Tesseract executable). The local action
signals are visual heuristics, not claims that a game event was semantically
understood. Every result includes availability/feature provenance.
"""
from __future__ import annotations

import os
import re

import cv2
import numpy as np

ACTION_TERMS = {
    "combat": ("kill", "eliminated", "headshot", "attack", "damage", "enemy", "defeat"),
    "victory": ("victory", "winner", "win", "champion", "completed", "success", "level up"),
    "failure": ("game over", "defeat", "failed", "eliminated", "you died", "try again"),
    "score_change": ("score", "points", "combo", "streak", "rank", "xp"),
    "stream_overlay": ("subscribed", "subscriber", "donation", "donated", "follow", "following", "chat"),
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _classify_ocr(text: str) -> list[str]:
    low = text.lower()
    found = []
    for label, terms in ACTION_TERMS.items():
        if any(term in low for term in terms):
            found.append(label)
    return found


def analyze_on_screen(path: str, max_samples: int = 90, ocr_enabled: bool = True) -> dict:
    if not os.path.isfile(path):
        return {"available": False, "samples": [], "reason": "media not found"}

    try:
        import pytesseract
    except Exception:
        pytesseract = None

    binary = os.getenv("TESSERACT_CMD")
    if pytesseract is not None and binary:
        pytesseract.pytesseract.tesseract_cmd = binary

    ocr_available = bool(ocr_enabled and pytesseract is not None)
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frames / fps if fps else 0.0
    if duration <= 0:
        cap.release()
        return {"available": False, "samples": [], "reason": "invalid video duration"}

    step = max(1.5, duration / max_samples)
    samples = []
    t = 0.0
    while t < duration and len(samples) < max_samples:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            t += step
            continue
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 150)
        edge_density = float(np.mean(edges > 0))
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturation = float(np.mean(hsv[:, :, 1]) / 255.0)
        # HUD-like content is more common around the perimeter than the center.
        border = np.concatenate([
            gray[:max(1, int(h * .18)), :].ravel(),
            gray[-max(1, int(h * .18)):, :].ravel(),
            gray[:, :max(1, int(w * .14))].ravel(),
            gray[:, -max(1, int(w * .14)):].ravel(),
        ])
        border_edges = cv2.Canny(border.reshape(-1, 1), 70, 150)
        hud_density = float(np.mean(border_edges > 0))

        text = ""
        if ocr_available:
            try:
                # Upscale small HUD labels and limit OCR work to sampled frames.
                crop = cv2.resize(gray, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_CUBIC)
                text = _clean_text(pytesseract.image_to_string(crop, config="--psm 11"))
            except Exception:
                text = ""

        events = _classify_ocr(text)
        samples.append({
            "time": round(t, 3),
            "ocrText": text[:500],
            "ocrAvailable": ocr_available,
            "actionLabels": events,
            "edgeDensity": round(edge_density, 4),
            "saturation": round(saturation, 4),
            "hudDensity": round(hud_density, 4),
            "gameplayLike": bool(hud_density > 0.035 and edge_density > 0.045),
        })
        t += step

    cap.release()
    return {
        "available": True,
        "ocrAvailable": ocr_available,
        "durationS": round(duration, 3),
        "sampleCount": len(samples),
        "samples": samples,
    }
