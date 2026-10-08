import os,subprocess,tempfile
def render(input_path:str,output_path:str,start:float=0,end:float|None=None,aspect:str="9:16",segments:list[dict]|None=None):
 os.makedirs(os.path.dirname(output_path),exist_ok=True)
 segs=segments or [{"start":start,"end":end if end is not None else start+0.01}]
 vf={"9:16":"crop=ih*9/16:ih:(iw-ih*9/16)/2:0","1:1":"crop=ih:ih:(iw-ih)/2:0","16:9":"scale=iw:ih"}.get(aspect,"scale=iw:ih")
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
