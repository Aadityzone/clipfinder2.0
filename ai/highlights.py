import re
CUES={"funny":["laugh","hilarious","funny","joke"],"reaction":["oh my","what","no way","wait","wow"],"drama":["serious","never","can't believe","crazy"],"quotable":["the truth","remember","lesson","important"],"unexpected":["actually","turns out","didn't know","surprise"]}
def score(text:str,start:float,end:float,instruction:str|None=None):
 t=text.lower(); words=re.findall(r"[a-z0-9']+",t); duration=max(0.1,end-start); density=min(1,len(words)/max(duration*2.2,1)); punct=min(1,(text.count("!")+text.count("?"))/3)
 novelty=len(set(words))/max(len(words),1); cue=sum(1 for xs in CUES.values() for x in xs if x in t); cue=min(1,cue/3)
 custom=0
 if instruction:
  custom=sum(1 for x in re.findall(r"[a-z0-9']+",instruction.lower()) if x in set(words))/max(1,len(re.findall(r"[a-z0-9']+",instruction.lower())))
 return round(100*(.28*density+.18*punct+.18*novelty+.24*cue+.12*custom),2)
def candidates(segments,instruction=None):
 out=[]
 for s in segments:
  start=max(0,float(s["start"])-3);end=float(s["end"])+5;text=str(s["text"]).strip()
  if len(text)<18:continue
  sc=score(text,start,end,instruction);cat=max(CUES,key=lambda k:sum(1 for x in CUES[k] if x in text.lower())) if any(x in text.lower() for xs in CUES.values() for x in xs) else "ai_detect"
  if out and start<out[-1]["end"]:continue
  out.append({"start":start,"end":end,"score":sc,"category":cat,"rationale":"Transcript-derived candidate scored from density, punctuation, novelty, semantic cues, and custom instruction match.","features":{"wordCount":len(re.findall(r"[a-z0-9']+",text))}})
 return sorted(out,key=lambda x:x["score"],reverse=True)[:50]