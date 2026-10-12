"""Generate candidate moments from media events, including clips with little speech.

This stage deliberately does not call an external model. It uses bounded timestamps
and evidence already extracted by the media-analysis pipeline to surface moments
that transcript-only candidate generation can miss.
"""
from __future__ import annotations

import math


MIN_CLIP_SECONDS = 12.0
MAX_CLIP_SECONDS = 42.0


def _number(value, default=0.0):
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if math.isfinite(parsed) else default


def _duration(media: dict) -> float:
    direct = _number(media.get("durationS"))
    if direct > 0:
        return direct
    audio = media.get("audio")
    if isinstance(audio, dict):
        direct = _number(audio.get("durationS"))
        if direct > 0:
            return direct
    ends = []
    for row in media.get("audioWindows", []) or []:
        if isinstance(row, dict):
            ends.append(_number(row.get("end")))
    for row in (media.get("visual") or {}).get("samples", []) or []:
        if isinstance(row, dict):
            ends.append(_number(row.get("time")))
    for row in (media.get("onScreen") or {}).get("samples", []) or []:
        if isinstance(row, dict):
            ends.append(_number(row.get("time")))
    return max(ends, default=0.0)


def _window(center: float, duration: float) -> tuple[float, float]:
    length = min(MAX_CLIP_SECONDS, duration)
    length = min(duration, max(min(MIN_CLIP_SECONDS, duration), length))
    start = max(0.0, min(center - length * 0.38, duration - length))
    return round(start, 3), round(start + length, 3)


def _peak_rows(rows: list, value_key: str, time_key: str = "time") -> list[tuple[float, float, dict]]:
    peaks = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        time = _number(row.get(time_key), -1)
        if time < 0:
            continue
        value = _number(row.get(value_key))
        if value > 0:
            peaks.append((time, value, row))
    return peaks


def generate_event_candidates(media: dict | None, instruction: str | None = None,
                              categories: list[str] | None = None,
                              limit: int = 30) -> list[dict]:
    """Create bounded, explainable candidates from non-transcript media evidence.

    Inputs are optional and missing modalities degrade gracefully. Candidates are
    returned only when at least one measurable event signal is available.
    """
    if not isinstance(media, dict):
        return []
    duration = _duration(media)
    if duration <= 0:
        return []

    requested = {str(item).strip().lower().replace(" ", "_") for item in (categories or [])}
    # Event-only evidence cannot reliably infer semantic categories such as funny.
    # Do not fabricate category labels when the user requests a specific category.
    if requested and not requested.intersection({"ai_detect", "ai_detected", "all"}):
        return []

    audio_rows = media.get("audioWindows", []) or []
    visual_rows = (media.get("visual") or {}).get("samples", []) or []
    screen_rows = (media.get("onScreen") or {}).get("samples", []) or []
    scene_times = (media.get("scenes") or {}).get("sceneChanges", []) or []
    semantic_rows = media.get("visualSemantic", []) or []

    events: list[tuple[float, float, str, dict]] = []
    audio_peaks = _peak_rows(audio_rows, "energy", "start")
    if audio_peaks:
        values = sorted(value for _, value, _ in audio_peaks)
        threshold = values[max(0, int((len(values) - 1) * 0.70))]
        for time, value, row in audio_peaks:
            if value >= max(0.45, threshold):
                events.append((time, min(1.0, value), "audio_energy", {
                    "audioEnergy": round(value, 4),
                    "audioPeakDb": row.get("peakDb"),
                }))

    visual_events = []
    for row in visual_rows:
        if not isinstance(row, dict):
            continue
        time = _number(row.get("time"), -1)
        if time < 0:
            continue
        change = _number(row.get("visualChange"))
        motion = _number(row.get("motion"))
        detail = _number(row.get("centerDetail"))
        signal = min(1.0, max(0.0, change) * 0.55 + max(0.0, motion) * 0.35 + max(0.0, detail) * 0.10)
        if signal >= 0.18:
            visual_events.append((time, signal, "visual_change", {
                "visualChange": round(change, 4),
                "motion": round(motion, 4),
                "centerDetail": round(detail, 4),
            }))
    if visual_events:
        strongest = sorted(visual_events, key=lambda event: event[1], reverse=True)[:20]
        events.extend(strongest)

    for raw_time in scene_times[:500]:
        time = _number(raw_time, -1)
        if 0 <= time < duration:
            events.append((time, 0.35, "scene_change", {"sceneChange": True}))

    for row in screen_rows:
        if not isinstance(row, dict):
            continue
        time = _number(row.get("time"), -1)
        labels = row.get("actionLabels", [])
        gameplay = bool(row.get("gameplayLike"))
        ocr = str(row.get("ocrText", "")).strip()
        if time < 0 or time >= duration:
            continue
        if labels or gameplay or ocr:
            events.append((time, 0.5 + min(0.3, len(labels or []) * 0.05),
                           "on_screen_event", {
                               "onScreenActionLabels": sorted({str(label) for label in (labels or [])})[:12],
                               "gameplayLike": gameplay,
                               "onScreenText": ocr[:500],
                           }))

    for row in semantic_rows:
        if not isinstance(row, dict):
            continue
        time = _number(row.get("time"), -1)
        score = _number(row.get("score"))
        if 0 <= time < duration and score >= 55:
            events.append((time, min(1.0, score / 100), "visual_semantic", {
                "visualSemanticScore": round(score, 3),
            }))

    # Cluster nearby signals into one event so a single loud/fast sequence does not
    # create dozens of nearly identical windows.
    events.sort(key=lambda event: event[0])
    clusters: list[list[tuple[float, float, str, dict]]] = []
    for event in events:
        if clusters and event[0] - clusters[-1][-1][0] <= 8.0:
            clusters[-1].append(event)
        else:
            clusters.append([event])

    candidates = []
    for cluster in clusters:
        center = sum(event[0] * max(event[1], 0.05) for event in cluster) / sum(
            max(event[1], 0.05) for event in cluster
        )
        start, end = _window(center, duration)
        if end <= start:
            continue
        types = sorted({event[2] for event in cluster})
        features = {}
        for event in cluster:
            features.update(event[3])
        evidence_score = min(100.0, round(
            28 + min(22, len(cluster) * 5) +
            min(20, sum(event[1] for event in cluster) * 8) +
            min(15, max(0, len(types) - 1) * 7), 2
        ))
        rationale = "Media-event candidate based on " + ", ".join(types) +             "; semantic quality is not inferred from these signals alone."
        candidates.append({
            "start": start,
            "end": end,
            "text": "",
            "score": evidence_score,
            "category": "ai_detect",
            "rationale": rationale,
            "features": {
                "candidateSource": "media_events",
                "eventTypes": types,
                "eventCount": len(cluster),
                "eventEvidenceScore": evidence_score,
                **features,
            },
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:max(0, min(int(limit), 100))]
