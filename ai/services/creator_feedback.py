from __future__ import annotations

import math
from typing import Any


def _number(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _feature_vector(features: dict[str, Any]) -> dict[str, float]:
    hooks = features.get("hookSignals") if isinstance(features.get("hookSignals"), dict) else {}
    conversation = features.get("conversation") if isinstance(features.get("conversation"), dict) else {}
    labels = features.get("onScreenActionLabels")
    labels = labels if isinstance(labels, list) else []
    semantic = features.get("visualSemanticScore")
    return {
        "face_presence": _clamp(_number(features.get("faceHits")) / 6),
        "scene_changes": _clamp(_number(features.get("sceneHits")) / 5),
        "audio_energy": _clamp(_number(features.get("audioEnergy"))),
        "visual_change": _clamp(_number(features.get("visualChange"))),
        "motion": _clamp(_number(features.get("motion"))),
        "gameplay": _clamp(_number(features.get("gameplayLikeRatio"))),
        "action_cues": _clamp(len(labels) / 3),
        "semantic_score": _clamp((_number(semantic) - 50) / 50) if semantic is not None else 0.0,
        "hook_density": _clamp((_number(hooks.get("questions")) + _number(hooks.get("exclamations"))) / 5),
        "conversation_turns": _clamp(_number(conversation.get("styleTransitions")) / 4),
    }


def apply_creator_preferences(
    candidates: list[dict[str, Any]], preferences: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Apply a small, bounded creator-specific score adjustment to ranked candidates."""
    if not isinstance(preferences, dict):
        return candidates
    allowed = {
        "face_presence", "scene_changes", "audio_energy", "visual_change", "motion",
        "gameplay", "action_cues", "semantic_score", "hook_density", "conversation_turns",
    }
    weights = {
        key: max(-1.0, min(1.0, _number(value)))
        for key, value in preferences.items()
        if key in allowed and abs(_number(value)) >= 0.08
    }
    if not weights:
        return candidates

    divisor = math.sqrt(len(weights))
    for candidate in candidates:
        features = candidate.get("features")
        if not isinstance(features, dict):
            features = {}
            candidate["features"] = features
        vector = _feature_vector(features)
        raw_adjustment = sum(weight * (vector[key] - 0.5) for key, weight in weights.items())
        adjustment = round(max(-5.0, min(5.0, 3.0 * raw_adjustment / divisor)), 2)
        candidate["score"] = round(max(0.0, min(100.0, _number(candidate.get("score")) + adjustment)), 2)
        features["creatorFeedback"] = {
            "applied": True,
            "scoreAdjustment": adjustment,
            "signalsUsed": len(weights),
        }
    return candidates
