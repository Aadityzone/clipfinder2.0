import re
CUES={"funny":["laugh","hilarious","funny","joke"],"reaction":["oh my","what","no way","wait","wow"],"drama":["serious","never","can't believe","crazy"],"quotable":["the truth","remember","lesson","important"],"unexpected":["actually","turns out","didn't know","surprise"],"fail / win":["win","won","lost","fail","failed","victory"],"wholesome":["love","proud","thank","kind","family"]}
ALIASES={"ai detect":"ai_detect","fail / win":"fail / win"}

def score(text:str,start:float,end:float,instruction:str|None=None):
 t=text.lower();words=re.findall(r"[a-z0-9']+",t);duration=max(.1,end-start)
 density=min(1,len(words)/max(duration*2.2,1));punct=min(1,(text.count("!")+text.count("?"))/3)
 novelty=len(set(words))/max(len(words),1);cue=sum(1 for xs in CUES.values() for x in xs if x in t);cue=min(1,cue/3);custom=0
 if instruction:
  iw=re.findall(r"[a-z0-9']+",instruction.lower());custom=sum(1 for x in iw if x in set(words))/max(1,len(iw))
 return round(100*(.28*density+.18*punct+.18*novelty+.24*cue+.12*custom),2)

def candidates(segments,instruction=None,categories=None,media=None):
 allowed={ALIASES.get(str(c).lower(),str(c).lower()) for c in (categories or ["ai_detect"])}
 media=media or {};faces=media.get("vision",{}).get("faces",[]);scenes=media.get("scenes",{}).get("sceneChanges",[])
 out=[]
 for s in segments:
  start=max(0,float(s["start"])-3);end=float(s["end"])+5;text=str(s["text"]).strip()
  if len(text)<18:continue
  low=text.lower();sc=score(text,start,end,instruction)
  matches={k:sum(1 for x in xs if x in low) for k,xs in CUES.items()};best=max(matches,key=matches.get) if matches else "ai_detect"
  cat=best if matches.get(best,0)>0 else "ai_detect"
  if "ai_detect" not in allowed and cat not in allowed:
   ranked=[k for k,v in sorted(matches.items(),key=lambda z:z[1],reverse=True) if k in allowed and v>0]
   if not ranked:continue
   cat=ranked[0]
  if out and start<out[-1]["end"]:continue
  face_hits=sum(1 for f in faces if start<=float(f.get("time",-1))<=end)
  scene_hits=sum(1 for x in scenes if start<=float(x)<=end)
  sc=min(100,round(sc+min(8,face_hits*1.5)+min(5,scene_hits),2))
  out.append({"start":start,"end":end,"score":sc,"category":cat,"rationale":"Candidate scored from transcript signals with optional visual face/scene evidence.","features":{"wordCount":len(re.findall(r"[a-z0-9']+",text)),"categoryMatches":matches,"faceHits":face_hits,"sceneHits":scene_hits,"audio":media.get("audio",{})}})
 return sorted(out,key=lambda x:x["score"],reverse=True)[:50]
