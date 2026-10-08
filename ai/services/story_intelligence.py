import re
from dataclasses import dataclass

@dataclass
class StorySignals:
    hook: float
    tension: float
    payoff: float
    completeness: float
    conversational: float

HOOKS = ("wait", "what", "why", "how", "listen", "okay", "so", "here's", "the thing")
TENSION = ("but", "however", "except", "until", "problem", "wrong", "failed", "couldn't", "never", "worried")
PAYOFF = ("because", "therefore", "finally", "turns out", "realized", "won", "lost", "actually", "so that's", "that's why")

def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())

def _hit_score(text: str, phrases: tuple[str, ...]) -> float:
    low = text.lower()
    return min(1.0, sum(1 for p in phrases if p in low) / 3.0)

def analyze_story(text: str, duration: float, before_text: str = "", after_text: str = "") -> StorySignals:
    tokens = _tokens(text)
    if not tokens:
        return StorySignals(0, 0, 0, 0, 0)
    hook = min(1, _hit_score(text, HOOKS) * .65 + min(1, text.count("?") / 2) * .35)
    tension = _hit_score(text, TENSION)
    payoff = _hit_score(text, PAYOFF) * .75 + min(1, len(tokens) / 90) * .25
    conversational = min(1, (text.count("?") + text.count("!") + text.count("you ") + text.count("I ")) / 8)
    # Standalone completeness rewards enough context but penalizes excessively long clips.
    context = min(1, len(tokens) / 55)
    length_penalty = max(0, min(1, (duration - 75) / 120))
    completeness = min(1, context * .65 + payoff * .25 + (1 - length_penalty) * .10)
    return StorySignals(hook, tension, payoff, completeness, conversational)

def story_score(signals: StorySignals) -> float:
    return round(100 * (
        signals.hook * .18 +
        signals.tension * .17 +
        signals.payoff * .28 +
        signals.completeness * .25 +
        signals.conversational * .12
    ), 2)

def _punctuated_word_bounds(segments: list[dict], start: float, end: float) -> tuple[float, float]:
    """Snap boundaries to available Whisper word timestamps near sentence punctuation."""
    words = []
    for segment in segments:
        for word in segment.get("words", []) or []:
            try:
                ws, we = float(word["start"]), float(word["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if we > start - 3 and ws < end + 3:
                words.append((ws, we, str(word.get("word", ""))))
    if not words:
        return start, end

    words.sort(key=lambda x: x[0])
    left_candidates = [w for w in words if w[1] <= start + 1.5]
    right_candidates = [w for w in words if w[0] >= end - 1.5]
    if left_candidates:
        left = left_candidates[-1]
        if left[2].strip().endswith((".", "!", "?")):
            start = left[1]
    if right_candidates:
        right = right_candidates[0]
        if right[2].strip().startswith((".", "!", "?")):
            end = right[0]
    return start, end


def find_boundaries(segments: list[dict], anchor_index: int, min_duration=12.0, max_duration=75.0) -> tuple[float, float]:
    anchor = segments[anchor_index]
    center_start, center_end = float(anchor["start"]), float(anchor["end"])
    start = center_start
    end = center_end

    # Expand around the anchor until enough context exists, preferring sentence boundaries.
    left = anchor_index - 1
    right = anchor_index + 1
    while left >= 0 and start - float(segments[left]["start"]) < 16:
        start = float(segments[left]["start"])
        left -= 1
    while right < len(segments) and float(segments[right]["end"]) - start <= max_duration:
        candidate_end = float(segments[right]["end"])
        if candidate_end - start > max_duration:
            break
        end = candidate_end
        right += 1

    if end - start < min_duration:
        end = min(start + min_duration, float(segments[-1]["end"]))
    if end - start > max_duration:
        end = start + max_duration
    start, end = _punctuated_word_bounds(segments, start, end)
    if end - start < min_duration:
        end = min(float(segments[-1]["end"]), start + min_duration)
    return max(0, start), end

def optimize_candidates(segments: list[dict], candidates: list[dict]) -> list[dict]:
    enriched = []
    for candidate in candidates:
        anchor = min(
            range(len(segments)),
            key=lambda i: abs(float(segments[i]["start"]) - float(candidate["start"]))
        )
        start, end = find_boundaries(segments, anchor)
        text = " ".join(
            str(s.get("text", "")).strip() for s in segments
            if float(s["end"]) > start and float(s["start"]) < end
        ).strip()
        signals = analyze_story(text, end - start)
        score = story_score(signals)
        candidate["start"] = start
        candidate["end"] = end
        candidate["text"] = text
        candidate["features"] = candidate.get("features", {})
        candidate["features"]["story"] = {
            "hook": round(signals.hook, 3),
            "tension": round(signals.tension, 3),
            "payoff": round(signals.payoff, 3),
            "completeness": round(signals.completeness, 3),
            "conversational": round(signals.conversational, 3),
        }
        candidate["features"]["storyScore"] = score
        candidate["score"] = round(min(100, float(candidate.get("score", 0)) * .58 + score * .42), 2)
        candidate["rationale"] = (
            "Optimized for standalone storytelling: hook, tension, payoff, "
            "context completeness and conversational engagement."
        )
        enriched.append(candidate)
    return enriched
