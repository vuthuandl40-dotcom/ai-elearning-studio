from pathlib import Path

p = Path("/app/server.py")
s = p.read_text(encoding="utf-8")
old = 'cmd=["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=25,format=yuv420p","-c:v","libx264","-movflags","+faststart",str(out)]'
new = 'cmd=["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=15,format=yuv420p","-c:v","libx264","-preset","ultrafast","-crf","30","-threads","1","-movflags","+faststart",str(out)]'
if old not in s:
    raise SystemExit("Target ffmpeg command not found")
p.write_text(s.replace(old, new), encoding="utf-8")
print("Applied low-resource FFmpeg patch")
