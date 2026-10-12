import math
import os

_model = None


def model():
    global _model
    if _model is None:
        # Loading faster-whisper can initialize large native dependencies and
        # download model files. Keep that work out of API startup and tests
        # that only need to import the AI service.
        from faster_whisper import WhisperModel

        device = os.getenv("WHISPER_DEVICE", "auto")
        compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device=device, compute_type=compute)
    return _model


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def transcribe(path: str, language: str | None = None):
    segments, info = model().transcribe(
        path, language=language, word_timestamps=True, vad_filter=True
    )
    segments = list(segments)
    duration = _finite_number(getattr(info, "duration", None)) or 0.0

    # Some media backends do not report duration. Derive a safe upper bound
    # from valid segment ends rather than returning malformed timestamps.
    if duration <= 0:
        valid_ends = []
        for segment in segments:
            start = _finite_number(getattr(segment, "start", None))
            end = _finite_number(getattr(segment, "end", None))
            if start is not None and end is not None and end > start:
                valid_ends.append(max(0.0, end))
        duration = max(valid_ends, default=0.0)

    output = []
    for segment in segments:
        start = _finite_number(getattr(segment, "start", None))
        end = _finite_number(getattr(segment, "end", None))
        if start is None or end is None or end <= start:
            continue
        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))
        if end <= start:
            continue

        words = []
        for word in getattr(segment, "words", None) or []:
            word_start = _finite_number(getattr(word, "start", None))
            word_end = _finite_number(getattr(word, "end", None))
            if word_start is None or word_end is None or word_end <= word_start:
                continue
            word_start = max(start, min(word_start, end))
            word_end = max(start, min(word_end, end))
            if word_end <= word_start:
                continue
            confidence = _finite_number(getattr(word, "probability", None))
            words.append({
                "start": word_start,
                "end": word_end,
                "word": str(getattr(word, "word", "")),
                "confidence": confidence,
            })
        words.sort(key=lambda word: (word["start"], word["end"]))

        segment_text = str(getattr(segment, "text", "") or "").strip()
        output.append({
            "start": start,
            "end": end,
            "text": segment_text,
            "confidence": None,
            "words": words,
        })

    output.sort(key=lambda segment: (segment["start"], segment["end"]))

    return {
        "language": getattr(info, "language", None) or "und",
        "text": " ".join(segment["text"] for segment in output if segment["text"]),
        "segments": output,
        "duration": duration,
    }
