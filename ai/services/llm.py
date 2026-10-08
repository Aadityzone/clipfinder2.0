import json
import os
from urllib.request import Request, urlopen

def score_candidates(candidates: list[dict], transcript: str, instruction: str | None = None) -> list[dict]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or not candidates:
        return candidates
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    compact = [{
        "i": i,
        "start": c["start"],
        "end": c["end"],
        "text": c.get("text", ""),
        "category": c.get("category"),
        "features": {
            "hookSignals": c.get("features", {}).get("hookSignals", {}),
            "audioEnergy": c.get("features", {}).get("audioEnergy", 0),
            "sceneHits": c.get("features", {}).get("sceneHits", 0),
            "faceHits": c.get("features", {}).get("faceHits", 0),
        },
    } for i, c in enumerate(candidates[:80])]
    prompt = {
        "instruction": instruction or "Rank moments by genuine clip-worthiness.",
        "transcript_context": transcript[:30000],
        "candidates": compact,
    }
    body = json.dumps({
        "model": model,
        "input": [
            {"role": "system", "content":
             "Return JSON only: an array of objects with i, score (0-100), rationale. "
             "Judge the supplied text and context. Do not invent candidates."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }).encode()
    req = Request(base + "/responses", data=body,
                  headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        raw = data.get("output_text", "")
        ranked = json.loads(raw)
        by = {int(x["i"]): x for x in ranked
              if isinstance(x, dict) and str(x.get("i", "")).isdigit()}
        for i, c in enumerate(candidates):
            x = by.get(i)
            if x:
                llm = max(0, min(100, float(x.get("score", c["score"]))))
                c["score"] = round(c["score"] * .55 + llm * .45, 2)
                c["rationale"] = str(x.get("rationale") or c.get("rationale") or "")
                c.setdefault("features", {})["llmScore"] = llm
    except Exception:
        pass
    return candidates
