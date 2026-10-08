import json, os
from urllib.request import Request, urlopen

def score_candidates(candidates:list[dict], transcript:str, instruction:str|None=None)->list[dict]:
    key=os.getenv("OPENAI_API_KEY")
    if not key or not candidates: return candidates
    base=os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
    model=os.getenv("OPENAI_MODEL","gpt-4o-mini")
    compact=[{"i":i,"start":c["start"],"end":c["end"],"text":c.get("text",""),"category":c.get("category")} for i,c in enumerate(candidates[:50])]
    prompt={"instruction":instruction or "Rank moments by genuine clip-worthiness.","candidates":compact}
    body=json.dumps({"model":model,"input":[{"role":"system","content":"Return JSON only: an array of objects with i, score (0-100), rationale. Do not invent candidates."},{"role":"user","content":json.dumps(prompt)}]}).encode()
    req=Request(base+"/responses",data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=45) as resp:data=json.loads(resp.read())
        raw=data.get("output_text","")
        ranked=json.loads(raw)
        by={int(x["i"]):x for x in ranked if isinstance(x,dict) and str(x.get("i","")).isdigit()}
        for i,c in enumerate(candidates):
            x=by.get(i)
            if x:
                llm=float(x.get("score",c["score"]))
                c["score"]=round(c["score"]*.55+max(0,min(100,llm))*.45,2)
                c["rationale"]=str(x.get("rationale") or c.get("rationale") or "")
                c.setdefault("features",{})["llmScore"]=llm
    except Exception:
        pass
    return candidates
