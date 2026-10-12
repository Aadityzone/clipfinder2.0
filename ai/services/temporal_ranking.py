"""Deterministic temporal/multimodal reranking for proposed clip moments.

This layer does not pretend that motion or loudness equals semantic quality. It
normalizes available evidence, rewards agreement between independent modalities,
and retains the upstream score as the majority of the final score. It is intended
as a transparent baseline until labelled benchmark data supports learned weights.
"""
from __future__ import annotations

import math
import re
from typing import Any


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _features(candidate: dict) -> dict:
    features = candidate.get("features")
    if not isinstance(features, dict):
        features = {}
        candidate["features"] = features
    return features


def _story_signal(features: dict) -> float | None:
    story = features.get("story")
    if isinstance(story, dict):
        values = []
        for key in ("hook", "tension", "payoff", "completeness", "conversational"):
            value = _finite(story.get(key))
            if value is not None:
                values.append(_clamp(value))
        if values:
            return sum(values) / len(values)
    score = _finite(features.get("storyScore"))
    return _clamp(score / 100) if score is not None else None


def _transcript_signal(candidate: dict, features: dict) -> float | None:
    text = candidate.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    words = re.findall(r"[a-z0-9']+", text.lower())
    if not words:
        return None
    hook_count = text.count("?") + text.count("!")
    unique_ratio = len(set(words)) / max(1, len(words))
    # Lightweight linguistic signal, deliberately lower-weight than story model.
    return _clamp(0.55 * min(1.0, len(words) / 45) +
                  0.25 * min(1.0, hook_count / 4) +
                  0.20 * unique_ratio)


def _multimodal_signal(features: dict) -> tuple[float | None, int, list[str]]:
    values: list[float] = []
    modalities: set[str] = set()

    audio = _finite(features.get("audioEnergy"))
    audio_peak = _finite(features.get("audioEnergyPeak"))
    if audio is not None or audio_peak is not None:
        # A peak can indicate an event, but sustained energy gets slightly more weight.
        values.append(_clamp(0.65 * _clamp(audio or 0) + 0.35 * _clamp(audio_peak or audio or 0)))
        modalities.add("audio")

    visual_change = _finite(features.get("visualChange"))
    motion = _finite(features.get("motion"))
    if visual_change is not None or motion is not None:
        values.append(_clamp(0.60 * _clamp(visual_change or 0) + 0.40 * _clamp(motion or 0)))
        modalities.add("visual")

    labels = features.get("onScreenActionLabels")
    labels = labels if isinstance(labels, list) else []
    text = features.get("onScreenText")
    gameplay = _finite(features.get("gameplayLikeRatio"))
    semantic = _finite(features.get("visualSemanticScore"))
    if labels or (isinstance(text, str) and text.strip()) or gameplay is not None:
        cue_strength = min(1.0, len(labels) / 3)
        if isinstance(text, str) and text.strip():
            cue_strength = max(cue_strength, 0.35)
        if gameplay is not None:
            cue_strength = max(cue_strength, _clamp(gameplay))
        values.append(cue_strength)
        modalities.add("on_screen")
    if semantic is not None:
        values.append(_clamp((semantic - 35.0) / 65.0))
        modalities.add("semantic")

    if not values:
        return None, 0, []
    return sum(values) / len(values), len(modalities), sorted(modalities)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Add ranking diagnostics and update score using available evidence only."""
    ranked = []
    for order, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        start, end = _finite(candidate.get("start")), _finite(candidate.get("end"))
        if start is None or end is None or start < 0 or end <= start:
            continue
        features = _features(candidate)
        original = _finite(candidate.get("score"))
        original = _clamp(original if original is not None else 0.0, 0.0, 100.0)

        signals: dict[str, float] = {}
        story = _story_signal(features)
        if story is not None:
            signals["story"] = story
        transcript = _transcript_signal(candidate, features)
        if transcript is not None:
            signals["transcript"] = transcript
        multimodal, modality_count, modalities = _multimodal_signal(features)
        if multimodal is not None:
            signals["multimodal"] = multimodal

        # Average only signals that are actually available; absence is not treated
        # as negative evidence, which protects silent gameplay and visual formats.
        quality = sum(signals.values()) / len(signals) if signals else original / 100
        agreement_bonus = min(0.08, max(0, modality_count - 1) * 0.025)
        quality = _clamp(quality + agreement_bonus)
        final_score = round(_clamp((original / 100) * 0.68 + quality * 0.32) * 100, 2)

        features["temporalRanking"] = {
            "version": 1,
            "inputScore": round(original, 2),
            "qualitySignal": round(quality, 4),
            "signals": {key: round(value, 4) for key, value in signals.items()},
            "modalities": modalities,
            "modalityCount": modality_count,
            "agreementBonus": round(agreement_bonus, 4),
            "finalScore": final_score,
        }
        candidate["score"] = final_score
        ranked.append((final_score, order, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked]
