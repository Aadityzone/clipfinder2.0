from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from .schemas import TranscribeRequest,TranscribeResponse
from .transcribe import transcribe
from .services.download import download
from .services.media import ffprobe
from .services.render import render
from .highlights import candidates
from .longform import stories,package
from .services.media_intelligence import analyze_media
from .services.dedup import deduplicate
from .services.llm import score_candidates
import os,uuid
app=FastAPI(title="Clip Finder AI",version="2.0.0")
class IngestRequest(BaseModel): url:str; output_dir:str
class IngestResponse(BaseModel): media_path:str; metadata:dict
class ProbeRequest(BaseModel): media_path:str
class AnalyzeRequest(BaseModel): segments:list[dict]; instruction:str|None=None; categories:list[str]=[]; media_path:str|None=None
class AnalyzeResponse(BaseModel): candidates:list[dict]
class LongFormResponse(BaseModel): stories:list[dict]; title:str; description:str; chapters:list[dict]
class RenderRequest(BaseModel): input_path:str; output_path:str; start:float=0; end:float=0; aspect:str="9:16"; segments:list[dict]|None=None; captions:list[dict]|None=None; caption_style:dict|None=None
def auth(secret:str|None):
 expected=os.getenv("AI_SERVICE_SECRET")
 if expected and secret!=expected: raise HTTPException(status_code=401,detail="Invalid AI service credentials")
@app.get("/health")
def health(): return {"ok":True,"service":"ai","version":"2.0.0"}
@app.post("/v1/ingest",response_model=IngestResponse)
def ingest(b:IngestRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret)
 try:path=download(b.url,os.path.join(b.output_dir,uuid.uuid4().hex));return {"media_path":path,"metadata":ffprobe(path)}
 except Exception as e: raise HTTPException(status_code=500,detail=str(e))
@app.post("/v1/probe")
def probe(b:ProbeRequest,x_ai_secret:str|None=Header(default=None)):\n auth(x_ai_secret)\n if not os.path.isfile(b.media_path): raise HTTPException(status_code=404,detail="Media file not found")\n return ffprobe(b.media_path)\n@app.post("/v1/transcribe",response_model=TranscribeResponse)
def transcribe_route(b:TranscribeRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret)
 if not os.path.isfile(b.media_path): raise HTTPException(status_code=404,detail="Media file not found")
 try:return transcribe(b.media_path,b.language)
 except Exception as e: raise HTTPException(status_code=500,detail=str(e))
@app.post("/v1/analyze",response_model=AnalyzeResponse)
def analyze(b:AnalyzeRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret);media=analyze_media(b.media_path) if b.media_path else {}; result=candidates(b.segments,b.instruction,b.categories,media); result=deduplicate(result); result=score_candidates(result," ".join(str(s.get("text","")) for s in b.segments),b.instruction); return {"candidates":result}
@app.post("/v1/longform",response_model=LongFormResponse)
def longform(b:AnalyzeRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret);items=stories(b.segments);meta=package(b.segments,items);return {"stories":items,**meta}
@app.post("/v1/render")
def render_route(b:RenderRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret)
 try:render(b.input_path,b.output_path,b.start,b.end,b.aspect,b.segments,b.captions,b.caption_style);\n  if not os.path.isfile(b.output_path) or os.path.getsize(b.output_path)<1024: raise RuntimeError("Render output was not created or is invalid")\n  return {"output_path":b.output_path,"size":os.path.getsize(b.output_path)}
 except Exception as e:raise HTTPException(status_code=500,detail=str(e))
