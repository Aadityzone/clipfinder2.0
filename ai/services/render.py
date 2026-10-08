import os,subprocess,tempfile\nfrom .captions import write_ass
def render(input_path:str,output_path:str,start:float=0,end:float|None=None,aspect:str="9:16",segments:list[dict]|None=None,captions:list[dict]|None=None,caption_style:dict|None=None):
 os.makedirs(os.path.dirname(output_path),exist_ok=True)
 segs=segments or [{"start":start,"end":end if end is not None else start+0.01}]
 vf={"9:16":"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","1:1":"scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080","16:9":"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"}.get(aspect,"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080")\n
 if len(segs)==1:
  s=segs[0];duration=max(.01,float(s["end"])-float(s["start"]))
  subprocess.run(["ffmpeg","-y","-ss",str(s["start"]),"-i",input_path,"-t",str(duration),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-movflags","+faststart",output_path],check=True);return
 with tempfile.TemporaryDirectory(prefix="clipfinder-render-") as d:
  parts=[]
  for i,s in enumerate(segs):
   p=os.path.join(d,f"part-{i}.mp4");duration=max(.01,float(s["end"])-float(s["start"]))
   subprocess.run(["ffmpeg","-y","-ss",str(s["start"]),"-i",input_path,"-t",str(duration),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-movflags","+faststart",p],check=True);parts.append(p)
  concat=os.path.join(d,"concat.txt")
  with open(concat,"w",encoding="utf-8") as f:
   for p in parts:f.write("file "+repr(p)+"\n")
  subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",concat,"-c","copy","-movflags","+faststart",output_path],check=True)
