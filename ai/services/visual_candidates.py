"""Propose evidence-backed candidates from multimodal events, including sparse-speech moments.

These are event-window proposals, not semantic claims that a fight, joke, or win
occurred. Genre-specific models can later classify the event using the attached
evidence and sampled frames.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if number == number and abs(number) != float("inf") else default


def _window_text(segments: list[dict], start: float, end: float) -> str:
    if not isinstance(segments, list):
        return ""
    pieces = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        seg_start = _number(segment.get("start"), -1)
        seg_end = _number(segment.get("end"), -1)
        if seg_start >= 0 and seg_end > seg_start and seg_end > start and seg_start < end:
            text = str(segment.get("text", "")).strip()
            if text:
                pieces.append(text)
    return " ".join(pieces).strip()


def multimodal_event_candidates(
    segments: list[dict],
    media: dict[str, Any],
    duration: float | None = None,
    min_event_strength: float = 0.58,
    max_candidates: int = 40,
) -> list[dict]:
    """Build bounded candidate windows from timestamped audio/visual event evidence."""
    duration_value = max(0.0, _number(duration, 0.0))
    try:
        threshold = float(min_event_strength)
    except (TypeError, ValueError, OverflowError):
        threshold = 0.58
    if threshold != threshold or abs(threshold) == float("inf"):
        threshold = 0.58
    threshold = max(0.0, min(1.0, threshold))
    try:
        candidate_limit = int(max_candidates)
    except (TypeError, ValueError, OverflowError):
        candidate_limit = 40
    candidate_limit = max(0, min(100, candidate_limit))
    if candidate_limit == 0 or not isinstance(media, dict):
        return []
    visual_block = media.get("visual")
    scenes_block = media.get("scenes")
    on_screen_block = media.get("onScreen")
    visual_samples = visual_block.get("samples", []) if isinstance(visual_block, dict) else []
    audio_windows = media.get("audioWindows", [])
    scenes = scenes_block.get("sceneChanges", []) if isinstance(scenes_block, dict) else []
    screen_samples = on_screen_block.get("samples", []) if isinstance(on_screen_block, dict) else []
    visual_samples = [row for row in (visual_samples or []) if isinstance(row, dict)]
    audio_windows = [row for row in (audio_windows or []) if isinstance(row, dict)]
    screen_samples = [row for row in (screen_samples or []) if isinstance(row, dict)]
    scenes = scenes if isinstance(scenes, list) else []
    if not any((visual_samples, audio_windows, scenes, screen_samples)):
        return []

    events: list[dict] = []
    for row in visual_samples:
        time = _number(row.get("time"), -1)
        if time < 0 or (duration_value > 0 and time > duration_value):
            continue
        change = max(0.0, min(1.0, _number(row.get("visualChange"))))
        motion = max(0.0, min(1.0, _number(row.get("motion"))))
        strength = max(change, motion)
        if strength >= threshold:
            events.append({"time": time, "strength": strength, "kind": "visual_change",
                           "evidence": {"visualChange": change, "motion": motion}})

    for row in audio_windows:
        time = _number(row.get("start"), -1)
        if time < 0 or (duration_value > 0 and time > duration_value):
            continue
        energy = max(0.0, min(1.0, _number(row.get("energy"))))
        peak_db = _number(row.get("peakDb"), -120.0)
        # Energy is normalized by the audio analyzer; a peak adds confidence.
        peak_strength = max(0.0, min(1.0, (peak_db + 24.0) / 24.0))
        strength = max(energy, peak_strength)
        if strength >= threshold:
            events.append({"time": time, "strength": strength, "kind": "audio_peak",
                           "evidence": {"audioEnergy": energy, "audioPeakDb": peak_db}})

    for time_value in scenes:
        time = _number(time_value, -1)
        if time >= 0 and (duration_value <= 0 or time <= duration_value):
            events.append({"time": time, "strength": 0.62, "kind": "scene_change",
                           "evidence": {"sceneChange": True}})

    for row in screen_samples:
        time = _number(row.get("time"), -1)
        raw_labels = row.get("actionLabels")
        labels = raw_labels if isinstance(raw_labels, list) else []
        if time >= 0 and labels and (duration_value <= 0 or time <= duration_value):
            events.append({"time": time, "strength": 0.72, "kind": "on_screen_action",
                           "evidence": {"onScreenActionLabels": sorted(set(map(str, labels))),
                                        "onScreenText": str(row.get("ocrText") or "")[:500]}})

    events.sort(key=lambda event: (-event["strength"], event["time"]))
    selected: list[dict] = []
    for event in events:
        if any(abs(event["time"] - kept["time"]) < 8.0 for kept in selected):
            continue
        selected.append(event)
        if len(selected) >= candidate_limit:
            break

    proposals = []
    for event in selected:
        center = event["time"]
        if duration_value > 0 and center > duration_value:
            continue
        start = max(0.0, center - 12.0)
        end = center + 18.0
        if duration_value > 0:
            end = min(duration_value, end)
        if end <= start:
            continue
        text = _window_text(segments, start, end)
        evidence = dict(event["evidence"])
        evidence["eventKind"] = event["kind"]
        evidence["eventStrength"] = round(event["strength"], 3)
        window_visual = [
            row for row in visual_samples
            if start <= _number(row.get("time"), -1) <= end
        ]
        window_audio = [
            row for row in audio_windows
            if _number(row.get("end")) > start and _number(row.get("start")) < end
        ]
        window_screen = [
            row for row in screen_samples
            if start <= _number(row.get("time"), -1) <= end
        ]
        vision_block = media.get("vision")
        face_rows = vision_block.get("faces", []) if isinstance(vision_block, dict) else []
        window_faces = [
            row for row in (face_rows or [])
            if isinstance(row, dict) and start <= _number(row.get("time"), -1) <= end
        ]
        evidence["visualChange"] = round(
            sum(_number(row.get("visualChange")) for row in window_visual) / len(window_visual), 4
        ) if window_visual else 0.0
        evidence["motion"] = round(
            sum(_number(row.get("motion")) for row in window_visual) / len(window_visual), 4
        ) if window_visual else 0.0
        evidence["faceHits"] = len(window_faces)
        evidence["sceneHits"] = sum(1 for value in scenes if start <= _number(value, -1) <= end)
        evidence["audioEnergy"] = round(
            sum(_number(row.get("energy")) for row in window_audio) / len(window_audio), 4
        ) if window_audio else 0.0
        evidence["gameplayLikeRatio"] = round(
            sum(1 for row in window_screen if row.get("gameplayLike")) / len(window_screen), 4
        ) if window_screen else 0.0
        evidence["onScreenActionLabels"] = sorted({
            str(label) for row in window_screen for label in (row.get("actionLabels") or [])
        })
        evidence["onScreenText"] = " ".join(
            str(row.get("ocrText") or "") for row in window_screen
        )[:1200]
        proposals.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
            "score": round(35.0 + event["strength"] * 30.0, 2),
            "category": "ai_detect",
            "rationale": "Candidate proposed from timestamped multimodal event evidence; semantic event identity is not yet verified.",
            "features": {"multimodalProposal": True, **evidence},
        })
    return proposals
