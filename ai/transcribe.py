from __future__ import annotations

import os
import math
from threading import Lock
from typing import Any

from faster_whisper import WhisperModel

_model: Any = None
_model_lock = Lock()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def model():
    """Load the configured Whisper model once, even under concurrent requests."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                device = os.getenv("WHISPER_DEVICE", "auto")
                compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                _model = WhisperModel(
                    os.getenv("WHISPER_MODEL", "small"),
                    device=device,
                    compute_type=compute,
                )
    return _model


def transcribe(path: str, language: str | None = None) -> dict:
    segments, info = model().transcribe(
        path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    output = []
    duration = _finite(getattr(info, "duration", None))
    duration_limit = duration if duration is not None and duration > 0 else None
    for segment in segments:
        start = _finite(getattr(segment, "start", None))
        end = _finite(getattr(segment, "end", None))
        if start is None or end is None or start < 0 or end <= start:
            continue
        if duration_limit is not None:
            if start >= duration_limit:
                continue
            end = min(end, duration_limit)
        if end <= start:
            continue
        words = []
        for word in getattr(segment, "words", None) or []:
            word_start = _finite(getattr(word, "start", None))
            word_end = _finite(getattr(word, "end", None))
            if word_start is None or word_end is None or word_end <= word_start:
                continue
            # Whisper word alignment can cross a segment edge by a few
            # milliseconds. Keep only the part supported by its parent segment.
            word_start = max(start, word_start)
            word_end = min(end, word_end)
            if word_end <= word_start:
                continue
            probability = _finite(getattr(word, "probability", None))
            if probability is not None and not 0.0 <= probability <= 1.0:
                probability = None
            word_text = getattr(word, "word", "")
            words.append({
                "start": word_start,
                "end": word_end,
                "word": word_text if isinstance(word_text, str) else str(word_text),
                "confidence": probability,
            })
        words.sort(key=lambda word: (word["start"], word["end"]))
        raw_text = getattr(segment, "text", "")
        segment_text = raw_text.strip() if isinstance(raw_text, str) else str(raw_text or "").strip()
        output.append({
            "start": start,
            "end": end,
            "text": segment_text,
            "confidence": None,
            "words": words,
        })
    output.sort(key=lambda segment: (segment["start"], segment["end"]))
    text_parts = [segment["text"] for segment in output]
    return {
        "language": info.language,
        "text": " ".join(part for part in text_parts if part),
        "segments": output,
        "duration": duration_limit if duration_limit is not None else (duration or 0.0),
    }
