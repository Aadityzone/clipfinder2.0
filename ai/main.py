from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .schemas import TranscribeRequest, TranscribeResponse
from .transcribe import transcribe
from .services.transcription_range import transcribe_range
from .services.analysis_range import extract_analysis_range, shift_segments_to_range, validate_analysis_range
from .services.download import download, download_range, get_video_metadata
from .services.media import ffprobe
from .services.render import render
from .highlights import candidates
from .longform import stories, package
from .services.media_intelligence import analyze_media
from .services.dedup import deduplicate, enforce_temporal_diversity
from .services.llm import score_candidates, ranking_capabilities
from .services.semantic import enrich_semantics
from .services.transcript_rag import enrich_candidates_with_context
from .services.story_intelligence import optimize_candidates
from .services.speaker_intelligence import speaker_signals
from .services.diarization import diarize, diarization_status
from .services.visual_intelligence import semantic_frame_scores, visual_capabilities
from .services.action_intelligence import _classify_ocr
from .services.creator_feedback import apply_creator_preferences
from .services.genre_intelligence import apply_genre_profile, VALID_GENRES
from .services.candidate_contract import validate_candidates
from .services.visual_candidates import multimodal_event_candidates
import hmac
import os
import uuid
import importlib.util
import shutil
import tempfile
import subprocess

app = FastAPI(title="Clip Finder AI", version="2.2.0")

class IngestRequest(BaseModel):
    url: str
    output_dir: str
    start_seconds: float | None = None
    end_seconds: float | None = None

class SourceMetadataRequest(BaseModel):
    url: str

class IngestResponse(BaseModel):
    media_path: str
    metadata: dict

class ProbeRequest(BaseModel):
    media_path: str

class ThumbnailRequest(BaseModel):
    input_path: str
    output_path: str
    time: float = 0

class AnalyzeRequest(BaseModel):
    segments: list[dict]
    instruction: str | None = None
    categories: list[str] = []
    media_path: str | None = None
    creator_preferences: dict[str, float] | None = None
    genre: str = "auto"
    start_seconds: float | None = None
    end_seconds: float | None = None

class AnalyzeResponse(BaseModel):
    candidates: list[dict]

class LongFormResponse(BaseModel):
    stories: list[dict]
    title: str
    description: str
    chapters: list[dict]

class RenderRequest(BaseModel):
    input_path: str
    output_path: str
    start: float = 0
    end: float = 0
    aspect: str = "9:16"
    segments: list[dict] | None = None
    captions: list[dict] | None = None
    caption_style: dict | None = None
    focus_x: float = 0.5

def auth(secret: str | None):
    expected = os.getenv("AI_SERVICE_SECRET")
    production = (
        os.getenv("ENVIRONMENT", "").lower() == "production"
        or os.getenv("NODE_ENV", "").lower() == "production"
    )
    if not expected:
        if production:
            raise HTTPException(
                status_code=503,
                detail="AI service authentication is not configured",
            )
        # Local development remains convenient, but production fails closed.
        return
    if not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=401, detail="Invalid AI service credentials")

@app.get("/health")
def health():
    dependencies = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "yt_dlp": shutil.which("yt-dlp") is not None,
    }
    ready = all(dependencies.values())
    return {
        "ok": ready,
        "service": "ai",
        "version": "2.2.0",
        "dependencies": dependencies,
    }

@app.post("/v1/ingest", response_model=IngestResponse)
def ingest(b: IngestRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    try:
        has_start, has_end = b.start_seconds is not None, b.end_seconds is not None
        if has_start != has_end:
            raise ValueError("Both start_seconds and end_seconds are required for a selected source range.")
        range_metadata = None
        output_dir = os.path.join(b.output_dir, uuid.uuid4().hex)
        if has_start:
            source = get_video_metadata(b.url)
            start, end = float(b.start_seconds), float(b.end_seconds)
            if start < 0 or end <= start or end > source["duration"] + 0.05 or end - start > 3 * 60 * 60:
                raise ValueError("Selected source range is outside the source duration or exceeds three hours.")
            path = download_range(b.url, output_dir, start, min(end, source["duration"]))
            range_metadata = {"sourceDuration": source["duration"], "sourceStartS": start, "sourceEndS": min(end, source["duration"])}
        else:
            path = download(b.url, output_dir)
        metadata = ffprobe(path)
        if not metadata.get("duration") or not metadata.get("width") or not metadata.get("height"):
            raise RuntimeError("Downloaded media has no valid video stream or duration.")
        if range_metadata:
            metadata.update(range_metadata)
        return {"media_path": path, "metadata": metadata}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/v1/source-metadata")
def source_metadata(b: SourceMetadataRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    try:
        return get_video_metadata(b.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/v1/probe")
def probe(b: ProbeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    if not os.path.isfile(b.media_path):
        raise HTTPException(status_code=404, detail="Media file not found")
    return ffprobe(b.media_path)

@app.post("/v1/thumbnail")
def thumbnail(b: ThumbnailRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    try:
        os.makedirs(os.path.dirname(b.output_path), exist_ok=True)
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-ss", str(max(0, b.time)), "-i", b.input_path,
                        "-frames:v", "1", "-q:v", "2", b.output_path], check=True)
        if not os.path.isfile(b.output_path):
            raise RuntimeError("Thumbnail was not created")
        return {"output_path": b.output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/transcribe", response_model=TranscribeResponse)
def transcribe_route(b: TranscribeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    if not os.path.isfile(b.media_path):
        raise HTTPException(status_code=404, detail="Media file not found")
    try:
        if b.start_seconds is None and b.end_seconds is None:
            return transcribe(b.media_path, b.language)
        if b.start_seconds is None or b.end_seconds is None:
            raise HTTPException(status_code=400, detail="Both start_seconds and end_seconds are required for a source range.")
        source_duration = float(ffprobe(b.media_path).get("duration") or 0)
        return transcribe_range(
            b.media_path, b.start_seconds, b.end_seconds, source_duration, b.language
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/ai-capabilities")
def ai_capabilities(x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    return {"diarization": diarization_status(), "semantic_embeddings": importlib.util.find_spec("sentence_transformers") is not None, "visual": visual_capabilities(), "ocr": {"installed": importlib.util.find_spec("pytesseract") is not None, "system_binary_available": shutil.which("tesseract") is not None, "requires_system_tesseract": True}, "genre_profiles": list(VALID_GENRES), "ranking": ranking_capabilities()}

def _ensure_candidate_titles(candidates: list[dict]) -> list[dict]:
    """Give every candidate a transparent title fallback when no LLM title exists."""
    for candidate in candidates:
        title = candidate.get("title")
        if isinstance(title, str) and title.strip():
            continue
        features = candidate.setdefault("features", {})
        words = str(candidate.get("text") or "").split()
        if words:
            title = " ".join(words[:8]).strip(" .,!?:;")
            if len(words) > 8:
                title += "…"
            features["titleSource"] = "transcript_extract"
        else:
            try:
                start = max(0, int(float(candidate.get("start", 0))))
            except (TypeError, ValueError, OverflowError):
                start = 0
            timestamp = f"{start // 60:02d}:{start % 60:02d}"
            event = str(features.get("eventKind") or candidate.get("category") or "visual highlight")
            title = f"{event.replace('_', ' ').title()} at {timestamp}"
            features["titleSource"] = "visual_timestamp"
        candidate["title"] = title or "Untitled highlight"
    return candidates


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(b: AnalyzeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    if b.start_seconds is not None or b.end_seconds is not None:
        if b.start_seconds is None or b.end_seconds is None:
            raise HTTPException(status_code=400, detail="Both start_seconds and end_seconds are required for bounded analysis.")
        if not b.media_path or not os.path.isfile(b.media_path):
            raise HTTPException(status_code=404, detail="A valid media_path is required for bounded analysis.")
        source_duration = float(ffprobe(b.media_path).get("duration") or 0)
        try:
            range_start, range_end = validate_analysis_range(
                b.start_seconds, b.end_seconds, source_duration
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with tempfile.TemporaryDirectory(prefix="clipfinder-analysis-range-") as temporary:
            try:
                ranged_path = extract_analysis_range(
                    b.media_path, range_start, range_end, os.path.join(temporary, "analysis-range.mp4")
                )
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise HTTPException(status_code=500, detail=f"Could not prepare bounded analysis media: {exc}") from exc
            local_segments = shift_segments_to_range(b.segments, range_start, range_end)
            local_request = b.model_copy(update={
                "segments": local_segments,
                "media_path": ranged_path,
                "start_seconds": None,
                "end_seconds": None,
            })
            local_result = analyze(local_request, x_ai_secret)
            for candidate in local_result.get("candidates", []):
                candidate["start"] = round(float(candidate["start"]) + range_start, 3)
                candidate["end"] = round(float(candidate["end"]) + range_start, 3)
                rag = candidate.get("features", {}).get("transcriptRag", {})
                for context in rag.get("chunks", []):
                    context["start"] = round(float(context["start"]) + range_start, 3)
                    context["end"] = round(float(context["end"]) + range_start, 3)
            absolute_candidates = validate_candidates(local_result.get("candidates", []), source_duration)
            absolute_candidates = sorted(absolute_candidates, key=lambda item: float(item.get("score", 0)), reverse=True)
            return {"candidates": absolute_candidates[:50]}
    media_duration = None
    if b.media_path:
        if not os.path.isfile(b.media_path):
            raise HTTPException(status_code=404, detail="Media file not found")
        media_duration = ffprobe(b.media_path).get("duration")
    media = analyze_media(b.media_path) if b.media_path else {}
    if b.media_path and b.instruction and os.getenv("VISUAL_SEMANTIC_BACKEND", "").lower() == "clip":
        media["visualSemantic"] = semantic_frame_scores(b.media_path, b.instruction)
    result = candidates(b.segments, b.instruction, b.categories, media)
    # Optimize transcript-centered candidates before adding visual-only event windows;
    # the latter must keep their measured event timestamps rather than snap to speech.
    if b.segments:
        result = optimize_candidates(b.segments, result)
    requested_categories = {str(category).strip().lower().replace("_", " ") for category in b.categories}
    allow_visual_proposals = not requested_categories or bool(
        requested_categories & {"ai detect", "general", "all"}
    )
    if allow_visual_proposals and media:
        result.extend(multimodal_event_candidates(
            b.segments, media, media_duration, max_candidates=40
        ))
    result = enrich_semantics(result, b.instruction)
    # Enforce one genre-neutral contract before any downstream feature extraction.
    result = validate_candidates(result, media_duration)
    diarized = (
        diarize(b.media_path, b.segments)
        if b.media_path and b.segments
        else {"available": False, "segments": [], "reason": "media or transcript segments unavailable"}
    )
    analysis_segments = diarized.get("segments") or b.segments
    speaker = speaker_signals(analysis_segments)
    for candidate in result:
        related = [x for x in speaker["segments"] if x["end"] > candidate["start"] and x["start"] < candidate["end"]]
        candidate.setdefault("features", {})["conversation"] = {
            "questionCount": sum(1 for x in related if x["style"] == "question"),
            "styleTransitions": sum(1 for x in related if x["transition"]),
            "secondPerson": sum(x["secondPerson"] for x in related),
            "firstPerson": sum(x["firstPerson"] for x in related),
        }
    result = deduplicate(result)
    transcript = " ".join(str(s.get("text", "")) for s in analysis_segments)
    result, rag_context = enrich_candidates_with_context(result, analysis_segments)
    result = score_candidates(
        result, transcript, b.instruction, media_path=b.media_path, genre=b.genre,
        retrieved_context=rag_context,
    )
    for candidate in result:
        related = [s for s in analysis_segments if float(s["end"]) > candidate["start"] and float(s["start"]) < candidate["end"]]
        labels = [s.get("speaker") for s in related if s.get("speaker")]
        if labels:
            counts = {label: labels.count(label) for label in set(labels)}
            turns = sum(1 for a, z in zip(labels, labels[1:]) if a != z)
            candidate.setdefault("features", {})["speakers"] = {
                "labels": sorted(counts),
                "dominant": max(counts, key=counts.get),
                "speakerCount": len(counts),
                "turnCount": turns,
            }
            if len(counts) >= 2:
                candidate["score"] = round(min(100, float(candidate.get("score", 0)) + min(5, 2 + turns * 0.75)), 2)
    # Genre profiles can now use speaker-turn and diarization features when available.
    result = apply_genre_profile(result, transcript, b.genre)
    result = apply_creator_preferences(result, b.creator_preferences)
    result = _ensure_candidate_titles(result)
    # Revalidate after model/profile adjustments so the API never emits invalid scores.
    result = validate_candidates(result, media_duration)
    result = sorted(result, key=lambda x: float(x.get("score", 0)), reverse=True)
    return {"candidates": result[:50]}

@app.post("/v1/longform", response_model=LongFormResponse)
def longform(b: AnalyzeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    media_duration = None
    if b.media_path:
        if not os.path.isfile(b.media_path):
            raise HTTPException(status_code=404, detail="Media file not found")
        media_duration = ffprobe(b.media_path).get("duration")

    # Let the model compare a wider candidate pool before selecting the final six.
    # Apply the same genre-neutral contract used by short-form analysis so invalid
    # timestamps and non-finite/out-of-range scores cannot leak into chapters.
    items = validate_candidates(stories(b.segments, limit=40), media_duration)
    transcript = " ".join(str(segment.get("text", "")) for segment in b.segments)
    items = score_candidates(
        items, transcript, b.instruction, media_path=b.media_path, genre=b.genre
    )
    items = apply_genre_profile(items, transcript, b.genre)
    items = apply_creator_preferences(items, b.creator_preferences)
    items = validate_candidates(items, media_duration)
    items = deduplicate(items, threshold=0.55)
    items = validate_candidates(items, media_duration)
    items = sorted(items, key=lambda item: float(item.get("score", 0)), reverse=True)[:6]
    items = _ensure_candidate_titles(items)
    meta = package(b.segments, items)
    return {"stories": items, **meta}

@app.post("/v1/render")
def render_route(b: RenderRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    try:
        render(b.input_path, b.output_path, b.start, b.end, b.aspect, b.segments,
               b.captions, b.caption_style, b.focus_x)
        if not os.path.isfile(b.output_path) or os.path.getsize(b.output_path) < 1024:
            raise RuntimeError("Render output was not created or is invalid")
        return {"output_path": b.output_path, "size": os.path.getsize(b.output_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
