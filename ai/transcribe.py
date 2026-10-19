import math
import os
import subprocess
import threading
import time
from typing import Any

import numpy as np

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

# Whisper consumes mono 16 kHz float32 samples.
WHISPER_SAMPLE_RATE = 16000


def decode_audio(path: str, sample_rate: int = WHISPER_SAMPLE_RATE) -> np.ndarray:
    """Decode any media file to mono float32 PCM at ``sample_rate`` using ffmpeg.

    faster-whisper would decode this itself through PyAV, but its decoder calls
    ``av.open(input_file, mode="r", metadata_errors="ignore")`` and the installed
    PyAV no longer accepts that keyword, so transcription failed with
    ``TypeError: open() got an unexpected keyword argument 'metadata_errors'``
    before reading a single sample. ffmpeg is already a hard dependency of this
    service, so decode here and hand Whisper an array; faster-whisper skips its
    PyAV path entirely when the input is already a numpy array.

    Keeping this as a module-level function also makes the decode step
    replaceable in tests and keeps transcription independent of a decoder whose
    version skew can silently break it.
    """
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", path,
        "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-f", "f32le", "-acodec", "pcm_f32le", "-",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"ffmpeg could not be run while decoding {path}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(
            f"Audio decoding failed for {path}: "
            f"{detail[:400] or 'ffmpeg exited with a non-zero status'}"
        )
    # np.frombuffer returns a read-only view; copy so downstream code may write.
    return np.frombuffer(completed.stdout, dtype=np.float32).copy()


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


def _looks_like_cuda_failure(error: BaseException) -> bool:
    """Recognize GPU library failures that a CPU fallback can actually fix."""
    text = f"{type(error).__name__}: {error}".lower()
    return any(marker in text for marker in ("cublas", "cudnn", "cuda", "nvidia", "gpu"))


def _model_device_hint() -> str:
    """Device the active model was constructed on (best effort; "auto" if unknown)."""
    return globals().get("_model_device", "") or "auto"


def _load_once(
    model_name: str,
    timeout: float,
    device: str,
    compute: str,
    local_only: bool,
) -> Any:
    _start_load(model_name, device, compute, local_only)
    try:
        result = _await_load(timeout, model_name)
    finally:
        # The attempt is finished whether it succeeded or failed; a later
        # call must not mistake the dead thread for a load still in flight.
        global _load_thread
        _load_thread = None
    global _model_device
    _model_device = device
    return result


def _reload_on_cpu(model_name: str | None = None) -> Any:
    """Rebuild the process model on CPU after a GPU-only library failure."""
    global _model
    name = model_name or os.getenv("WHISPER_MODEL", "small")
    timeout = _positive_seconds(
        os.getenv("WHISPER_LOAD_TIMEOUT_SECONDS"), DEFAULT_LOAD_TIMEOUT
    )
    _model = _load_once(
        name,
        timeout,
        "cpu",
        os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        _env_flag("WHISPER_LOCAL_FILES_ONLY", False),
    )
    return _model


def model():
    """Load the configured Whisper model once, even under concurrent requests.

    The load is bounded in time. It is also the only place a model download may
    happen, and it runs on a daemon thread so a stalled download cannot block the
    model lock (and therefore the whole transcription route) indefinitely.

    When the configured/auto device is a GPU stack whose CUDA libraries are
    missing, the load falls back once to CPU so machines with a partial CUDA
    install (torch bundles CUDA headers but not cublas/cudnn runtime DLLs) keep
    their transcription capability instead of failing every request.
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
                compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                local_only = _env_flag("WHISPER_LOCAL_FILES_ONLY", False)
                requested_device = os.getenv("WHISPER_DEVICE", "auto")
                try:
                    _model = _load_once(model_name, timeout, requested_device, compute, local_only)
                except RuntimeError as primary_error:
                    if requested_device.strip().lower() in {"auto", "gpu", "cuda"} and _looks_like_cuda_failure(primary_error):
                        _model = _load_once(model_name, timeout, "cpu", compute, local_only)
                    else:
                        raise
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


def _finite(value: Any) -> float | None:
    """Coerce a timestamp or score to a finite float without raising."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def transcribe(path: str, language: str | None = None, timeout: float | None = None) -> dict:
    effective_timeout = timeout if timeout is not None else DEFAULT_TRANSCRIBE_TIMEOUT
    # Whisper consumes mono 16 kHz float32 samples. Decode them here rather than
    # letting faster-whisper do it: its PyAV call passes `metadata_errors` to
    # `av.open`, which the installed PyAV no longer accepts, so every
    # transcription request failed with TypeError before any audio was read.
    audio = path if isinstance(path, np.ndarray) else decode_audio(path)
    try:
        segments, info = model().transcribe(
            audio,
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )
    except RuntimeError as inference_error:
        # ctranslate2 can construct the model on CUDA when CUDA is visible but
        # only part of the runtime (cublas/cudnn) is installed, and then fail on
        # the first inference. One bounded rebuild on CPU preserves the request.
        if _looks_like_cuda_failure(inference_error) and _model_device_hint() != "cpu":
            _reload_on_cpu()
            segments, info = model().transcribe(
                audio,
                language=language,
                word_timestamps=True,
                vad_filter=True,
            )
        else:
            raise
    duration = _finite(getattr(info, "duration", None))
    # Timestamps cannot describe moments outside the decoded media; clamping
    # keeps malformed Whisper output from creating out-of-range candidates.
    duration_limit = duration if duration is not None and duration > 0 else None
    output = []
    start_time = time.time()
    for segment in segments:
        if effective_timeout and (time.time() - start_time) > effective_timeout:
            raise RuntimeError(f"Whisper transcription timed out after {int(effective_timeout)}s")
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
        words.sort(key=lambda item: (item["start"], item["end"]))
        raw_text = getattr(segment, "text", "")
        segment_text = raw_text.strip() if isinstance(raw_text, str) else str(raw_text or "").strip()
        output.append({
            "start": start,
            "end": end,
            "text": segment_text,
            "confidence": None,
            "words": words,
        })

    # A provider can emit segments out of order; downstream candidate windows
    # assume chronological transcript rows.
    output.sort(key=lambda segment: (segment["start"], segment["end"]))
    text_parts = [segment["text"] for segment in output]
    return {
        "language": info.language,
        "text": " ".join(part for part in text_parts if part),
        "segments": output,
        "duration": duration_limit if duration_limit is not None else (duration or 0.0),
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
