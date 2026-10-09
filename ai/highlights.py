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
    visual = media.get("visual", {}).get("samples", [])
    on_screen = media.get("onScreen", {}).get("samples", [])
    semantic = media.get("visualSemantic", [])
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
        visual_rows = [v for v in visual if start <= float(v.get("time", -1)) <= end]
        visual_change = sum(float(v.get("visualChange", 0)) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        motion = sum(float(v.get("motion", 0)) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        center_detail = sum(float(v.get("centerDetail", 0)) for v in visual_rows) / len(visual_rows) if visual_rows else 0.0
        screen_rows = [v for v in on_screen if start <= float(v.get("time", -1)) <= end]
        action_labels = sorted({label for row in screen_rows for label in row.get("actionLabels", [])})
        ocr_text = " ".join(str(row.get("ocrText", "")) for row in screen_rows).strip()
        gameplay_like = sum(1 for row in screen_rows if row.get("gameplayLike")) / len(screen_rows) if screen_rows else 0.0
        semantic_rows = [v for v in semantic if start <= float(v.get("time", -1)) <= end]
        semantic_score = sum(float(v.get("score", 0)) for v in semantic_rows) / len(semantic_rows) if semantic_rows else 0.0

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
