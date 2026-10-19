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

HOOKS = ("wait", "what", "why", "how", "listen", "okay", "so", "here's", "the thing", "guess what", "watch this", "look at", "check this out", "did you see")
TENSION = ("but", "however", "except", "until", "problem", "wrong", "failed", "couldn't", "never", "worried", "suddenly", "all of a sudden", "close call", "scary", "intense")
PAYOFF = ("because", "therefore", "finally", "turns out", "realized", "won", "lost", "actually", "so that's", "that's why", "insane", "crazy", "unreal", "let's go", "clutch", "omg")

def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower()) if isinstance(text, str) else []

def _contains_phrase(text: str, phrase: str) -> bool:
    if not isinstance(text, str) or not isinstance(phrase, str):
        return False
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
    if not isinstance(text, str):
        return StorySignals(0, 0, 0, 0, 0)
    tokens = _tokens(text)
    if not tokens:
        return StorySignals(0, 0, 0, 0, 0)
    try:
        duration_value = float(duration)
    except (TypeError, ValueError, OverflowError):
        duration_value = 0.0
    if not math.isfinite(duration_value) or duration_value < 0:
        duration_value = 0.0
    hook = min(1.0, _hit_score(text, HOOKS) * .65 + min(1.0, text.count("?") / 2) * .35)
    tension = _hit_score(text, TENSION)
    setup_in_before = (
        ("?" in before_text or _hit_score(before_text, HOOKS) > 0.3)
        if isinstance(before_text, str) and before_text
        else False
    )
    payoff_bonus = 0.1 if (setup_in_before and _hit_score(text, PAYOFF) > 0.3) else 0.0
    self_contained_bonus = 0.1 if (hook > 0.4 and (tension > 0.3 or _hit_score(text, PAYOFF) > 0.3)) else 0.0

    payoff = min(1.0, _hit_score(text, PAYOFF) * .75 + min(1.0, len(tokens) / 90) * .25 + payoff_bonus)
    conversational = min(1.0, (text.count("?") + text.count("!") + sum(1 for token in tokens if token in {"you", "your", "i", "we", "us", "our"})) / 8)
    # Standalone completeness rewards enough context but penalizes excessively long clips.
    context = min(1.0, len(tokens) / 55)
    length_penalty = max(0.0, min(1.0, (duration_value - 75) / 120))
    completeness = min(1.0, context * .60 + payoff * .25 + (1.0 - length_penalty) * .10 + self_contained_bonus)
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


def _trim_dead_air(
    segments: list[dict],
    start: float,
    end: float,
    min_duration: float = 12.0,
    max_duration: float = 75.0,
) -> tuple[float, float]:
    """Trim excessive leading (>1.5s) or trailing (>2.0s) silence if word timestamps exist."""
    words: list[tuple[float, float]] = []
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
            if math.isfinite(ws) and math.isfinite(we) and ws >= 0 and we > ws:
                if we >= start and ws <= end:
                    words.append((ws, we))

    if not words:
        return start, end

    words.sort(key=lambda item: item[0])
    first_word_start = words[0][0]
    last_word_end = words[-1][1]

    new_start = start
    new_end = end

    # If silence before first word exceeds 1.5s, tighten start with a comfortable 0.35s lead-in
    lead_silence = first_word_start - start
    if lead_silence > 1.5:
        target_start = max(start, first_word_start - 0.35)
        if (new_end - target_start) >= min_duration:
            new_start = target_start

    # If silence after last word exceeds 2.0s, tighten end with a comfortable 0.5s pad
    trail_silence = end - last_word_end
    if trail_silence > 2.0:
        target_end = min(end, last_word_end + 0.5)
        if (target_end - new_start) >= min_duration:
            new_end = target_end

    return max(0.0, new_start), max(new_start, new_end)


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
    anchor_start = float(anchor["start"])
    start = anchor_start
    end = float(anchor["end"])
    left, right = anchor_position - 1, anchor_position + 1
    # Compare prior rows to the anchor, not to the moving start. Comparing to
    # the moving start walks through every contiguous transcript row and can
    # move a candidate all the way to the beginning of a long video.
    while left >= 0 and anchor_start - float(segments[left]["start"]) < 16:
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
    bounded_start, bounded_end = start, end
    start, end = _punctuated_word_bounds(segments, start, end)
    # Sentence snapping is best-effort. Do not let it undo the clip duration
    # limit established above.
    if end - start > maximum:
        start, end = bounded_start, bounded_end
    if end - start < minimum:
        end = min(float(segments[-1]["end"]), start + minimum)

    # Trim excessive leading or trailing dead air if word timestamps exist
    start, end = _trim_dead_air(segments, start, end, min_duration=minimum, max_duration=maximum)
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
        before_text = " ".join(
            str(segment.get("text", "")).strip() for segment in segments
            if float(segment["end"]) <= start and float(segment["end"]) >= start - 20.0
        ).strip()
        after_text = " ".join(
            str(segment.get("text", "")).strip() for segment in segments
            if float(segment["start"]) >= end and float(segment["start"]) <= end + 20.0
        ).strip()
        signals = analyze_story(text, end - start, before_text=before_text, after_text=after_text)
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
