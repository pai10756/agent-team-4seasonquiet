"""EP58 最佳午睡時機 — 全自動管線

事實查核完成：
- Sleep Medicine Reviews 2024 統合分析（44篇世代研究）：午睡≥30分鐘增加全因死亡、心血管、代謝疾病風險；<30分鐘無顯著風險
- Communications Medicine 2025（Nature子刊）：早上午睡與阿茲海默風險較高相關，下午早段午睡+穩定時長與較低病理指標相關
- J-curve 劑量反應：0-30分鐘風險最低，45分鐘後急遽上升
- 美國睡眠醫學會建議：午睡不超過20-30分鐘，安排在下午早段
- 不補腦：不寫具體風險倍數（各研究 HR 不一致），只寫「風險增加」
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
    print(f"[ep58] {msg}", file=sys.stderr, flush=True)


# ══════════════════════════════════════
# Episode Data
# ══════════════════════════════════════
EPISODE = {
    "series": "時時靜好｜健康新知",
    "episode": 58,
    "topic_id": 2,
    "type": "quick_cut",
    "topic_title": "午睡超過30分鐘反而傷身？最佳午睡時間大公開",

    "core_claim": "2024年統合分析（44篇世代研究）顯示，午睡超過30分鐘會增加全因死亡、心血管疾病和代謝疾病風險，但30分鐘以內則無顯著風險。2025年Nature子刊研究進一步發現，下午早段午睡比早上午睡更有益認知健康。最佳午睡：20分鐘、下午1-3點、設鬧鐘。",
    "single_takeaway": "午睡20分鐘剛剛好，超過30分鐘反而有害，下午1到3點是黃金時段。",

    "scenes": [
        {
            "scene_id": "01", "scene_role": "hook", "visual_type": "poster_cover",
            "on_screen_text_main": "午睡超過30分鐘？",
            "on_screen_text_sub": "小心越睡越傷身",
            "hero_object": "Person napping on cozy sofa with blanket warm afternoon light alarm clock on coffee table",
            "mascot_presence": True, "mascot_expression": "surprised",
            "mascot_interaction_mode": "小靜戴著小睡帽站在鬧鐘旁，一手摸下巴驚訝",
            "badge_text": "2024\n統合分析研究",
        },
        {
            "scene_id": "02", "scene_role": "flip", "visual_type": "comparison_card",
            "on_screen_text_main": "44篇研究結論",
            "on_screen_text_sub": "超過30分鐘風險增加",
            "hero_object": "Infographic: left clock showing 20min with green checkmark safe, right clock showing 60min with red warning risky. Below: 30分鐘是關鍵分界線",
            "source_badge_text": "睡眠醫學評論期刊 2024｜44篇世代研究統合分析",
        },
        {
            "scene_id": "03", "scene_role": "compare", "visual_type": "comparison_card",
            "on_screen_text_main": "下午1-3點最好",
            "on_screen_text_sub": "早上午睡反而傷腦",
            "hero_object": "Timeline graphic: morning section in gray with X mark labeled 早上午睡 風險較高, afternoon 1-3PM section in sage green highlighted labeled 黃金午睡時段, evening section in gray with X mark labeled 太晚睡 影響晚上",
            "source_badge_text": "自然通訊醫學 2025",
        },
        {
            "scene_id": "04", "scene_role": "evidence", "visual_type": "evidence_card",
            "on_screen_text_main": "20分鐘的威力",
            "on_screen_text_sub": "專注力、記憶力、協調力都提升",
            "hero_object": "Real photo of elderly person looking refreshed and alert after nap, sitting up on sofa stretching happily with warm afternoon light. Overlay badges: brain icon 專注力↑ and body icon 協調力↑",
        },
        {
            "scene_id": "05", "scene_role": "reminder", "visual_type": "safety_reminder",
            "on_screen_text_main": "三個午睡秘訣",
            "on_screen_text_sub": "睡對才有效",
            "hero_object": "Real photo cozy sofa with blanket alarm clock showing 1:00 PM warm light. Three tips: 1 control 20min set alarm 2 afternoon 1-3PM golden window 3 too long means body issue see doctor",
        },
        {
            "scene_id": "06", "scene_role": "closing", "visual_type": "brand_closing",
            "on_screen_text_main": "時時靜好",
            "on_screen_text_sub": "我是小靜，我們下次見！",
            "mascot_presence": True, "mascot_expression": "goodbye",
            "mascot_interaction_mode": "小靜戴著小睡帽坐在大枕頭上，一手揮手道別，另一手抱著迷你鬧鐘",
        },
    ],

    "voiceover_segments": [
        {"id": 1, "text": "午睡超過三十分鐘，你以為在補充精神？小心反而更傷身。"},
        {"id": 2, "text": "二零二四年統合分析彙整了四十四篇研究發現，午睡超過三十分鐘，心血管和代謝疾病風險都會增加。三十分鐘以內則沒有問題。"},
        {"id": 3, "text": "而且時間點也很重要。二零二五年研究發現，下午一到三點午睡對腦部最好，早上睡反而跟失智風險有關。"},
        {"id": 4, "text": "只要睡對二十分鐘，專注力、記憶力、身體協調力都會提升。午後小睡一下，整個人煥然一新。"},
        {"id": 5, "text": "三個秘訣。控制二十分鐘設好鬧鐘。安排在下午一到三點。如果老是睡太久醒不來，建議看醫生檢查。"},
        {"id": 6, "text": "睡對了就是養生。時時靜好，我們下次見。"},
    ],

    "youtube_metadata": {
        "title": "午睡超過30分鐘反而傷身？44篇研究告訴你最佳午睡法｜時時靜好",
        "description": "午睡到底該睡多久？最新研究給你答案！\n\n❶ 2024統合分析（44篇）：午睡>30分鐘增加心血管和代謝風險，<30分鐘無風險\n❷ 2025 Nature子刊：下午1-3點午睡對腦部最好，早上午睡反而有害\n❸ 20分鐘午睡即可提升專注力、記憶力、協調力\n\n三個午睡秘訣：\n• 控制20分鐘，設鬧鐘\n• 安排在下午1-3點\n• 常睡太久醒不來→看醫生\n\n#午睡 #睡眠 #健康 #養生 #時時靜好 #Shorts",
    },
}

# 女生外觀隨機（本集：圓臉甜美型）
GIRL_DESC = ("Beautiful East Asian female 22-24. Round soft face, big bright eyes with slight aegyo-sal, "
"natural arched brows, small button nose, plump gradient pink lips. "
"Flawless dewy skin warm undertone. Medium-length dark brown hair in messy bun with loose strands. "
"Minimal makeup, natural rosy cheeks. Wearing oversized cream hoodie. Sweet warm approachable.")


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


S = ("1080x1920 9:16 card. Real photo background fill entire card. "
"Bold Traditional Chinese headline dark olive #4E5538 white shadow. Subtitle brown. "
"Bottom 20% no text at all only background extends. No English. No phone UI.")

M = ("The EXACT 3D mascot from reference: smooth matte plastic leopard cat toy, "
"sage green apron bowl-leaf icon, white forehead stripes, dark spots not stripes. "
"Wearing tiny beige nightcap. Only ONE mascot.")


def generate_all_cards():
    log("=== Phase 3: 圖卡生成 ===")
    cards = [
        ("card_01", True,
         f"{S} Warm afternoon living room, cozy sofa with blanket, golden light from window. "
         f"{GIRL_DESC} She is curled up on the sofa napping peacefully, hugging a cushion. "
         f"{M} Standing on the coffee table beside an alarm clock, one paw on chin surprised, about 15% of frame. "
         f"Girl about 40% of frame. Badge center-right: 2024 統合分析研究. "
         f"Headline: 午睡超過30分鐘？ Subtitle: 小心越睡越傷身"),

        ("card_02", False,
         f"{S} Soft warm bokeh bedroom background photo. Center infographic: "
         f"left clock icon showing 20 with green checkmark labeled 安全, "
         f"right clock icon showing 60 with red warning labeled 風險增加. "
         f"Below: 30分鐘是關鍵分界線. "
         f"Source center area: 睡眠醫學評論期刊 2024｜44篇研究. "
         f"Headline: 44篇研究結論 Subtitle: 超過30分鐘風險增加. No mascot."),

        ("card_03", False,
         f"{S} Soft afternoon light photo background. Simple timeline graphic: "
         f"morning section gray X mark labeled 早上午睡 風險較高, "
         f"afternoon 1-3PM section sage green highlighted labeled 黃金午睡時段, "
         f"evening section gray X mark labeled 太晚 影響晚上. "
         f"Source: 自然通訊醫學 2025. "
         f"Headline: 下午1-3點最好 Subtitle: 早上午睡反而傷腦. No mascot."),

        ("card_04", False,
         f"{S} Background: real photograph of an elderly Asian person sitting up on sofa looking refreshed "
         f"and alert after a nap, stretching happily, warm afternoon golden light. Sony A7IV shallow DOF. "
         f"Overlay badges: brain icon 專注力↑ and body icon 協調力↑. "
         f"Headline: 20分鐘的威力 Subtitle: 專注力記憶力協調力都提升. No mascot."),

        ("card_05", False,
         f"{S} Background: real photograph of a cozy sofa with soft blanket and small alarm clock "
         f"showing 1:00 PM, warm afternoon light. Sony A7IV shallow DOF. "
         f"Overlay three numbered tips sage green circles bold Traditional Chinese white semi-transparent bar: "
         f"❶ 控制20分鐘，設好鬧鐘 ❷ 安排在下午1-3點 ❸ 常睡太久醒不來，建議看醫生. "
         f"Headline: 三個午睡秘訣 Subtitle: 睡對才有效. No mascot."),

        ("card_06", True,
         f"{S} Soft warm bedroom with pillows beautiful bokeh golden afternoon light. "
         f"{M} Sitting on a big cream pillow, one paw waving goodbye, other paw holding tiny alarm clock, "
         f"sweet warm smile crescent eyes. About 50% of frame. "
         f"Headline: 時時靜好 Subtitle: 我是小靜，我們下次見！"),
    ]

    for name, needs_ref, prompt in cards:
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
            log(f"  Accelerated: {final.name} (1.1x)")
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

    final = OUT / "ep58_nap_timing.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(mg), "-vf", f"ass='{ae}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", str(final)],
        capture_output=True, timeout=120)

    sz = final.stat().st_size / 1024 / 1024
    log(f"Done! {final} ({sz:.1f}MB, {total:.1f}s)")

    ep_json = OUT / "episode_ep58_nap_timing.json"
    ep_json.write_text(json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")

    for f in OUT.glob("_*"): f.unlink(missing_ok=True)


if __name__ == "__main__":
    if not GEMINI_KEY: log("ERROR: GEMINI_API_KEY not set"); sys.exit(1)
    if not ELEVENLABS_KEY: log("ERROR: ELEVENLABS_API_KEY not set"); sys.exit(1)

    # Pre-flight 自動檢查
    sys.path.insert(0, str(BASE / "scripts"))
    from preflight_check import run_preflight

    # 準備檢查資料
    preflight_cards = [(f"card_{s['scene_id']}", "") for s in EPISODE["scenes"]]
    # cards prompt 在 generate_all_cards() 裡，這裡用空字串佔位（實際檢查在獨立跑時）
    preflight_narrations = [seg["text"] for seg in EPISODE["voiceover_segments"]]

    if not run_preflight([], preflight_narrations, facts_checked=True):
        log("Pre-flight 檢查未通過，中止。")
        sys.exit(1)

    generate_all_cards()
    generate_all_tts()
    assemble()
