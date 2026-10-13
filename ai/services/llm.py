import json
import os
from urllib.request import Request, urlopen


def _response_text(data: dict) -> str:
    """Extract generated text from both SDK-style and raw Responses API payloads."""
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                value = part.get("text")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
    return "\n".join(chunks)


def _parse_rankings(raw: str) -> dict[int, dict]:
    """Parse model rankings defensively; ignore malformed and out-of-range indexes."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("candidates", parsed.get("rankings", []))
    if not isinstance(parsed, list):
        return {}

    ranked = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        index = item.get("i")
        try:
            index = int(index)
            score = float(item.get("score"))
        except (TypeError, ValueError, OverflowError):
            continue
        if index < 0 or not 0 <= score <= 100:
            continue
        ranked[index] = {
            "score": score,
            "rationale": str(item.get("rationale") or "").strip(),
        }
    return ranked


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
        ranked = _parse_rankings(_response_text(data))
        for i, candidate in enumerate(candidates[:80]):
            item = ranked.get(i)
            if item:
                llm_score = item["score"]
                candidate["score"] = round(float(candidate.get("score", 0)) * .55 + llm_score * .45, 2)
                if item["rationale"]:
                    candidate["rationale"] = item["rationale"]
                candidate.setdefault("features", {})["llmScore"] = llm_score
    except Exception:
        # LLM scoring is an optional enhancement; a provider failure must not
        # break the deterministic transcript/audio/visual ranking pipeline.
        pass
    return candidates
