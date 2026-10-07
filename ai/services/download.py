import os,subprocess
def download(url:str,out_dir:str)->str:
    os.makedirs(out_dir,exist_ok=True);template=os.path.join(out_dir,"source.%(ext)s")
    subprocess.run(["yt-dlp","--no-playlist","-f","bv*+ba/b","--merge-output-format","mp4","-o",template,url],check=True)
    files=[os.path.join(out_dir,x) for x in os.listdir(out_dir) if x.startswith("source.")]
    if not files: raise RuntimeError("yt-dlp produced no media")
    return files[0]