import re

CUES = {
    "funny": ["laugh", "laughed", "hilarious", "funny", "joke", "roast"],
    "reaction": ["oh my", "what", "no way", "wait", "wow", "bro", "damn"],
    "drama": ["serious", "never", "can't believe", "crazy", "fight", "angry"],
    "quotable": ["the truth", "remember", "lesson", "important", "meaning", "realize"],
    "unexpected": ["actually", "turns out", "didn't know", "surprise", "unexpected"],
    "fail / win": ["win", "won", "lost", "fail", "failed", "victory", "clutch"],
    "wholesome": ["love", "proud", "thank", "kind", "family", "helped"],
}
ALIASES = {"ai detect": "ai_detect", "fail/win": "fail / win"}

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())

def score(text: str, start: float, end: float, instruction: str | None = None):
    words = _words(text)
    duration = max(.5, end - start)
    density = min(1, len(words) / max(duration * 2.2, 1))
    punct = min(1, (text.count("!") + text.count("?")) / 3)
    novelty = len(set(words)) / max(len(words), 1)
    cue_hits = sum(1 for xs in CUES.values() for x in xs if x in text.lower())
    cue = min(1, cue_hits / 4)
    custom = 0.0
    if instruction:
        iw = _words(instruction)
        custom = sum(1 for x in iw if x in set(words)) / max(1, len(iw))
    question = 1.0 if "?" in text else 0.0
    hook = min(1.0, punct * .55 + question * .35 + cue * .35)
    return round(100 * (.20 * density + .13 * punct + .13 * novelty + .22 * cue + .12 * custom + .20 * hook), 2)

def _window_text(segments, start, end):
    return " ".join(str(s.get("text", "")).strip() for s in segments
                    if float(s["end"]) > start and float(s["start"]) < end).strip()

def candidates(segments, instruction=None, categories=None, media=None):
    allowed = {ALIASES.get(str(c).lower(), str(c).lower()) for c in (categories or ["ai_detect"])}
    media = media or {}
    faces = media.get("vision", {}).get("faces", [])
    scenes = media.get("scenes", {}).get("sceneChanges", [])
    audio = media.get("audioWindows", [])
    out = []
    for idx, s in enumerate(segments):
        raw_start, raw_end = float(s["start"]), float(s["end"])
        if raw_end <= raw_start:
            continue
        # Expand around a transcript segment so the model sees setup + payoff.
        start = max(0.0, raw_start - 4.0)
        end = raw_end + 6.0
        text = _window_text(segments, start, end)
        if len(text) < 28:
            continue
        low = text.lower()
        base = score(text, start, end, instruction)
        matches = {k: sum(1 for x in xs if x in low) for k, xs in CUES.items()}
        best = max(matches, key=matches.get) if matches else "ai_detect"
        cat = best if matches.get(best, 0) else "ai_detect"
        if "ai_detect" not in allowed and cat not in allowed:
            ranked = [k for k, v in sorted(matches.items(), key=lambda z: z[1], reverse=True)
                      if k in allowed and v > 0]
            if not ranked:
                continue
            cat = ranked[0]

        face_points = [f for f in faces if start <= float(f.get("time", -1)) <= end]
        face_hits = len(face_points)
        focus_x = (sum(float(f.get("x", .5)) for f in face_points) / face_hits) if face_hits else .5
        scene_hits = sum(1 for x in scenes if start <= float(x) <= end)
        audio_rows = [a for a in audio if float(a.get("end", 0)) > start and float(a.get("start", 0)) < end]
        energy = sum(float(a.get("energy", 0)) for a in audio_rows) / len(audio_rows) if audio_rows else 0.0

        # Strong moments tend to have a hook, a change, and a payoff signal.
        score_value = min(100, round(base + min(7, face_hits * 1.2) +
                                     min(6, scene_hits * 1.5) + min(6, energy * 6), 2))
        out.append({
            "start": start,
            "end": end,
            "text": text,
            "score": score_value,
            "category": cat,
            "rationale": "Ranked from transcript hook, lexical novelty, category cues, visual change, face presence and audio energy.",
            "features": {
                "wordCount": len(_words(text)),
                "segmentIndex": idx,
                "categoryMatches": matches,
                "faceHits": face_hits,
                "faceFocusX": round(focus_x, 4),
                "sceneHits": scene_hits,
                "audioEnergy": round(energy, 3),
                "hookSignals": {
                    "questions": text.count("?"),
                    "exclamations": text.count("!"),
                },
            },
        })
    return sorted(out, key=lambda x: x["score"], reverse=True)[:80]
