import os
import time
from threading import Lock
from typing import Any

from .services.media import ffprobe

try:
    from faster_whisper import WhisperModel
    _WHISPER_IMPORT_ERROR = None
except Exception as exc:  # Keep silent-video and non-transcription routes available.
    WhisperModel = None
    _WHISPER_IMPORT_ERROR = exc

_model: Any = None
_model_lock = Lock()
DEFAULT_TRANSCRIBE_TIMEOUT = float(os.getenv("WHISPER_TIMEOUT_SECONDS", "3600"))


def model():
    """Load the configured Whisper model once, even under concurrent requests."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if WhisperModel is None:
                    raise RuntimeError(
                        "faster-whisper is unavailable in this AI service environment."
                    ) from _WHISPER_IMPORT_ERROR
                device = os.getenv("WHISPER_DEVICE", "auto")
                compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                _model = WhisperModel(
                    os.getenv("WHISPER_MODEL", "small"),
                    device=device,
                    compute_type=compute,
                )
    return _model


def transcription_capabilities() -> dict:
    return {
        "available": WhisperModel is not None,
        "model": os.getenv("WHISPER_MODEL", "small") if WhisperModel is not None else None,
        "reason": None if WhisperModel is not None else "faster-whisper could not be loaded",
    }


def transcribe(path: str, language: str | None = None, timeout: float | None = None) -> dict:
    effective_timeout = timeout if timeout is not None else DEFAULT_TRANSCRIBE_TIMEOUT
    segments, info = model().transcribe(
        path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    output = []
    text_parts = []
    start_time = time.time()
    for segment in segments:
        if effective_timeout and (time.time() - start_time) > effective_timeout:
            raise RuntimeError(f"Whisper transcription timed out after {int(effective_timeout)}s")
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


def transcribe_media(
    path: str,
    language: str | None = None,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> dict:
    """Transcribe available audio, returning an honest empty result for silent video."""
    if (start_seconds is None) != (end_seconds is None):
        raise ValueError("Both start_seconds and end_seconds are required for a source range.")

    metadata = ffprobe(path)
    source_duration = float(metadata.get("duration") or 0)
    if start_seconds is not None:
        from .services.transcription_range import validate_transcription_range

        start, end = validate_transcription_range(start_seconds, end_seconds, source_duration)
    else:
        start, end = 0.0, source_duration

    if not metadata.get("hasAudio"):
        return {
            "language": language or "unknown",
            "text": "",
            "segments": [],
            "duration": round(end - start, 3),
        }

    if start_seconds is not None:
        from .services.transcription_range import transcribe_range

        return transcribe_range(path, start, end, source_duration, language)
    return transcribe(path, language)
