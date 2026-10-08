"""Optional true speaker diarization.

The pipeline remains fully usable without credentials. When pyannote.audio and
HF_TOKEN are available, this module assigns speaker labels to transcript
segments/words. Without them it returns an explicit unavailable state rather
than fabricating speaker identities.
"""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _pipeline():
    try:
        from pyannote.audio import Pipeline
    except Exception:
        return None
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        return None
    model = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
    try:
        return Pipeline.from_pretrained(model, token=token)
    except TypeError:
        try:
            return Pipeline.from_pretrained(model, use_auth_token=token)
        except Exception:
            return None
    except Exception:
        return None


def diarization_status() -> dict:
    pipe = _pipeline()
    return {
        "available": pipe is not None,
        "provider": "pyannote" if pipe is not None else None,
        "model": os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"),
    }


def _speaker_at(intervals: list[tuple[float, float, str]], start: float, end: float) -> str | None:
    best = (0.0, None)
    for a, b, speaker in intervals:
        overlap = max(0.0, min(end, b) - max(start, a))
        if overlap > best[0]:
            best = (overlap, speaker)
    return best[1]


def diarize(media_path: str, segments: list[dict]) -> dict:
    pipe = _pipeline()
    if pipe is None:
        return {"available": False, "segments": [], "speakers": [], "reason": "optional diarization model/token unavailable"}

    try:
        output = pipe(media_path)
        intervals: list[tuple[float, float, str]] = []
        for turn, _, speaker in output.itertracks(yield_label=True):
            intervals.append((float(turn.start), float(turn.end), str(speaker)))

        enriched = []
        speakers = sorted({x[2] for x in intervals})
        for segment in segments:
            item = dict(segment)
            start, end = float(item["start"]), float(item["end"])
            speaker = _speaker_at(intervals, start, end)
            item["speaker"] = speaker
            words = []
            for word in item.get("words", []) or []:
                w = dict(word)
                ws, we = float(w.get("start", start)), float(w.get("end", end))
                w["speaker"] = _speaker_at(intervals, ws, we) or speaker
                words.append(w)
            if words:
                item["words"] = words
            enriched.append(item)

        return {
            "available": True,
            "provider": "pyannote",
            "model": os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"),
            "segments": enriched,
            "speakers": speakers,
        }
    except Exception as exc:
        return {
            "available": False,
            "segments": [],
            "speakers": [],
            "reason": f"diarization failed: {type(exc).__name__}",
        }
