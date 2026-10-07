from faster_whisper import WhisperModel
import os
_model=None
def model():
    global _model
    if _model is None:
        device=os.getenv("WHISPER_DEVICE","auto")
        compute=os.getenv("WHISPER_COMPUTE_TYPE","int8")
        _model=WhisperModel(os.getenv("WHISPER_MODEL","small"),device=device,compute_type=compute)
    return _model
def transcribe(path:str,language:str|None=None):
    segments,info=model().transcribe(path,language=language,word_timestamps=True,vad_filter=True)
    out=[];text=[]
    for s in segments:
        words=[]
        for w in s.words or []:
            words.append({"start":float(w.start),"end":float(w.end),"word":w.word,"confidence":float(w.probability) if w.probability is not None else None})
        out.append({"start":float(s.start),"end":float(s.end),"text":s.text.strip(),"confidence":None,"words":words});text.append(s.text.strip())
    duration=float(getattr(info,"duration",0) or 0)
    return {"language":info.language,"text":" ".join(x for x in text if x),"segments":out,"duration":duration}