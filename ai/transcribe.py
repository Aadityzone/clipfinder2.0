import math
import os
import threading
import time
from typing import Any

from .services.media import ffprobe

try:
    from faster_whisper import WhisperModel
    _WHISPER_IMPORT_ERROR = None
except Exception as exc:  # Keep silent-video and non-transcription routes available.
    WhisperModel = None
    _WHISPER_IMPORT_ERROR = exc

_model: Any = None
_model_lock = threading.Lock()
_load_thread: threading.Thread | None = None
_load_result: dict[str, Any] = {}

DEFAULT_TRANSCRIBE_TIMEOUT = float(os.getenv("WHISPER_TIMEOUT_SECONDS", "3600"))
DEFAULT_LOAD_TIMEOUT = float(os.getenv("WHISPER_LOAD_TIMEOUT_SECONDS", "300"))


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _positive_seconds(raw: str | None, fallback: float) -> float:
    try:
        value = float(raw) if raw is not None else fallback
    except (TypeError, ValueError, OverflowError):
        return fallback
    return value if math.isfinite(value) and value > 0 else fallback


def _start_load(model_name: str, device: str, compute: str, local_only: bool) -> None:
    """Run the blocking model load on a daemon thread so it can be time-bounded."""
    global _load_thread, _load_result
    result: dict[str, Any] = {}

    def _worker() -> None:
        try:
            result["model"] = WhisperModel(
                model_name,
                device=device,
                compute_type=compute,
                local_files_only=local_only,
            )
        except BaseException as exc:  # surfaced to the caller as a clear error
            result["error"] = exc

    _load_thread = threading.Thread(target=_worker, name="whisper-model-load", daemon=True)
    _load_result = result
    _load_thread.start()


def _await_load(timeout: float, model_name: str) -> Any:
    thread, result = _load_thread, _load_result
    if thread is None:
        raise RuntimeError("Whisper model load was not started.")
    thread.join(timeout)
    if thread.is_alive():
        # Constructing WhisperModel may download hundreds of megabytes. A stalled
        # download used to hold the model lock forever, wedging every later
        # transcription request behind it. Fail with a bounded, actionable error.
        raise RuntimeError(
            f"Whisper model '{model_name}' did not load within {int(timeout)}s. "
            "Pre-download it, raise WHISPER_LOAD_TIMEOUT_SECONDS, or set "
            "WHISPER_LOCAL_FILES_ONLY=1 to fail fast when it is not cached."
        )
    if "model" in result:
        return result["model"]
    error = result.get("error")
    if isinstance(error, BaseException):
        raise RuntimeError(
            f"Whisper model '{model_name}' could not be loaded: {type(error).__name__}: {error}"
        ) from error
    raise RuntimeError(f"Whisper model '{model_name}' could not be loaded.")


def model():
    """Load the configured Whisper model once, even under concurrent requests.

    The load is bounded in time. It is also the only place a model download may
    happen, and it runs on a daemon thread so a stalled download cannot block the
    model lock (and therefore the whole transcription route) indefinitely.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if WhisperModel is None:
                    raise RuntimeError(
                        "faster-whisper is unavailable in this AI service environment."
                    ) from _WHISPER_IMPORT_ERROR
                model_name = os.getenv("WHISPER_MODEL", "small")
                timeout = _positive_seconds(
                    os.getenv("WHISPER_LOAD_TIMEOUT_SECONDS"), DEFAULT_LOAD_TIMEOUT
                )
                # Reuse a load that is already in flight instead of stacking another.
                if _load_thread is None or not _load_thread.is_alive():
                    _start_load(
                        model_name,
                        os.getenv("WHISPER_DEVICE", "auto"),
                        os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                        _env_flag("WHISPER_LOCAL_FILES_ONLY", False),
                    )
                _model = _await_load(timeout, model_name)
    return _model


def transcription_capabilities() -> dict:
    available = WhisperModel is not None
    return {
        "available": available,
        "model": os.getenv("WHISPER_MODEL", "small") if available else None,
        "reason": None if available else "faster-whisper could not be loaded",
        "loaded": _model is not None,
        "localFilesOnly": _env_flag("WHISPER_LOCAL_FILES_ONLY", False),
        "loadTimeoutSeconds": _positive_seconds(
            os.getenv("WHISPER_LOAD_TIMEOUT_SECONDS"), DEFAULT_LOAD_TIMEOUT
        ),
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
