"""EP58 精簡版組裝"""
import json, subprocess, re, time, os
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent
TTS_DIR = OUT / "tts"
TTS_DIR.mkdir(exist_ok=True)
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CARD_RHYTHM = {"hook":3.0,"flip":5.0,"compare":7.0,"evidence":8.0,"reminder":6.0,"closing":4.0}

env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "yC4SQtHeGxfvfsrKVdz9")

SLIM = [
    {"id":1, "text":"午睡超過三十分鐘？小心越睡越傷身。"},
    {"id":2, "text":"四十四篇研究統合分析發現，超過三十分鐘，心血管和代謝風險增加。三十分鐘以內沒問題。"},
    {"id":3, "text":"時間點也重要。下午一到三點午睡最好，早上睡反而跟失智風險有關。"},
    {"id":4, "text":"二十分鐘就夠。專注力、記憶力、協調力都提升。"},
    {"id":5, "text":"三個秘訣。二十分鐘設鬧鐘。下午一到三點。常睡太久醒不來就看醫生。"},
    {"id":6, "text":"睡對了就是養生。時時靜好，下次見。"},
]

SCENES = [
    {"scene_id":"01","scene_role":"hook"},
    {"scene_id":"02","scene_role":"flip"},
    {"scene_id":"03","scene_role":"compare"},
    {"scene_id":"04","scene_role":"evidence"},
    {"scene_id":"05","scene_role":"reminder"},
    {"scene_id":"06","scene_role":"closing"},
]

def log(m): print(f"[ep58] {m}", flush=True)

def gen_tts(text, out):
    if out.exists() and out.stat().st_size > 1000: log(f"  TTS exists: {out.name}"); return
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({"text":text,"model_id":"eleven_v3","voice_settings":{"stability":0.35,"similarity_boost":0.85,"style":0.15,"use_speaker_boost":True,"speed":1.2}}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json","xi-api-key":ELEVENLABS_KEY}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp: out.write_bytes(resp.read()); log(f"  TTS OK: {out.name}")
    except Exception as e: log(f"  TTS ERROR: {e}")

def probe(p):
    r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",str(p)],capture_output=True,text=True,timeout=10)
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0

def to_ass(s):
    h=int(s//3600);m=int((s%3600)//60);sec=s%60
    return f"{h}:{m:02d}:{sec:05.2f}"

# Phase 5
log("=== Phase 5: TTS ===")
for seg in SLIM:
    sid = seg["id"]
    raw = TTS_DIR / f"seg_{sid:02d}_raw.mp3"
    final = TTS_DIR / f"seg_{sid:02d}.mp3"
    gen_tts(seg["text"], raw); time.sleep(0.5)
    if raw.exists() and raw.stat().st_size > 1000:
        subprocess.run(["ffmpeg","-y","-i",str(raw),"-af","atempo=1.1","-c:a","libmp3lame","-b:a","128k",str(final)],capture_output=True,timeout=15)
        log(f"  Accelerated: {final.name}")
    time.sleep(0.3)

# Phase 6
log("=== Phase 6: Assemble ===")
card_vids, audio_segs, all_subs = [], [], []
cum = 0.0

for i, sc in enumerate(SCENES):
    sid=sc["scene_id"]; role=sc["scene_role"]
    base=CARD_RHYTHM.get(role,5.0)
    tts=TTS_DIR/f"seg_{i+1:02d}.mp3"
    tts_dur=probe(tts) if tts.exists() else 0.0
    dur=max(base, tts_dur+0.3)
    log(f"Scene {sid} ({role}): {base}s rhythm, {tts_dur:.1f}s tts, {dur:.1f}s actual")

    card_img=OUT/f"card_{sid}.jpg"; card_vid=OUT/f"_cv_{sid}.mp4"
    subprocess.run(["ffmpeg","-y","-loop","1","-i",str(card_img),"-f","lavfi","-i","anullsrc=r=44100:cl=stereo","-t",str(dur),"-vf",
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v","libx264","-preset","medium","-crf","18","-c:a","aac","-b:a","128k","-ar","44100","-ac","2",
        "-r",str(FPS),"-pix_fmt","yuv420p","-shortest",str(card_vid)],capture_output=True,timeout=60)
    card_vids.append(card_vid)

    if tts.exists() and tts_dur>0:
        ao=OUT/f"_au_{sid}.m4a"
        subprocess.run(["ffmpeg","-y","-i",str(tts),"-af",f"aresample=44100,apad=whole_dur={dur}",
            "-ac","2","-ar","44100","-c:a","aac","-b:a","128k",str(ao)],capture_output=True,timeout=30)
        audio_segs.append(ao)
    else:
        sl=OUT/f"_sl_{sid}.m4a"
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=stereo",
            "-t",str(dur),"-c:a","aac","-b:a","128k",str(sl)],capture_output=True,timeout=10)
        audio_segs.append(sl)

    if i<len(SLIM):
        parts=re.split(r'[。，、；！？]+',SLIM[i]["text"])
        parts=[p.strip() for p in parts if p.strip()]
        tc=sum(len(p) for p in parts)
        t=cum
        for p in parts:
            d=tts_dur*(len(p)/tc) if tc else 0
            all_subs.append({"text":p,"start":round(t,2),"end":round(t+d,2)})
            t+=d
    cum+=dur

log("Concat...")
vl=OUT/"_vl.txt"; vl.write_text("\n".join(f"file '{v.name}'" for v in card_vids),encoding="utf-8")
cv=OUT/"_cv.mp4"
subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(vl),"-c","copy",str(cv)],capture_output=True,timeout=30)

al=OUT/"_al.txt"; al.write_text("\n".join(f"file '{a.name}'" for a in audio_segs),encoding="utf-8")
ca=OUT/"_ca.m4a"
subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(al),"-c","copy",str(ca)],capture_output=True,timeout=30)

mg=OUT/"_mg.mp4"
subprocess.run(["ffmpeg","-y","-i",str(cv),"-i",str(ca),"-map","0:v:0","-map","1:a:0",
    "-c:v","copy","-c:a","aac","-b:a","128k",str(mg)],capture_output=True,timeout=30)
total=probe(mg)
log(f"Total: {total:.1f}s")

log("Subtitles...")
ass_lines = [
    "[Script Info]", f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}", "ScriptType: v4.00+", "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
    "Alignment, MarginL, MarginR, MarginV, Encoding",
    "Style: Default,Microsoft JhengHei,82,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
    "1,0,0,0,100,100,2,0,1,5,1,2,20,20,280,1",
    "Style: Watermark,Microsoft JhengHei,22,&H80FFFFFF,&H000000FF,&H00000000,&H00000000,"
    "0,0,0,0,100,100,1,0,1,2,0,9,0,20,20,1",
    "", "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    f"Dialogue: 1,0:00:00.00,{to_ass(total)},Watermark,,0,0,0,,時時靜好",
]
for s in all_subs:
    ass_lines.append(f"Dialogue: 0,{to_ass(s['start'])},{to_ass(s['end'])},Default,,0,0,0,,{s['text']}")

af=OUT/"subs.ass"; af.write_text("\n".join(ass_lines),encoding="utf-8-sig")
ae=str(af).replace("\\","/").replace(":","\\:")

final=OUT/"ep58_nap_timing.mp4"
subprocess.run(["ffmpeg","-y","-i",str(mg),"-vf",f"ass='{ae}'",
    "-c:v","libx264","-preset","medium","-crf","18","-c:a","copy",str(final)],capture_output=True,timeout=120)

sz=final.stat().st_size/1024/1024
log(f"Done! {final} ({sz:.1f}MB, {total:.1f}s)")

for f in OUT.glob("_*"): f.unlink(missing_ok=True)
