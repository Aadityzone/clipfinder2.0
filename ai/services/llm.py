import base64
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


def _candidate_frame_data_url(media_path: str, time_s: float) -> str | None:
    """Encode one bounded, low-resolution frame for visual model evidence."""
    if not media_path or not os.path.isfile(media_path):
        return None
    capture = None
    try:
        import cv2

        capture = cv2.VideoCapture(media_path)
        if not capture.isOpened():
            return None
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(time_s)) * 1000)
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        height, width = frame.shape[:2]
        scale = min(1.0, 512.0 / max(height, width))
        if scale < 1.0:
            frame = cv2.resize(
                frame,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
        if not ok:
            return None
        return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
    except Exception:
        # Visual evidence is optional: keep the transcript/audio pipeline available.
        return None
    finally:
        if capture is not None:
            capture.release()


def _request_body(model: str, prompt: dict, frame_urls: dict[int, str] | None = None) -> bytes:
    content = [{"type": "input_text", "text": json.dumps(prompt)}]
    for index, data_url in (frame_urls or {}).items():
        content.append({"type": "input_text", "text": f"Visual evidence for candidate index {index} (one frame near its midpoint):"})
        content.append({"type": "input_image", "image_url": data_url, "detail": "low"})
    return json.dumps({
        "model": model,
        "input": [
            {"role": "system", "content":
             "Return JSON only: an array of objects with i, score (0-100), rationale. "
             "Judge transcript text and supplied frame/audio evidence. Images show only one sampled frame per candidate, not the whole event. "
             "Do not infer motion, dialogue, or outcomes that a still frame cannot establish. Do not invent events or candidates. "
             "Low-level motion, scene changes, or loud audio alone do not prove that a kill, fight, win, joke, or reveal occurred. "
             "When text is empty, rank only observable evidence and remain conservative."},
            {"role": "user", "content": content},
        ],
    }).encode()


def score_candidates(
    candidates: list[dict],
    transcript: str,
    instruction: str | None = None,
    media_path: str | None = None,
) -> list[dict]:
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
            "visualChange": c.get("features", {}).get("visualChange", 0),
            "motion": c.get("features", {}).get("motion", 0),
            "gameplayLikeRatio": c.get("features", {}).get("gameplayLikeRatio", 0),
            "onScreenActionLabels": c.get("features", {}).get("onScreenActionLabels", []),
            "eventKind": c.get("features", {}).get("eventKind"),
            "eventStrength": c.get("features", {}).get("eventStrength", 0),
        },
    } for i, c in enumerate(candidates[:80])]
    prompt = {
        "instruction": instruction or "Rank moments by genuine clip-worthiness.",
        "transcript_context": transcript[:30000],
        "candidates": compact,
        "visual_evidence_note": (
            "For a subset of candidates, a single sampled frame follows the JSON. "
            "Treat it as partial visual context, not proof of what happened over time."
        ),
    }
    frame_urls = {}
    if media_path:
        # Cap image payload size and cost; text ranking still covers up to 80 candidates.
        for index, candidate in enumerate(candidates[:12]):
            try:
                midpoint = (float(candidate["start"]) + float(candidate["end"])) / 2
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            frame_url = _candidate_frame_data_url(media_path, midpoint)
            if frame_url:
                frame_urls[index] = frame_url

    req = Request(
        base + "/responses",
        data=_request_body(model, prompt, frame_urls),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        try:
            with urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except Exception:
            # Some OpenAI-compatible providers do not accept image inputs. Retry
            # text-only so optional vision support never disables basic LLM ranking.
            if not frame_urls:
                raise
            fallback = Request(
                base + "/responses",
                data=_request_body(model, prompt),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            )
            with urlopen(fallback, timeout=45) as resp:
                data = json.loads(resp.read())
        ranked = _parse_rankings(_response_text(data))
        for i, candidate in enumerate(candidates[:80]):
            item = ranked.get(i)
            if item:
                llm_score = item["score"]
                candidate["score"] = round(float(candidate.get("score", 0)) * .55 + llm_score * .45, 2)
                if item["rationale"]:
                    candidate["rationale"] = item["rationale"]
                features = candidate.setdefault("features", {})
                features["llmScore"] = llm_score
                if i in frame_urls:
                    features["llmVisualEvidence"] = True
    except Exception:
        # LLM scoring is an optional enhancement; deterministic ranking remains available.
        pass
    return candidates
