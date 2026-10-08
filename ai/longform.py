import re
def stories(segments,limit=6):
 out=[]
 if not segments:return out
 window=[];start=0
 for s in segments:
  text=str(s.get("text","")).strip()
  if not text:continue
  if not window:start=float(s["start"])
  window.append(s)
  if len(window)>=10 or float(s["end"])-start>=300:
   end=float(window[-1]["end"]);joined=" ".join(str(x["text"]).strip() for x in window);words=re.findall(r"[a-z0-9']+",joined.lower());score=min(100,round(35+len(set(words))/max(len(words),1)*35+min(30,len(words)/80*30),2));title=" ".join(joined.split()[:10]).strip(" .,!?:;")+"…";out.append({"start":start,"end":end,"score":score,"title":title,"rationale":"Long-form story candidate grouped from contiguous transcript context."});window=[]
 if window:
  end=float(window[-1]["end"]);joined=" ".join(str(x["text"]).strip() for x in window);words=re.findall(r"[a-z0-9']+",joined.lower());out.append({"start":start,"end":end,"score":round(min(100,35+len(set(words))/max(len(words),1)*35+min(30,len(words)/80*30)),2),"title":" ".join(joined.split()[:10]).strip(" .,!?:;")+"…","rationale":"Long-form story candidate from the final transcript context."})
 return sorted(out,key=lambda x:x["score"],reverse=True)[:limit]


def package(segments,stories_out):
    texts=[str(s.get("text","")).strip() for s in segments if str(s.get("text","")).strip()]
    joined=" ".join(texts)
    words=joined.split()
    title=" ".join(words[:12]).strip(" .,!?:;") or "Untitled long-form video"
    if len(title)>90:title=title[:87].rsplit(" ",1)[0]+"…"
    description=(joined[:500].strip()+"…") if len(joined)>500 else joined
    chapters=[{"start":float(s["start"]),"title":str(s.get("title") or "Highlight")} for s in stories_out]
    return {"title":title,"description":description,"chapters":chapters}
