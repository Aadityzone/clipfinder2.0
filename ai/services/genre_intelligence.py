"""Lightweight genre-aware candidate reranking.

These profiles are transparent heuristics over transcript words and already-computed
media signals. They are not trained genre classifiers; quality must be measured on
real examples before making genre-specific accuracy claims.
"""
from __future__ import annotations

import re

GENRE_CUES: dict[str, tuple[str, ...]] = {
    "gaming": (
        "clutch", "headshot", "eliminated", "respawn", "boss fight", "victory",
        "game over", "ranked", "kill", "damage", "squad", "gg", "level up",
        "final round", "last player",
    ),
    "irl_stream": (
        "chat", "donation", "subscriber", "stream", "prank", "meet this",
        "no way", "let's go", "what happened", "bro", "reaction", "in real life",
    ),
    "movies_tv": (
        "plot twist", "the ending", "this character", "the villain", "episode",
        "the scene", "spoiler", "revealed", "story arc", "final scene", "foreshadow",
    ),
    "anime": (
        "anime", "manga", "sensei", "jutsu", "domain expansion", "transformation",
        "power level", "final form", "episode", "arc", "fight scene", "voice actor",
    ),
    "tech": (
        "benchmark", "graphics card", "gpu", "cpu", "processor", "software",
        "open source", "code", "developer", "update", "review", "performance",
        "latency", "memory", "model", "ai tool", "laptop",
    ),
    "knowledge": (
        "explained", "the reason", "because", "for example", "principle",
        "research", "evidence", "the key is", "here is how", "lesson", "learn",
        "in other words", "the process",
    ),
    "facts": (
        "did you know", "scientists discovered", "study found", "fun fact",
        "surprisingly", "the record", "percent of", "million years", "rarely",
        "one fact", "researchers found",
    ),
    "podcast": (
        "i think", "i believe", "i disagree", "exactly", "in my experience",
        "let me explain", "what do you think", "my point is", "to be honest",
        "the question is", "interview", "conversation",
    ),
}

ALIASES = {
    "irl": "irl_stream", "irl stream": "irl_stream", "in real life": "irl_stream",
    "movie": "movies_tv", "movies": "movies_tv", "tv": "movies_tv",
    "educational": "knowledge", "educational content": "knowledge",
    "knowledge content": "knowledge", "facts": "facts", "fact": "facts",
    "podcasts": "podcast", "tech videos": "tech", "games": "gaming",
    "anime/manga": "anime", "auto": "auto", "general": "general",
}
VALID_GENRES = ("auto", "general", *GENRE_CUES.keys())


def normalize_genre(genre: str | None) -> str:
    value = re.sub(r"[_-]+", " ", (genre or "auto").strip().lower())
    value = ALIASES.get(value, value.replace(" ", "_"))
    return value if value in VALID_GENRES else "auto"


def _contains_cue(text: str, cue: str) -> bool:
    """Match complete words/phrases instead of accidental substrings (e.g. kill/skill)."""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    phrase = re.sub(r"\s+", " ", cue.lower()).strip()
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", normalized))


def _count_cues(text: str, cues: tuple[str, ...]) -> int:
    return sum(1 for cue in cues if _contains_cue(text, cue))


def infer_genre(transcript: str) -> tuple[str, dict[str, int]]:
    """Infer genre only when evidence is strong and the leading profile is unambiguous."""
    scores = {genre: _count_cues(transcript, cues) for genre, cues in GENRE_CUES.items()}
    if not scores:
        return "general", scores
    highest = max(scores.values())
    leaders = [genre for genre, score in scores.items() if score == highest]
    # Avoid silently choosing whichever profile happens to appear first in the map.
    if highest < 2 or len(leaders) != 1:
        return "general", scores
    return leaders[0], scores


def apply_genre_profile(
    candidates: list[dict], transcript: str, requested_genre: str | None = "auto"
) -> list[dict]:
    """Apply small, explainable boosts to candidates that fit the selected genre."""
    requested = normalize_genre(requested_genre)
    inferred, transcript_scores = infer_genre(transcript)
    active = inferred if requested == "auto" else requested
    if active == "general":
        for candidate in candidates:
            candidate.setdefault("features", {})["genreProfile"] = {
                "requested": requested, "detected": inferred, "active": "general",
                "cueMatches": 0,
            }
        return candidates

    cues = GENRE_CUES[active]
    for candidate in candidates:
        text = str(candidate.get("text", ""))
        matches = _count_cues(text, cues)
        features = candidate.setdefault("features", {})
        action_labels = features.get("onScreenActionLabels", [])
        gameplay_ratio = float(features.get("gameplayLikeRatio") or 0)
        visual_change = float(features.get("visualChange") or 0)
        motion = float(features.get("motion") or 0)

        # Only a small bonus: transcript/media heuristics must not dominate ranking.
        bonus = min(8.0, matches * 1.5)
        if active == "gaming":
            bonus += min(2.0, len(action_labels) * 0.5)
            bonus += min(1.0, gameplay_ratio)
            if any(label in {"combat", "victory", "failure"} for label in action_labels):
                bonus += 1.5
        elif active == "irl_stream":
            bonus += min(1.5, float(features.get("faceHits") or 0) * 0.25)
            bonus += min(1.0, float(features.get("audioEnergy") or 0))
        elif active == "podcast":
            bonus += min(1.5, float(features.get("faceHits") or 0) * 0.25)
            speakers = features.get("speakers") or {}
            bonus += min(2.0, float(speakers.get("turnCount") or 0) * 0.4)
        elif active in {"movies_tv", "anime"}:
            bonus += min(2.0, visual_change * 1.5 + motion)
            bonus += min(1.0, float(features.get("sceneHits") or 0) * 0.2)
        elif active == "tech":
            bonus += min(1.5, float(features.get("sceneHits") or 0) * 0.25)
            bonus += min(1.0, len(str(features.get("onScreenText") or "")) / 300)
        elif active in {"knowledge", "facts"}:
            story = features.get("story") or {}
            bonus += min(2.0, float(story.get("completeness") or 0) * 2)
            bonus += min(1.0, float(story.get("payoff") or 0))
        bonus = min(12.0, bonus)
        candidate["score"] = round(min(100.0, float(candidate.get("score", 0)) + bonus), 2)
        features["genreProfile"] = {
            "requested": requested,
            "detected": inferred,
            "active": active,
            "cueMatches": matches,
            "transcriptCueCounts": transcript_scores,
            "bonus": round(bonus, 2),
        }
        if matches:
            candidate["rationale"] = (
                str(candidate.get("rationale") or "").rstrip(".")
                + f"; genre fit: {active.replace('_', ' ')} ({matches} cue matches)."
            )
    return candidates
