from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from .schemas import TranscribeRequest,TranscribeResponse
from .transcribe import transcribe
from .services.download import download
from .services.media import ffprobe
from .highlights import candidates
import os,uuid
app=FastAPI(title="Clip Finder AI",version="2.0.0")
class IngestRequest(BaseModel): url:str; output_dir:str
class IngestResponse(BaseModel): media_path:str; metadata:dict
class AnalyzeRequest(BaseModel): segments:list[dict]; instruction:str|None=None
class AnalyzeResponse(BaseModel): candidates:list[dict]
def auth(secret:str|None):
 expected=os.getenv("AI_SERVICE_SECRET")
 if expected and secret!=expected: raise HTTPException(status_code=401,detail="Invalid AI service credentials")
@app.get("/health")
def health(): return {"ok":True,"service":"ai","version":"2.0.0"}
@app.post("/v1/ingest",response_model=IngestResponse)
def ingest(b:IngestRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret)
 try:
  path=download(b.url,os.path.join(b.output_dir,uuid.uuid4().hex));return {"media_path":path,"metadata":ffprobe(path)}
 except Exception as e: raise HTTPException(status_code=500,detail=str(e))
@app.post("/v1/transcribe",response_model=TranscribeResponse)
def transcribe_route(b:TranscribeRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret)
 if not os.path.isfile(b.media_path): raise HTTPException(status_code=404,detail="Media file not found")
 try:return transcribe(b.media_path,b.language)
 except Exception as e: raise HTTPException(status_code=500,detail=str(e))
@app.post("/v1/analyze",response_model=AnalyzeResponse)
def analyze(b:AnalyzeRequest,x_ai_secret:str|None=Header(default=None)):
 auth(x_ai_secret);return {"candidates":candidates(b.segments,b.instruction)}
