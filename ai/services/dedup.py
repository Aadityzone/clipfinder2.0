def _iou(a:dict,b:dict)->float:
    left=max(float(a["start"]),float(b["start"]));right=min(float(a["end"]),float(b["end"]))
    inter=max(0,right-left)
    union=max(float(a["end"]),float(b["end"]))-min(float(a["start"]),float(b["start"]))
    return inter/union if union else 0

def deduplicate(candidates:list[dict],threshold:float=.55)->list[dict]:
    kept=[]
    for c in sorted(candidates,key=lambda x:float(x.get("score",0)),reverse=True):
        if all(_iou(c,k)<threshold for k in kept):
            kept.append(c)
    return kept
