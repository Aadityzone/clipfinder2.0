import re

PRONOUNS = {
    "first_person": {"i", "me", "my", "mine", "we", "us", "our"},
    "second_person": {"you", "your", "yours"},
    "third_person": {"he", "she", "they", "them", "his", "her", "their"},
}

def speaker_signals(segments: list[dict]) -> dict:
    """Infer conversational structure without pretending Whisper diarization exists."""
    rows = []
    previous_style = None
    for i, segment in enumerate(segments):
        text = str(segment.get("text", "")).strip()
        tokens = re.findall(r"[a-z0-9']+", text.lower())
        if not tokens:
            continue
        counts = {name: sum(1 for t in tokens if t in words) for name, words in PRONOUNS.items()}
        style = "question" if "?" in text else "exclamation" if "!" in text else "statement"
        transition = previous_style is not None and style != previous_style
        rows.append({
            "segmentIndex": i,
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "style": style,
            "transition": transition,
            "firstPerson": counts["first_person"],
            "secondPerson": counts["second_person"],
            "thirdPerson": counts["third_person"],
        })
        previous_style = style
    return {
        "segments": rows,
        "questionCount": sum(1 for r in rows if r["style"] == "question"),
        "styleTransitions": sum(1 for r in rows if r["transition"]),
    }
