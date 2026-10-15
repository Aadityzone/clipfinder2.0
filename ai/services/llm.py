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


def ranking_capabilities() -> dict:
    """Expose safe provider readiness metadata without revealing credentials."""
    if os.getenv("OPENAI_API_KEY"):
        return {
            "provider": "openai-compatible",
            "configured": True,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "visualRanking": True,
        }
    if os.getenv("OLLAMA_BASE_URL", "").strip():
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        normalized = model.lower()
        vision_model = any(
            marker in normalized
            for marker in ("qwen2.5vl", "qwen3-vl", "llava", "minicpm-v", "vision", "gemma3")
        )
        return {
            "provider": "ollama",
            "configured": True,
            "model": model,
            "visualRanking": vision_model,
        }
    return {
        "provider": "heuristic",
        "configured": False,
        "model": None,
        "visualRanking": False,
    }


def _ollama_supports_vision(model: str) -> bool:
    normalized = model.lower()
    return any(
        marker in normalized
        for marker in ("qwen2.5vl", "qwen3-vl", "llava", "minicpm-v", "vision", "gemma3")
    )


def _ollama_response_text(data: dict) -> str:
    message = data.get("message")
    if isinstance(message, dict):
        value = message.get("content")
        if isinstance(value, str):
            return value.strip()
    return ""


def _ollama_request_body(
    model: str,
    prompt: dict,
    frame_urls: dict[int, str] | None = None,
) -> bytes:
    messages = [
        {
            "role": "system",
            "content": (
                "Return JSON only: an array of objects with i, score (0-100), rationale. "
                "Rank genuine clip-worthiness using transcript and any attached single-frame evidence. "
                "A still image cannot prove motion, dialogue, or an outcome. Do not invent events."
            ),
        },
        {"role": "user", "content": json.dumps(prompt)},
    ]
    for index, data_url in (frame_urls or {}).items():
        if "," not in data_url:
            continue
        messages.append({
            "role": "user",
            "content": f"Visual evidence for candidate index {index}, sampled near its midpoint. This is only one frame.",
            "images": [data_url.split(",", 1)[1]],
        })
    return json.dumps({
        "model": model,
        "stream": False,
        "format": "json",
        "messages": messages,
        "options": {"temperature": 0.1},
    }).encode()


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


def _candidate_frame_data_urls(
    media_path: str,
    candidates: list[dict],
    limit: int = 12,
) -> dict[int, str]:
    """Sample a bounded set of candidate frames using one video decoder handle."""
    if not media_path or not os.path.isfile(media_path):
        return {}
    capture = None
    result: dict[int, str] = {}
    try:
        import cv2

        capture = cv2.VideoCapture(media_path)
        if not capture.isOpened():
            return {}
        for index, candidate in enumerate(candidates[:max(0, limit)]):
            try:
                midpoint = (float(candidate["start"]) + float(candidate["end"])) / 2
                if midpoint < 0:
                    continue
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            capture.set(cv2.CAP_PROP_POS_MSEC, midpoint * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            scale = min(1.0, 512.0 / max(height, width))
            if scale < 1.0:
                frame = cv2.resize(
                    frame,
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
            if ok:
                result[index] = "data:image/jpeg;base64," + base64.b64encode(
                    encoded.tobytes()
                ).decode("ascii")
    except Exception:
        # Visual evidence is optional: keep transcript/audio ranking available.
        return result
    finally:
        if capture is not None:
            capture.release()
    return result


def _candidate_frame_data_url(media_path: str, time_s: float) -> str | None:
    """Compatibility helper for a single timestamp."""
    frames = _candidate_frame_data_urls(
        media_path, [{"start": time_s, "end": time_s}], limit=1
    )
    return frames.get(0)


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
    if not candidates:
        return candidates

    openai_key = os.getenv("OPENAI_API_KEY")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if not openai_key and not ollama_base:
        return candidates

    provider = "openai" if openai_key else "ollama"
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") if openai_key else ollama_base
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini") if openai_key else os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
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
            "Some candidates may have a single sampled frame attached. "
            "Treat it as partial visual context, not proof of an event over time."
        ),
    }
    # Sample frames only for providers/models that can accept image inputs.
    can_see_frames = provider == "openai" or _ollama_supports_vision(model)
    frame_urls = (
        _candidate_frame_data_urls(media_path, candidates, limit=12)
        if media_path and can_see_frames else {}
    )

    def make_request(with_frames: bool) -> Request:
        frames = frame_urls if with_frames else {}
        if provider == "ollama":
            return Request(
                base + "/api/chat",
                data=_ollama_request_body(model, prompt, frames),
                headers={"Content-Type": "application/json"},
            )
        return Request(
            base + "/responses",
            data=_request_body(model, prompt, frames),
            headers={"Authorization": "Bearer " + openai_key, "Content-Type": "application/json"},
        )

    try:
        try:
            with urlopen(make_request(bool(frame_urls)), timeout=90 if provider == "ollama" else 60) as resp:
                data = json.loads(resp.read())
        except Exception:
            # Providers without vision support can still rank transcript candidates.
            if not frame_urls:
                raise
            with urlopen(make_request(False), timeout=90 if provider == "ollama" else 45) as resp:
                data = json.loads(resp.read())

        raw = _ollama_response_text(data) if provider == "ollama" else _response_text(data)
        ranked = _parse_rankings(raw)
        for i, candidate in enumerate(candidates[:80]):
            item = ranked.get(i)
            if item:
                llm_score = item["score"]
                candidate["score"] = round(float(candidate.get("score", 0)) * .55 + llm_score * .45, 2)
                if item["rationale"]:
                    candidate["rationale"] = item["rationale"]
                features = candidate.setdefault("features", {})
                features["llmScore"] = llm_score
                features["llmProvider"] = provider
                if i in frame_urls:
                    features["llmVisualEvidence"] = True
    except Exception:
        # LLM is optional; deterministic ranking remains available if a provider is offline.
        pass
    return candidates
