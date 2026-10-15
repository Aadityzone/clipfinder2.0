from __future__ import annotations

import os
from threading import Lock
from typing import Any

from faster_whisper import WhisperModel

_model: Any = None
_model_lock = Lock()


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
    text_parts = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            words.append({
                "start": float(word.start),
                "end": float(word.end),
                "word": word.word,
                "confidence": float(word.probability) if word.probability is not None else None,
            })
        segment_text = segment.text.strip()
        output.append({
            "start": float(segment.start),
            "end": float(segment.end),
            "text": segment_text,
            "confidence": None,
            "words": words,
        })
        text_parts.append(segment_text)

    duration = float(getattr(info, "duration", 0) or 0)
    return {
        "language": info.language,
        "text": " ".join(part for part in text_parts if part),
        "segments": output,
        "duration": duration,
    }
