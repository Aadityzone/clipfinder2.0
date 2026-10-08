import html

def ass_escape(text:str)->str:
    return html.escape(text).replace("\\","\\\\").replace("{","\\{").replace("}","\\}")

def write_ass(cues:list[dict],path:str,style:dict|None=None):
    style=style or {}
    font=style.get("font","Arial");size=int(style.get("size",48));color=style.get("color","&H00FFFFFF")
    with open(path,"w",encoding="utf-8") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n")
        f.write(f"Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n")
        f.write(f"Style: Default,{font},{size},{color},&H000000FF,&H00000000,&H80000000,1,0,1,3,1,2,60,60,90,1\n\n[Events]\n")
        f.write("Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
        for c in cues:
            def tm(x):
                x=max(0,float(x));h=int(x//3600);m=int((x%3600)//60);s=x%60
                return f"{h}:{m:02d}:{s:05.2f}"
            f.write(f"Dialogue: 0,{tm(c['start'])},{tm(c['end'])},Default,,0,0,0,,{ass_escape(str(c['text']))}\n")
