from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .schemas import TranscribeRequest, TranscribeResponse
from .transcribe import transcribe
from .services.download import download
from .services.media import ffprobe
from .services.render import render
from .highlights import candidates
from .longform import stories, package
from .services.media_intelligence import analyze_media
from .services.dedup import deduplicate
from .services.llm import score_candidates
from .services.semantic import enrich_semantics
from .services.story_intelligence import optimize_candidates
from .services.speaker_intelligence import speaker_signals
from .services.diarization import diarize, diarization_status
from .services.visual_intelligence import semantic_frame_scores, visual_capabilities
from .services.action_intelligence import _classify_ocr
import os
import uuid
import importlib.util

app = FastAPI(title="Clip Finder AI", version="2.2.0")

class IngestRequest(BaseModel):
    url: str
    output_dir: str

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
    if expected and secret != expected:
        raise HTTPException(status_code=401, detail="Invalid AI service credentials")

@app.get("/health")
def health():
    return {"ok": True, "service": "ai", "version": "2.2.0"}

@app.post("/v1/ingest", response_model=IngestResponse)
def ingest(b: IngestRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    try:
        path = download(b.url, os.path.join(b.output_dir, uuid.uuid4().hex))
        return {"media_path": path, "metadata": ffprobe(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        return transcribe(b.media_path, b.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/ai-capabilities")
def ai_capabilities(x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    return {"diarization": diarization_status(), "semantic_embeddings": bool(os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2")), "visual": visual_capabilities(), "ocr": {"installed": importlib.util.find_spec("pytesseract") is not None, "requires_system_tesseract": True}}

@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(b: AnalyzeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    media = analyze_media(b.media_path) if b.media_path else {}
    if b.media_path and b.instruction and os.getenv("VISUAL_SEMANTIC_BACKEND", "").lower() == "clip":
        media["visualSemantic"] = semantic_frame_scores(b.media_path, b.instruction)
    result = candidates(b.segments, b.instruction, b.categories, media)
    result = enrich_semantics(result, b.instruction)
    result = optimize_candidates(b.segments, result)
    diarized = diarize(b.media_path, b.segments) if b.media_path else {"available": False, "segments": []}
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
    result = score_candidates(result, transcript, b.instruction)
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
    result = sorted(result, key=lambda x: float(x.get("score", 0)), reverse=True)
    return {"candidates": result[:50]}

@app.post("/v1/longform", response_model=LongFormResponse)
def longform(b: AnalyzeRequest, x_ai_secret: str | None = Header(default=None)):
    auth(x_ai_secret)
    items = stories(b.segments)
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
