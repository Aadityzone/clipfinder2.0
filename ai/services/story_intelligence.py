import math
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

def _contains_phrase(text: str, phrase: str) -> bool:
    low = re.sub(r"\s+", " ", text.lower()).strip()
    cue = re.sub(r"\s+", " ", phrase.lower()).strip()
    return bool(
        cue
        and re.search(
            r"(?<![a-z0-9])" + re.escape(cue) + r"(?![a-z0-9])",
            low,
        )
    )


def _hit_score(text: str, phrases: tuple[str, ...]) -> float:
    return min(1.0, sum(1 for phrase in phrases if _contains_phrase(text, phrase)) / 3.0)

def analyze_story(text: str, duration: float, before_text: str = "", after_text: str = "") -> StorySignals:
    tokens = _tokens(text)
    if not tokens:
        return StorySignals(0, 0, 0, 0, 0)
    hook = min(1, _hit_score(text, HOOKS) * .65 + min(1, text.count("?") / 2) * .35)
    tension = _hit_score(text, TENSION)
    payoff = _hit_score(text, PAYOFF) * .75 + min(1, len(tokens) / 90) * .25
    conversational = min(1, (text.count("?") + text.count("!") + sum(1 for token in tokens if token in {"you", "your", "i", "we", "us", "our"})) / 8)
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
    """Snap boundaries to valid Whisper word timestamps near sentence punctuation."""
    words = []
    if not isinstance(segments, list):
        return start, end
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("words"), list):
            continue
        for word in segment["words"]:
            if not isinstance(word, dict):
                continue
            try:
                ws, we = float(word["start"]), float(word["end"])
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(ws) or not math.isfinite(we) or ws < 0 or we <= ws:
                continue
            if we > start - 3 and ws < end + 3:
                words.append((ws, we, str(word.get("word", ""))))
    if not words:
        return start, end
    words.sort(key=lambda item: item[0])
    left_candidates = [word for word in words if word[1] <= start + 1.5]
    right_candidates = [word for word in words if word[0] >= end - 1.5]
    if left_candidates and left_candidates[-1][2].strip().endswith((".", "!", "?")):
        start = left_candidates[-1][1]
    if right_candidates and right_candidates[0][2].strip().startswith((".", "!", "?")):
        end = right_candidates[0][0]
    for index, word in enumerate(words[:-1]):
        if word[1] > end or not word[2].strip().endswith((".", "!", "?")):
            continue
        next_word = words[index + 1]
        if word[1] <= next_word[0] < end and end - next_word[0] <= 1.5:
            end = next_word[0]
            break
    return start, end


def _valid_segments(segments):
    valid = []
    if not isinstance(segments, list):
        return valid
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            start, end = float(segment["start"]), float(segment["end"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(start) and math.isfinite(end) and start >= 0 and end > start:
            valid.append({**segment, "start": start, "end": end})
    return valid


def find_boundaries(segments: list[dict], anchor_index: int, min_duration=12.0, max_duration=75.0) -> tuple[float, float]:
    segments = _valid_segments(segments)
    if not segments:
        return 0.0, 0.0
    try:
        minimum = float(min_duration)
        maximum = float(max_duration)
        anchor_position = int(anchor_index)
    except (TypeError, ValueError, OverflowError):
        minimum, maximum, anchor_position = 12.0, 75.0, 0
    if not math.isfinite(minimum) or minimum <= 0:
        minimum = 12.0
    if not math.isfinite(maximum) or maximum < minimum:
        maximum = max(75.0, minimum)
    anchor_position = max(0, min(anchor_position, len(segments) - 1))
    anchor = segments[anchor_position]
    start = float(anchor["start"])
    end = float(anchor["end"])
    left, right = anchor_position - 1, anchor_position + 1
    while left >= 0 and start - float(segments[left]["start"]) < 16:
        start = float(segments[left]["start"])
        left -= 1
    while right < len(segments):
        candidate_end = float(segments[right]["end"])
        if candidate_end - start > maximum:
            break
        end = candidate_end
        right += 1
    if end - start < minimum:
        end = min(start + minimum, float(segments[-1]["end"]))
    if end - start > maximum:
        end = start + maximum
    start, end = _punctuated_word_bounds(segments, start, end)
    if end - start < minimum:
        end = min(float(segments[-1]["end"]), start + minimum)
    return max(0.0, start), max(start, end)


def optimize_candidates(segments: list[dict], candidates: list[dict]) -> list[dict]:
    segments = _valid_segments(segments)
    if not segments or not isinstance(candidates, list):
        return []
    enriched = []
    for raw_candidate in candidates:
        if not isinstance(raw_candidate, dict):
            continue
        try:
            candidate_start = float(raw_candidate["start"])
            candidate_end = float(raw_candidate["end"])
            original_score = float(raw_candidate.get("score", 0))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(value) for value in (candidate_start, candidate_end, original_score)):
            continue
        if candidate_end <= candidate_start:
            continue
        anchor = min(
            range(len(segments)),
            key=lambda index: abs(float(segments[index]["start"]) - candidate_start),
        )
        start, end = find_boundaries(segments, anchor)
        if end <= start:
            continue
        text = " ".join(
            str(segment.get("text", "")).strip() for segment in segments
            if float(segment["end"]) > start and float(segment["start"]) < end
        ).strip()
        signals = analyze_story(text, end - start)
        score = story_score(signals)
        candidate = dict(raw_candidate)
        candidate["start"] = start
        candidate["end"] = end
        candidate["text"] = text
        features = candidate.get("features")
        if not isinstance(features, dict):
            features = {}
        else:
            features = dict(features)
        features["story"] = {
            "hook": round(signals.hook, 3),
            "tension": round(signals.tension, 3),
            "payoff": round(signals.payoff, 3),
            "completeness": round(signals.completeness, 3),
            "conversational": round(signals.conversational, 3),
        }
        features["storyScore"] = score
        candidate["features"] = features
        candidate["score"] = round(max(0.0, min(100.0, original_score * .58 + score * .42)), 2)
        candidate["rationale"] = (
            "Optimized for standalone storytelling: hook, tension, payoff, "
            "context completeness and conversational engagement."
        )
        enriched.append(candidate)
    return enriched
