import sys, time
sys.path.insert(0, ".")
from ai.transcribe import decode_audio, model, transcribe

path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/smoke-source/bbb_trailer.mp4"
t0 = time.time()
audio = decode_audio(path)
print(f"[probe] decode_audio: {time.time()-t0:.1f}s samples={audio.shape}", flush=True)
t1 = time.time()
m = model()
print(f"[probe] model load: {time.time()-t1:.1f}s", flush=True)
t2 = time.time()
def timeout_cb():
    pass
result = transcribe(audio, timeout=None)
print(f"[probe] transcribe: {time.time()-t2:.1f}s segments={len(result['segments'])} duration={result['duration']}", flush=True)
