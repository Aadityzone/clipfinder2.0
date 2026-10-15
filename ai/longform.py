import re
from typing import Any

from .services.story_intelligence import analyze_story, story_score


def _story_candidate(window: list[dict[str, Any]], start: float, rationale: str) -> dict:
    end = float(window[-1]["end"])
    joined = " ".join(str(segment.get("text", "")).strip() for segment in window).strip()
    tokens = re.findall(r"[a-z0-9']+", joined.lower())
    diversity = len(set(tokens)) / max(1, len(tokens))
    signals = analyze_story(joined, max(0.0, end - start))
    # Blend story structure with lexical variety. Optional model ranking is a
    # later stage, so this deterministic score remains available offline.
    score = round(min(100.0, story_score(signals) * 0.85 + diversity * 15.0), 2)
    words = joined.split()
    title = " ".join(words[:10]).strip(" .,!?:;")
    if len(words) > 10:
        title += "…"
    return {
        "start": start,
        "end": end,
        "score": score,
        "title": title or "Untitled story",
        "text": joined,
        "category": "long_form_story",
        "rationale": rationale,
        "features": {
            "wordCount": len(tokens),
            "lexicalDiversity": round(diversity, 4),
            "story": {
                "hook": round(signals.hook, 3),
                "tension": round(signals.tension, 3),
                "payoff": round(signals.payoff, 3),
                "completeness": round(signals.completeness, 3),
                "conversational": round(signals.conversational, 3),
            },
        },
    }


def stories(segments: list[dict], limit: int = 6) -> list[dict]:
    """Create transcript-grounded story windows with inspectable ranking evidence."""
    if not segments:
        return []
    out: list[dict] = []
    window: list[dict] = []
    start = 0.0
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        if not window:
            start = float(segment["start"])
        window.append(segment)
        if len(window) >= 10 or float(segment["end"]) - start >= 300:
            out.append(_story_candidate(
                window, start,
                "Long-form story candidate ranked by hook, tension, payoff, completeness, and lexical variety.",
            ))
            window = []
    if window:
        out.append(_story_candidate(
            window, start,
            "Final long-form story candidate ranked from the remaining transcript context.",
        ))
    return sorted(out, key=lambda item: float(item.get("score", 0)), reverse=True)[:max(1, int(limit))]


def package(segments: list[dict], stories_out: list[dict]) -> dict:
    texts = [
        str(segment.get("text", "")).strip()
        for segment in segments
        if str(segment.get("text", "")).strip()
    ]
    joined = " ".join(texts)
    words = joined.split()
    title = " ".join(words[:12]).strip(" .,!?:;") or "Untitled long-form video"
    if len(title) > 90:
        title = title[:87].rsplit(" ", 1)[0] + "…"
    description = (joined[:500].strip() + "…") if len(joined) > 500 else joined
    # Chapters must be chronological even though story candidates are score-ranked.
    chapters = [
        {"start": float(item["start"]), "title": str(item.get("title") or "Highlight")}
        for item in sorted(stories_out, key=lambda item: float(item.get("start", 0)))
    ]
    return {"title": title, "description": description, "chapters": chapters}
