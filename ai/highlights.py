import math
import re

CUES = {
    "funny": ["laugh", "laughed", "hilarious", "funny", "joke", "roast", "lmao", "lol", "ridiculous", "comedy", "cracking up", "too good"],
    "reaction": ["oh my", "what", "no way", "wait", "wow", "bro", "damn", "holy", "omg", "are you serious", "unbelievable", "insane", "look at that", "what the"],
    "drama": ["serious", "never", "can't believe", "crazy", "fight", "angry", "betrayal", "argument", "exposed", "shocking", "threat", "conflict"],
    "quotable": ["the truth", "remember", "lesson", "important", "meaning", "realize"],
    "unexpected": ["actually", "turns out", "didn't know", "surprise", "unexpected", "plot twist", "who knew", "sudden", "never expected", "out of nowhere"],
    "fail / win": ["win", "won", "lost", "fail", "failed", "victory", "clutch", "choke", "game over", "comeback", "ace", "epic", "legendary"],
    "wholesome": ["love", "proud", "thank", "kind", "family", "helped"],
}
ALIASES = {"ai detect": "ai_detect", "fail/win": "fail / win"}

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())

def _contains_cue(text: str, cue: str) -> bool:
    """Match complete cue words/phrases, not accidental substrings."""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    phrase = re.sub(r"\s+", " ", cue.lower()).strip()
    return bool(
        phrase
        and re.search(
            r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])",
            normalized,
        )
    )

def score(text: str, start: float, end: float, instruction: str | None = None):
    words = _words(text)
    duration = max(.5, end - start)
    density = min(1, len(words) / max(duration * 2.2, 1))
    punct = min(1, (text.count("!") + text.count("?")) / 3)
    novelty = len(set(words)) / max(len(words), 1)
    cue_hits = sum(1 for xs in CUES.values() for x in xs if _contains_cue(text, x))
    cue = min(1, cue_hits / 4)
    custom = 0.0
    if instruction:
        iw = _words(instruction)
        custom = sum(1 for x in iw if x in set(words)) / max(1, len(iw))
    question = 1.0 if "?" in text else 0.0
    hook = min(1.0, punct * .55 + question * .35 + cue * .35)
    return round(100 * (.20 * density + .13 * punct + .13 * novelty + .22 * cue + .12 * custom + .20 * hook), 2)

def _number(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if math.isfinite(number) else fallback


def _rows(value):
    """Return only object rows from optional media evidence collections."""
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _window_text(segments, start, end):
    pieces = []
    for segment in _rows(segments):
        seg_start = _number(segment.get("start"), -1)
        seg_end = _number(segment.get("end"), -1)
        if seg_start >= 0 and seg_end > seg_start and seg_end > start and seg_start < end:
            text = str(segment.get("text", "")).strip()
            if text:
                pieces.append(text)
    return " ".join(pieces).strip()

def candidates(segments, instruction=None, categories=None, media=None):
    allowed = {ALIASES.get(str(c).lower(), str(c).lower()) for c in (categories or ["ai_detect"])}
    media = media if isinstance(media, dict) else {}
    vision = media.get("vision") if isinstance(media.get("vision"), dict) else {}
    scenes_block = media.get("scenes") if isinstance(media.get("scenes"), dict) else {}
    visual_block = media.get("visual") if isinstance(media.get("visual"), dict) else {}
    screen_block = media.get("onScreen") if isinstance(media.get("onScreen"), dict) else {}
    faces = _rows(vision.get("faces", []))
    scenes = scenes_block.get("sceneChanges", [])
    scenes = scenes if isinstance(scenes, list) else []
    audio = _rows(media.get("audioWindows", []))
    visual = _rows(visual_block.get("samples", []))
    on_screen = _rows(screen_block.get("samples", []))
    semantic = _rows(media.get("visualSemantic", []))
    out = []
    for idx, s in enumerate(_rows(segments)):
        raw_start, raw_end = _number(s.get("start"), -1), _number(s.get("end"), -1)
        if raw_start < 0 or raw_end <= raw_start:
            continue
        # Expand around a transcript segment so the model sees setup + payoff.
        start = max(0.0, raw_start - 4.0)
        end = raw_end + 6.0
        text = _window_text(segments, start, end)
        if len(text) < 28:
            continue
        low = text.lower()
        base = score(text, start, end, instruction)
        matches = {k: sum(1 for x in xs if _contains_cue(low, x)) for k, xs in CUES.items()}
        best = max(matches, key=matches.get) if matches else "ai_detect"
        cat = best if matches.get(best, 0) else "ai_detect"
        if "ai_detect" not in allowed and cat not in allowed:
            ranked = [k for k, v in sorted(matches.items(), key=lambda z: z[1], reverse=True)
                      if k in allowed and v > 0]
            if not ranked:
                continue
            cat = ranked[0]

        face_points = [f for f in faces if start <= _number(f.get("time"), -1) <= end]
        face_hits = len(face_points)
        focus_x = (sum(_number(f.get("x"), .5) for f in face_points) / face_hits) if face_hits else .5
        scene_hits = sum(1 for x in scenes if start <= _number(x, -1) <= end)
        audio_rows = [a for a in audio if _number(a.get("end")) > start and _number(a.get("start")) < end]
        energy = sum(_number(a.get("energy")) for a in audio_rows) / len(audio_rows) if audio_rows else 0.0
        visual_rows = [v for v in visual if start <= _number(v.get("time"), -1) <= end]
        visual_change = sum(_number(v.get("visualChange")) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        motion = sum(_number(v.get("motion")) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        center_detail = sum(_number(v.get("centerDetail")) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        screen_rows = [v for v in on_screen if start <= _number(v.get("time"), -1) <= end]
        action_labels = sorted({
            str(label)
            for row in screen_rows
            for label in (row.get("actionLabels") if isinstance(row.get("actionLabels"), list) else [])
        })
        ocr_text = " ".join(str(row.get("ocrText", "")) for row in screen_rows).strip()
        gameplay_like = sum(1 for row in screen_rows if row.get("gameplayLike")) / len(screen_rows) if screen_rows else 0.0
        semantic_rows = [v for v in semantic if start <= _number(v.get("time"), -1) <= end]
        semantic_score = sum(_number(v.get("score")) for v in semantic_rows) / len(semantic_rows) if semantic_rows else 0.0

        # Strong moments tend to have a hook, a change, and a payoff signal.
        score_value = min(100, round(base + min(7, face_hits * 1.2) +
                                     min(6, scene_hits * 1.5) + min(6, energy * 6) +
                                     min(5, visual_change * 5) + min(4, motion * 4) + min(2, center_detail * 2) +
                                     min(4, len(action_labels) * 1.5) + min(2, gameplay_like * 2) +
                                     (max(0, min(5, (semantic_score - 50) * 0.1)) if semantic_rows else 0), 2))
        out.append({
            "start": start,
            "end": end,
            "text": text,
            "score": score_value,
            "category": cat,
            "rationale": "Ranked from transcript, audio, visual change/motion, face presence and available on-screen action cues.",
            "features": {
                "wordCount": len(_words(text)),
                "segmentIndex": idx,
                "categoryMatches": matches,
                "faceHits": face_hits,
                "faceFocusX": round(focus_x, 4),
                "sceneHits": scene_hits,
                "audioEnergy": round(energy, 3),
                "visualChange": round(visual_change, 4),
                "motion": round(motion, 4),
                "centerDetail": round(center_detail, 4),
                "onScreenActionLabels": action_labels,
                "onScreenText": ocr_text[:1200],
                "gameplayLikeRatio": round(gameplay_like, 4),
                "visualSemanticScore": round(semantic_score, 3) if semantic_rows else None,
                "hookSignals": {
                    "questions": text.count("?"),
                    "exclamations": text.count("!"),
                },
            },
        })
    return sorted(out, key=lambda x: x["score"], reverse=True)[:80]
