"""EP59 長輩防滑拖鞋怎麼挑 — 全自動管線

事實查核完成：
- Annals Geriatr Med 2024 綜合回顧：鞋底紋路、固定方式、鞋跟高度直接影響跌倒風險
- JAGS 2026 Cheever et al.：證據基礎鞋履建議，止滑、包覆、固定三大關鍵
- RCT 2025：PU/EVA 止滑鞋底顯著改善平衡，實驗期間零跌倒
- 70,196 件跌倒分析：穿開口式拖鞋顯著預測跌倒→住院
- 步態研究：無後跟拖鞋改變膝踝角度，增加絆倒風險
- 國健署 2017：台灣 65+ 每6人有1人跌倒，浴室佔室內跌傷 17%
- SR/SRA 認證僅適用工作安全鞋，市售家用拖鞋無此標示（不寫入圖卡）
- 「指甲刮鞋底」為民間經驗非研究建議（不寫入圖卡）
"""
import json, subprocess, base64, os, sys, time, re, io
import urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
TTS_DIR = OUT / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "yC4SQtHeGxfvfsrKVdz9")
GEMINI_MODELS = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"]
MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
WIDTH, HEIGHT, FPS = 1080, 1920, 30


def log(msg):
    print(f"[ep59] {msg}", file=sys.stderr, flush=True)


EPISODE = {
    "series": "時時靜好｜生活智慧",
    "episode": 59,
    "topic_title": "你家拖鞋安全嗎？四招挑對防滑拖鞋",

    "core_claim": "七萬多件長輩跌倒分析顯示，穿開口式拖鞋顯著增加跌倒住院風險。2024年綜合回顧與2026年美國老年醫學會建議指出，鞋底紋路、材質彈性、腳背包覆和後跟固定是預防跌倒的四大關鍵。台灣65歲以上每6人就有1人曾跌倒，浴室是室內第三大跌傷地點。",
    "single_takeaway": "買拖鞋翻過來看鞋底、用手按材質、確認包腳背、有後跟固定，四招就能大幅降低跌倒風險。",

    "scenes": [
        {"scene_id": "01", "scene_role": "hook", "visual_type": "poster_cover",
         "on_screen_text_main": "你家拖鞋安全嗎？",
         "on_screen_text_sub": "每6位長輩就有1位曾跌倒",
         "mascot_presence": True, "badge_text": "國健署統計"},
        {"scene_id": "02", "scene_role": "flip", "visual_type": "comparison_card",
         "on_screen_text_main": "這種拖鞋最危險",
         "on_screen_text_sub": "七萬件跌倒分析的結論",
         "source_badge_text": "老年醫學研究年報 2024｜70,196件跌倒分析"},
        {"scene_id": "03", "scene_role": "compare", "visual_type": "comparison_card",
         "on_screen_text_main": "鞋底翻過來比一比",
         "on_screen_text_sub": "紋路深淺差很多"},
        {"scene_id": "04", "scene_role": "evidence", "visual_type": "evidence_card",
         "on_screen_text_main": "四招挑對防滑拖鞋",
         "on_screen_text_sub": "在店裡就能自己檢查"},
        {"scene_id": "05", "scene_role": "reminder", "visual_type": "safety_reminder",
         "on_screen_text_main": "浴室安全三提醒",
         "on_screen_text_sub": "拖鞋只是第一步"},
        {"scene_id": "06", "scene_role": "closing", "visual_type": "brand_closing",
         "on_screen_text_main": "時時靜好",
         "on_screen_text_sub": "我是小靜，我們下次見！",
         "mascot_presence": True},
    ],

    "voiceover_segments": [
        {"id": 1, "text": "你家的拖鞋安全嗎？台灣每六位長輩就有一位曾經跌倒。"},
        {"id": 2, "text": "七萬多件跌倒分析發現，穿沒有後跟的開口拖鞋，跌倒住院風險明顯增加。夾腳拖和露趾涼拖最危險。"},
        {"id": 3, "text": "關鍵在鞋底。把拖鞋翻過來，有深紋路的才防滑。光滑的底遇水就像溜冰。"},
        {"id": 4, "text": "四招挑對。第一，鞋底有深紋路。第二，PU或橡膠底，按下去有彈性。第三，包覆腳背。第四，有後跟固定。"},
        {"id": 5, "text": "三個提醒。浴室地板保持乾燥。進出浴室一定穿防滑拖鞋。加裝扶手更安心。"},
        {"id": 6, "text": "一雙好拖鞋就是最簡單的防跌投資。時時靜好，下次見。"},
    ],

    "youtube_metadata": {
        "title": "你家拖鞋安全嗎？四招挑對防滑拖鞋｜7萬件跌倒分析｜時時靜好",
        "description": "台灣每6位長輩就有1位曾跌倒，浴室是第三大跌傷地點！\n\n❶ 70,196件跌倒分析：開口式拖鞋顯著增加跌倒住院風險\n❷ 2024綜合回顧+2026 JAGS建議：四大挑選標準\n❸ RCT實驗：PU/EVA止滑鞋底顯著改善平衡\n\n四招挑對防滑拖鞋：\n• 鞋底有深紋路\n• PU或橡膠底（按下去有彈性）\n• 包覆腳背\n• 有後跟固定\n\n#防滑拖鞋 #長輩安全 #防跌 #浴室安全 #時時靜好 #Shorts",
    },
}

# ══════════════════════════════════════
# 女生外觀隨機（本集：活潑短髮型）
# ══════════════════════════════════════
GIRL = ("East Asian female 23-25 short bob cut dark brown hair, round face, big eyes, "
"natural brows, small nose, rosy lips, dewy skin, wearing casual white t-shirt and denim shorts, "
"bright cheerful energetic.")

# 小靜服裝（居家主題→圍裙預設）
sys.path.insert(0, str(BASE / "scripts"))
from mascot_outfit import get_mascot_prompt
MASCOT = get_mascot_prompt(EPISODE["topic_title"], EPISODE["core_claim"])


# ══════════════════════════════════════
# Pre-flight
# ══════════════════════════════════════
from preflight_check import run_preflight

S = ("1080x1920 9:16 card. Real photo background fill entire card from top to bottom edge, "
"NO blur NO gradient NO white bar at bottom. Bold Traditional Chinese headline dark olive #4E5538 "
"white shadow. Subtitle brown. Bottom 20% no text only background photo continues sharp. "
"No English. No phone UI.")

CARDS = [
    ("card_01", True,
     f"{S} Warm bathroom entrance, real photo. {GIRL} Standing at bathroom door holding a pair of slippers, "
     f"looking at camera with curious questioning expression, 40% frame. "
     f"{MASCOT} Standing beside a pair of bathroom slippers on the floor, 15% frame. "
     f"Badge center-right: 國健署統計. "
     f"Headline: 你家拖鞋安全嗎？ Subtitle: 每6位長輩就有1位曾跌倒"),

    ("card_02", False,
     f"{S} Real photo comparison on wooden floor. Left side: a pair of cheap flip-flops and backless open slippers "
     f"with red X mark and label 危險. Right side: a pair of enclosed anti-slip bathroom slippers with deep sole "
     f"grooves and heel strap with green checkmark and label 安全. Clear side-by-side product comparison. "
     f"Source center area: 老年醫學研究年報 2024. "
     f"Headline: 這種拖鞋最危險 Subtitle: 七萬件跌倒分析的結論. No mascot."),

    ("card_03", False,
     f"{S} Real photo close-up of two slipper soles flipped upside down on white surface. "
     f"Left sole: completely smooth flat plastic sole, label 光滑底 with X. "
     f"Right sole: deep treaded grooves like tire tread pattern rubber sole, label 深紋路 with checkmark. "
     f"Clear visible texture difference. "
     f"Headline: 鞋底翻過來比一比 Subtitle: 紋路深淺差很多. No mascot."),

    ("card_04", False,
     f"{S} Real photo of a good anti-slip slipper on wooden surface with warm light Sony A7IV. "
     f"Four numbered callout badges pointing to different features of the slipper: "
     f"❶ 鞋底有深紋路 pointing to sole grooves, "
     f"❷ PU或橡膠底有彈性 pointing to sole material, "
     f"❸ 包覆腳背 pointing to closed upper, "
     f"❹ 有後跟固定 pointing to heel strap. "
     f"Headline: 四招挑對防滑拖鞋 Subtitle: 在店裡就能自己檢查. No mascot."),

    ("card_05", False,
     f"{S} Real photo of clean modern bathroom with non-slip mat, grab bar on wall, "
     f"and a pair of anti-slip slippers on dry floor. Sony A7IV warm light. "
     f"Three tips sage circles: ❶ 浴室地板保持乾燥 ❷ 進出浴室穿防滑拖鞋 ❸ 加裝扶手更安心. "
     f"Headline: 浴室安全三提醒 Subtitle: 拖鞋只是第一步. No mascot."),

    ("card_06", True,
     f"{S} Warm bathroom entrance soft bokeh golden light. "
     f"{MASCOT} Sitting on a large bathroom slipper, one paw waving goodbye, "
     f"other paw holding a tiny slipper, sweet smile crescent eyes, 50% frame. "
     f"Headline: 時時靜好 Subtitle: 我是小靜，我們下次見！"),
]

preflight_cards = [(name, prompt) for name, _, prompt in CARDS]
preflight_narrations = [seg["text"] for seg in EPISODE["voiceover_segments"]]


# ══════════════════════════════════════
# Phase 3: 圖卡生成
# ══════════════════════════════════════
def gen_card(name, prompt, ref_path=None):
    parts = [{"text": prompt}]
    if ref_path:
        from PIL import Image
        img = Image.open(ref_path).resize((800, 450), Image.LANCZOS)
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=80)
        parts = [
            {"text": "EXACT REFERENCE mascot:"},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"text": prompt},
        ]
    payload = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()

    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        for attempt in range(2):
            try:
                start = time.time()
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                elapsed = time.time() - start
                for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "inlineData" in p:
                        img_bytes = base64.b64decode(p["inlineData"]["data"])
                        if len(img_bytes) > 10000:
                            (OUT / f"{name}.jpg").write_bytes(img_bytes)
                            log(f"  OK {name} ({len(img_bytes)//1024}KB, {elapsed:.0f}s, {model})")
                            return True
                log(f"  {name} #{attempt+1}: no image ({elapsed:.0f}s, {model})")
            except urllib.error.HTTPError as e:
                log(f"  {name} #{attempt+1}: HTTP {e.code} ({model})")
                if e.code == 429: break
            except Exception as e:
                log(f"  {name} #{attempt+1}: {e} ({model})")
            time.sleep(20)
    log(f"  FAILED {name}")
    return False


def generate_all_cards():
    log("=== Phase 3: 圖卡生成 ===")
    for name, needs_ref, prompt in CARDS:
        log(f"Generating {name}...")
        ref = MASCOT_REF if needs_ref else None
        gen_card(name, prompt, ref)
        time.sleep(12)


# ══════════════════════════════════════
# Phase 5: TTS
# ══════════════════════════════════════
def generate_tts(text, out_path):
    if out_path.exists() and out_path.stat().st_size > 1000:
        log(f"  TTS exists: {out_path.name}"); return True
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({"text": text, "model_id": "eleven_v3",
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.85, "style": 0.15,
                           "use_speaker_boost": True, "speed": 1.2}}).encode()
    req = urllib.request.Request(url, data=payload,
        headers={"Content-Type": "application/json", "xi-api-key": ELEVENLABS_KEY}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read()); log(f"  TTS OK: {out_path.name}"); return True
    except Exception as e:
        log(f"  TTS ERROR: {e}"); return False

def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0

def generate_all_tts():
    log("=== Phase 5: TTS 語音 ===")
    for seg in EPISODE["voiceover_segments"]:
        sid = seg["id"]
        raw = TTS_DIR / f"seg_{sid:02d}_raw.mp3"; final = TTS_DIR / f"seg_{sid:02d}.mp3"
        generate_tts(seg["text"], raw); time.sleep(0.5)
        if raw.exists() and raw.stat().st_size > 1000:
            subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-af", "atempo=1.1",
                           "-c:a", "libmp3lame", "-b:a", "128k", str(final)], capture_output=True, timeout=15)
            log(f"  Accelerated: {final.name}")
        time.sleep(0.3)


# ══════════════════════════════════════
# Phase 6: 組裝
# ══════════════════════════════════════
CARD_RHYTHM = {"hook": 3.0, "flip": 5.0, "compare": 7.0, "evidence": 8.0, "reminder": 6.0, "closing": 4.0}

def to_ass_time(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"

def auto_subtitles(narration, tts_dur, offset):
    parts = re.split(r'[。，、；！？]+', narration)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts: return []
    tc = sum(len(p) for p in parts)
    if tc == 0: return []
    subs, t = [], offset
    for p in parts:
        d = tts_dur * (len(p) / tc)
        subs.append({"text": p, "start": round(t, 2), "end": round(t + d, 2)})
        t += d
    return subs

def assemble():
    log("=== Phase 6: 影片組裝 ===")
    segments = EPISODE["voiceover_segments"]
    card_vids, audio_segs, all_subs = [], [], []
    cum = 0.0

    for i, sc in enumerate(EPISODE["scenes"]):
        sid = sc["scene_id"]; role = sc.get("scene_role", "")
        base = CARD_RHYTHM.get(role, 5.0)
        tts = TTS_DIR / f"seg_{i+1:02d}.mp3"
        tts_dur = probe_duration(tts) if tts.exists() else 0.0
        dur = max(base, tts_dur + 0.3)
        log(f"Scene {sid} ({role}): rhythm={base}s, tts={tts_dur:.1f}s, actual={dur:.1f}s")

        card_img = OUT / f"card_{sid}.jpg"; card_vid = OUT / f"_cv_{sid}.mp4"
        if card_img.exists():
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(card_img), "-f", "lavfi", "-i",
                "anullsrc=r=44100:cl=stereo", "-t", str(dur), "-vf",
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "128k",
                "-ar", "44100", "-ac", "2", "-r", str(FPS), "-pix_fmt", "yuv420p", "-shortest",
                str(card_vid)], capture_output=True, timeout=60)
        card_vids.append(card_vid)

        if tts.exists() and tts_dur > 0:
            ao = OUT / f"_au_{sid}.m4a"
            subprocess.run(["ffmpeg", "-y", "-i", str(tts), "-af", f"aresample=44100,apad=whole_dur={dur}",
                "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", str(ao)], capture_output=True, timeout=30)
            audio_segs.append(ao)
        else:
            sl = OUT / f"_sl_{sid}.m4a"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(dur), "-c:a", "aac", "-b:a", "128k", str(sl)], capture_output=True, timeout=10)
            audio_segs.append(sl)

        if i < len(segments):
            subs = auto_subtitles(segments[i]["text"], tts_dur, cum)
            all_subs.extend(subs)
        cum += dur

    log("Concat...")
    vl = OUT / "_vl.txt"; vl.write_text("\n".join(f"file '{v.name}'" for v in card_vids), encoding="utf-8")
    cv = OUT / "_cv.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vl), "-c", "copy", str(cv)], capture_output=True, timeout=30)

    al = OUT / "_al.txt"; al.write_text("\n".join(f"file '{a.name}'" for a in audio_segs), encoding="utf-8")
    ca = OUT / "_ca.m4a"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(al), "-c", "copy", str(ca)], capture_output=True, timeout=30)

    mg = OUT / "_mg.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(cv), "-i", str(ca), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(mg)], capture_output=True, timeout=30)
    total = probe_duration(mg)
    log(f"Total: {total:.1f}s")

    log("Subtitles...")
    ass = [
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
        f"Dialogue: 1,0:00:00.00,{to_ass_time(total)},Watermark,,0,0,0,,時時靜好",
    ]
    for s in all_subs:
        ass.append(f"Dialogue: 0,{to_ass_time(s['start'])},{to_ass_time(s['end'])},Default,,0,0,0,,{s['text']}")

    af = OUT / "subs.ass"; af.write_text("\n".join(ass), encoding="utf-8-sig")
    ae = str(af).replace("\\", "/").replace(":", "\\:")

    final = OUT / "ep59_slipper_safety.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(mg), "-vf", f"ass='{ae}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", str(final)],
        capture_output=True, timeout=120)

    sz = final.stat().st_size / 1024 / 1024
    log(f"Done! {final} ({sz:.1f}MB, {total:.1f}s)")

    ep_json = OUT / "episode_ep59_slipper_safety.json"
    ep_json.write_text(json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")

    for f in OUT.glob("_*"): f.unlink(missing_ok=True)

    # Post-check
    from preflight_check import run_postcheck
    run_postcheck(OUT)


if __name__ == "__main__":
    if not GEMINI_KEY: log("ERROR: GEMINI_API_KEY not set"); sys.exit(1)
    if not ELEVENLABS_KEY: log("ERROR: ELEVENLABS_API_KEY not set"); sys.exit(1)

    # Pre-flight
    if not run_preflight(preflight_cards, preflight_narrations, facts_checked=True):
        log("Pre-flight 未通過，中止。"); sys.exit(1)

    generate_all_cards()
    generate_all_tts()
    assemble()
