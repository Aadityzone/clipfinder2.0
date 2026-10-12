import json
import logging
import math
import os
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


def _features(candidate: dict) -> dict:
    features = candidate.get("features")
    if not isinstance(features, dict):
        features = {}
        candidate["features"] = features
    return features


def _set_diagnostic(candidate: dict, status: str, reason: str | None = None) -> None:
    features = _features(candidate)
    diagnostic = {"status": status}
    if reason:
        diagnostic["reason"] = reason
    features["llmScoring"] = diagnostic


def _valid_score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        score = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(score):
        return None
    return max(0.0, min(100.0, score))


def score_candidates(candidates: list[dict], transcript: str, instruction: str | None = None) -> list[dict]:
    if not candidates:
        return candidates

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        for candidate in candidates:
            _set_diagnostic(candidate, "skipped", "missing_api_key")
        return candidates

    try:
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        submitted = candidates[:80]
        compact = [{
            "i": i,
            "start": c["start"],
            "end": c["end"],
            "text": c.get("text", ""),
            "category": c.get("category"),
            "features": {
                "hookSignals": _features(c).get("hookSignals", {}),
                "audioEnergy": _features(c).get("audioEnergy", 0),
                "sceneHits": _features(c).get("sceneHits", 0),
                "faceHits": _features(c).get("faceHits", 0),
                # Keep event provenance visible to the model; empty transcript text
                # must not make a visual/audio candidate look like an ordinary quote.
                "candidateSource": _features(c).get("candidateSource", "transcript"),
                "eventTypes": _features(c).get("eventTypes", []),
                "eventEvidenceScore": _features(c).get("eventEvidenceScore"),
                "visualChange": _features(c).get("visualChange", 0),
                "motion": _features(c).get("motion", 0),
                "gameplayLike": _features(c).get("gameplayLike", False),
                "onScreenActionLabels": _features(c).get("onScreenActionLabels", []),
                "onScreenText": _features(c).get("onScreenText", "")[:300],
            },
        } for i, c in enumerate(submitted)]
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
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, dict) or not isinstance(data.get("output_text"), str):
            raise ValueError("missing output_text")
        ranked = json.loads(data["output_text"])
        if not isinstance(ranked, list):
            raise ValueError("model output must be an array")
    except Exception as exc:
        logger.warning("LLM candidate scoring failed: %s", type(exc).__name__)
        for candidate in candidates:
            _set_diagnostic(candidate, "failed", "request_or_response_error")
        return candidates

    valid_by_index: dict[int, tuple[float, str | None]] = {}
    invalid_rows = False
    for item in ranked:
        if not isinstance(item, dict):
            invalid_rows = True
            continue
        index = item.get("i")
        score = _valid_score(item.get("score"))
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(submitted) or score is None:
            invalid_rows = True
            continue
        if index in valid_by_index:
            invalid_rows = True
            continue
        rationale = item.get("rationale")
        valid_by_index[index] = (score, rationale[:1000] if isinstance(rationale, str) else None)

    for index, candidate in enumerate(candidates):
        if index >= len(submitted):
            _set_diagnostic(candidate, "skipped", "candidate_limit")
            continue
        result = valid_by_index.get(index)
        if result is None:
            _set_diagnostic(candidate, "partial" if valid_by_index else "skipped",
                             "invalid_model_output" if invalid_rows else "no_score_for_candidate")
            continue

        llm_score, rationale = result
        original_score = _valid_score(candidate.get("score"))
        if original_score is None:
            _set_diagnostic(candidate, "skipped", "invalid_candidate_score")
            continue
        candidate["score"] = round(original_score * .55 + llm_score * .45, 2)
        if rationale:
            candidate["rationale"] = rationale
        features = _features(candidate)
        features["llmScore"] = llm_score
        _set_diagnostic(candidate, "applied")

    return candidates
