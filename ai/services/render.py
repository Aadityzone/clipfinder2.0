import os,subprocess
def render(input_path:str,output_path:str,start:float,end:float,aspect:str="9:16"):
 os.makedirs(os.path.dirname(output_path),exist_ok=True);duration=max(0.01,end-start)
 vf={"9:16":"crop=ih*9/16:ih:(iw-ih*9/16)/2:0","1:1":"crop=ih:ih:(iw-ih)/2:0"}.get(aspect,"scale=iw:ih")
 subprocess.run(["ffmpeg","-y","-ss",str(start),"-i",input_path,"-t",str(duration),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-movflags","+faststart",output_path],check=True)