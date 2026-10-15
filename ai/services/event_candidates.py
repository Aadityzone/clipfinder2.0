"""Generate candidate moments from media events, including clips with little speech.

This proposal stage is deliberately explainable and does not call an external model.
It fuses event evidence while retaining modality-specific features for downstream
ranking and creator preferences. These signals suggest activity, not semantic quality.
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
    start = max(0.0, min(center - length * 0.5, duration - length))
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


def _candidate_features(cluster: list[tuple[float, float, str, dict]]) -> dict:
    """Aggregate a cluster instead of letting the last modality overwrite others."""
    types = sorted({event[2] for event in cluster})
    payloads = [event[3] for event in cluster]
    features = {
        "candidateSource": "media_events",
        "eventTypes": types,
        "eventCount": len(cluster),
        "eventEvidenceScore": 0.0,
        "sceneHits": sum(1 for _, _, kind, _ in cluster if kind == "scene_change"),
    }

    for key in ("audioEnergy", "visualChange", "motion", "centerDetail", "visualSemanticScore"):
        values = [_number(payload[key]) for payload in payloads if key in payload]
        if values:
            # Preserve both peak and mean: a single spike and a sustained event
            # should remain distinguishable to the next ranking stage.
            features[key] = round(sum(values) / len(values), 4)
            features[f"{key}Peak"] = round(max(values), 4)

    peaks = [_number(payload["audioPeakDb"]) for payload in payloads
             if payload.get("audioPeakDb") is not None]
    if peaks:
        features["audioPeakDb"] = round(max(peaks), 2)

    labels = sorted({str(label) for payload in payloads
                     for label in (payload.get("onScreenActionLabels") or [])})
    if labels:
        features["onScreenActionLabels"] = labels[:12]
    texts = [str(payload.get("onScreenText", "")).strip() for payload in payloads
             if str(payload.get("onScreenText", "")).strip()]
    if texts:
        features["onScreenText"] = " | ".join(dict.fromkeys(texts))[:1200]

    gameplay_events = sum(1 for payload in payloads if payload.get("gameplayLike"))
    screen_events = sum(1 for payload in payloads
                        if "gameplayLike" in payload or "onScreenActionLabels" in payload
                        or "onScreenText" in payload)
    if screen_events:
        features["gameplayLikeRatio"] = round(gameplay_events / screen_events, 4)
        features["gameplayLike"] = gameplay_events > 0

    return features


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
    if requested and not requested.intersection({"ai_detect", "ai_detected", "all"}):
        return []

    audio_rows = media.get("audioWindows", []) or []
    visual_rows = (media.get("visual") or {}).get("samples", []) or []
    screen_rows = (media.get("onScreen") or {}).get("samples", []) or []
    scene_times = (media.get("scenes") or {}).get("sceneChanges", []) or []
    semantic_rows = media.get("visualSemantic", []) or []

    events: list[tuple[float, float, str, dict]] = []
    audio_peaks = []
    for row in audio_rows:
        if not isinstance(row, dict):
            continue
        row_start = _number(row.get("start"), -1)
        row_end = _number(row.get("end"), -1)
        energy = _number(row.get("energy"))
        if row_start < 0 or row_end <= row_start or energy <= 0:
            continue
        # Center events inside their measured energy window rather than anchoring
        # every proposed clip to the window's leading edge.
        audio_peaks.append(((row_start + row_end) / 2, energy, row))
    if audio_peaks:
        values = sorted(value for _, value, _ in audio_peaks)
        threshold = values[max(0, int((len(values) - 1) * 0.70))]
        for time, value, row in audio_peaks:
            if value >= max(0.45, threshold):
                events.append((time, min(1.0, value), "audio_energy", {
                    "audioEnergy": value,
                    "audioPeakDb": row.get("peakDb"),
                }))

    visual_events = []
    for row in visual_rows:
        if not isinstance(row, dict):
            continue
        time = _number(row.get("time"), -1)
        if time < 0 or time >= duration:
            continue
        change = _number(row.get("visualChange"))
        motion = _number(row.get("motion"))
        detail = _number(row.get("centerDetail"))
        signal = min(1.0, max(0.0, change) * 0.55 + max(0.0, motion) * 0.35 + max(0.0, detail) * 0.10)
        if signal >= 0.18:
            visual_events.append((time, signal, "visual_change", {
                "visualChange": change, "motion": motion, "centerDetail": detail,
            }))
    events.extend(sorted(visual_events, key=lambda event: event[1], reverse=True)[:20])

    for raw_time in scene_times[:500]:
        time = _number(raw_time, -1)
        if 0 <= time < duration:
            events.append((time, 0.35, "scene_change", {"sceneChange": True}))

    for row in screen_rows:
        if not isinstance(row, dict):
            continue
        time = _number(row.get("time"), -1)
        labels = row.get("actionLabels", [])
        labels = labels if isinstance(labels, list) else []
        gameplay = bool(row.get("gameplayLike"))
        ocr = str(row.get("ocrText", "")).strip()
        if time < 0 or time >= duration:
            continue
        if labels or gameplay or ocr:
            events.append((time, 0.5 + min(0.3, len(labels) * 0.05),
                           "on_screen_event", {
                               "onScreenActionLabels": sorted({str(label) for label in labels})[:12],
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
                "visualSemanticScore": score,
            }))

    # Cluster nearby signals; a single loud/fast sequence should not create
    # dozens of nearly identical windows.
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
        evidence_score = min(100.0, round(
            28 + min(22, len(cluster) * 5) +
            min(20, sum(event[1] for event in cluster) * 8) +
            min(15, max(0, len(types) - 1) * 7), 2
        ))
        features = _candidate_features(cluster)
        features["eventEvidenceScore"] = evidence_score
        rationale = (
            "Media-event candidate based on " + ", ".join(types) +
            "; activity signals alone do not establish semantic quality."
        )
        candidates.append({
            "start": start, "end": end, "text": "", "score": evidence_score,
            "category": "ai_detect", "rationale": rationale, "features": features,
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:max(0, min(int(limit), 100))]
