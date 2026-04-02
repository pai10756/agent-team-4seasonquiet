"""EP57 每天8杯水的迷思 — 全自動管線（圖卡生成→TTS→組裝）

無需人工介入，一次跑完。
"""
import json, subprocess, base64, os, sys, time, re, io
import urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
TTS_DIR = OUT / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Load .env ──
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
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={GEMINI_KEY}"
WIDTH, HEIGHT, FPS = 1080, 1920, 30


def log(msg):
    print(f"[ep57] {msg}", file=sys.stderr, flush=True)


# ══════════════════════════════════════
# Episode Data
# ══════════════════════════════════════
EPISODE = {
    "series": "時時靜好｜健康新知",
    "episode": 57,
    "topic_id": 12,
    "type": "quick_cut",
    "topic_title": "每天要喝8杯水？這個說法根本沒有科學根據",

    "core_claim": "「每天8杯水」的說法沒有科學根據。2022年《Science》研究追蹤26國5604人，發現每日水分需求因人而異（1.5-4升），且約兩到四成來自食物。身體的口渴機制已經足夠精準，正常人跟著渴的感覺喝就對了。",
    "single_takeaway": "不用算杯數，渴了就喝，尿液淡黃色就表示喝夠了。",

    "scenes": [
        {
            "scene_id": "01",
            "scene_role": "hook",
            "visual_type": "poster_cover",
            "on_screen_text_main": "每天8杯水？",
            "on_screen_text_sub": "這個說法沒有科學根據",
            "hero_object": "一個透明玻璃杯裝滿清水，旁邊排列著8個小水杯，溫暖的木桌上，柔和自然晨光",
            "background_scene": "溫暖的廚房木桌場景，柔和晨光從窗戶灑入",
            "mascot_presence": True,
            "mascot_expression": "surprised",
            "mascot_pose": "think_with_object",
            "mascot_interaction_mode": "小靜站在水杯旁邊，一隻手摸下巴思考，表情驚訝疑惑",
            "badge_text": "2022\nScience 研究",
        },
        {
            "scene_id": "02",
            "scene_role": "flip",
            "visual_type": "comparison_card",
            "on_screen_text_main": "26國 5604人研究",
            "on_screen_text_sub": "每日需水量因人而異",
            "hero_object": "簡潔的資訊圖：左邊一個人形圖示標示「1.5升」，右邊一個人形圖示標示「4升」，中間一個雙向箭頭標示「因人而異」。下方標註「年齡、體重、氣候、活動量都會影響」",
            "source_badge_text": "Science 2022｜26國 5,604人追蹤研究",
        },
        {
            "scene_id": "03",
            "scene_role": "compare",
            "visual_type": "comparison_card",
            "on_screen_text_main": "兩到四成的水從食物來",
            "on_screen_text_sub": "水果蔬菜湯品都算",
            "hero_object": "左右對比：左邊一杯清水標示「直接喝水 60-80%」，右邊一盤水果蔬菜湯品標示「食物中的水分 20-40%」。簡潔圓餅圖或對比圖示",
            "source_badge_text": "Science 2022",
        },
        {
            "scene_id": "04",
            "scene_role": "evidence",
            "visual_type": "evidence_card",
            "on_screen_text_main": "渴了就喝就對了",
            "on_screen_text_sub": "身體的口渴機制比你想像的精準",
            "hero_object": "一個人的手拿起一杯水正要喝的真實攝影特寫，旁邊有一個簡潔的打勾圖示標示「口渴=該喝水了」。溫暖光線，Sony A7IV 淺景深風格",
        },
        {
            "scene_id": "05",
            "scene_role": "reminder",
            "visual_type": "safety_reminder",
            "on_screen_text_main": "三個喝水建議",
            "on_screen_text_sub": "簡單判斷喝夠沒",
            "hero_object": "真實攝影背景：溫暖木桌上一杯清水和幾顆水果。圖卡上列出三個建議：❶ 渴了就喝，不用算杯數 ❷ 尿液淡黃色就表示喝夠了 ❸ 運動流汗後多補充",
            "background_scene": "溫暖的生活場景，自然光",
        },
        {
            "scene_id": "06",
            "scene_role": "closing",
            "visual_type": "brand_closing",
            "on_screen_text_main": "時時靜好",
            "on_screen_text_sub": "我是小靜，我們下次見！",
            "background_scene": "柔和溫暖的廚房背景，木質桌面，一杯水在散景中",
            "mascot_presence": True,
            "mascot_expression": "goodbye",
            "mascot_pose": "greet_viewer",
            "mascot_interaction_mode": "小靜坐在一個大玻璃水杯旁邊，一隻手揮手道別，另一隻手抱著迷你水杯，表情溫暖開心",
        },
    ],

    "voiceover_segments": [
        {"id": 1, "text": "每天要喝八杯水？告訴你，這個說法根本沒有科學根據。"},
        {"id": 2, "text": "二零二二年 Science 期刊追蹤了二十六個國家五千多人，發現每日需水量因人而異，從一點五升到四升都有。"},
        {"id": 3, "text": "而且你每天喝的水，大約兩到四成是從食物來的。水果、蔬菜、湯，這些都算。"},
        {"id": 4, "text": "其實你的身體比你想的聰明。口渴機制非常精準，渴了就喝就對了。"},
        {"id": 5, "text": "三個建議。渴了就喝不用算杯數。尿液淡黃色就表示喝夠了。運動流汗後多補充。"},
        {"id": 6, "text": "別再算杯數了。時時靜好，我們下次見。"},
    ],

    "youtube_metadata": {
        "title": "每天8杯水是錯的？Science研究：渴了就喝才對｜時時靜好",
        "description": "每天要喝8杯水？這個說法根本沒有科學根據！\n\n❶ Science 2022研究（26國5604人）：每日需水量1.5-4升，因人而異\n❷ 約兩到四成水分來自食物（水果蔬菜湯品）\n❸ 口渴機制很精準，渴了就喝就對了\n\n三個喝水建議：\n• 渴了就喝，不用算杯數\n• 尿液淡黃色=喝夠了\n• 運動流汗後多補充\n\n#喝水 #8杯水 #迷思 #健康 #養生 #時時靜好 #Shorts",
    },
}


# ══════════════════════════════════════
# Phase 3: 圖卡生成（Gemini 全中文 prompt）
# ══════════════════════════════════════
def gen_card(name, prompt, ref_path=None):
    """Generate a single card image via Gemini API (urllib, timeout 300s)."""
    parts = [{"text": prompt}]
    if ref_path:
        from PIL import Image
        img = Image.open(ref_path)
        img = img.resize((800, 450), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        parts = [
            {"text": "小靜參考圖，必須完全一致："},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"text": prompt},
        ]

    payload = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()

    for attempt in range(3):
        try:
            start = time.time()
            req = urllib.request.Request(GEMINI_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
            elapsed = time.time() - start

            for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in p:
                    img_bytes = base64.b64decode(p["inlineData"]["data"])
                    if len(img_bytes) > 10000:
                        (OUT / f"{name}.jpg").write_bytes(img_bytes)
                        log(f"  OK {name} ({len(img_bytes):,} bytes, {elapsed:.0f}s)")
                        return True
            log(f"  {name} #{attempt+1}: no image ({elapsed:.0f}s)")
        except urllib.error.HTTPError as e:
            log(f"  {name} #{attempt+1}: HTTP {e.code} - {e.read().decode()[:60]}")
        except Exception as e:
            log(f"  {name} #{attempt+1}: {e}")
        time.sleep(20)
    log(f"  FAILED {name}")
    return False


STYLE = ("生成一張 1080x1920 的 9:16 直式圖卡。"
"背景儘量使用真實攝影照片填滿整張圖卡，搭配適度圖表插圖。"
"標題：大號粗體繁體中文，深橄欖色 #4E5538，畫面中最大最醒目。"
"副標題：較小字，棕色 #3B2A1F。"
"底部 20% 安全區不放文字但可有背景延伸，不刻意留白底色。"
"照片背景上文字加白色半透明陰影確保可讀。"
"乾淨現代風格。絕對不要任何英文文字、手機介面。")

MASCOT_DESC = ("台灣石虎 3D 磨砂塑膠玩具，大圓頭小身體，"
"黃棕色帶圓形深棕斑點，額頭兩條粗白線，粉紅三角鼻，"
"大圓深棕眼，鼠尾草綠圍裙胸前碗葉圖示，必須與參考圖一致。")

MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"


def generate_all_cards():
    log("=== Phase 3: 圖卡生成 ===")
    scenes = EPISODE["scenes"]

    card_prompts = {
        "01": (f"{STYLE} 背景：溫暖廚房木桌晨光場景，真實攝影填滿。"
               f"木桌上一個透明玻璃杯裝滿清水，旁邊排列著八個小水杯。"
               f"吉祥物小靜（{MASCOT_DESC}）站在水杯旁，一手摸下巴思考，表情驚訝。僅一隻，佔畫面 20%。"
               f"右上角徽章：「2022 Science 研究」鼠尾草綠圓角矩形。"
               f"標題：每天8杯水？ 副標題：這個說法沒有科學根據"),

        "02": (f"{STYLE} 簡潔資訊圖。"
               f"畫面中央：左邊人形圖示標「1.5升」，右邊人形圖示標「4升」，中間雙向箭頭標「因人而異」。"
               f"下方小字：「年齡、體重、氣候、活動量都會影響」。"
               f"來源標註：「Science 2022｜26國 5,604人」。"
               f"背景用淡淡的真實攝影水滴質感。"
               f"標題：26國 5604人研究 副標題：每日需水量因人而異。不要吉祥物。"),

        "03": (f"{STYLE} 左右對比圖。"
               f"左邊一杯清水標示「直接喝水 60-80%」。右邊一盤真實攝影的水果蔬菜湯品標示「食物中的水分 20-40%」。"
               f"用簡潔的圓餅圖或對比圖示呈現五五比例。"
               f"來源：Science 2022。"
               f"背景用真實攝影的水果蔬菜特寫，填滿整張。"
               f"標題：兩到四成的水從食物來 副標題：水果蔬菜湯品都算。不要吉祥物。"),

        "04": (f"{STYLE} 真實攝影背景填滿。"
               f"一隻手拿起一杯清水正要喝的特寫，Sony A7IV 50mm f/1.8 淺景深暖色調。"
               f"旁邊一個簡潔鼠尾草綠打勾圖示標示「口渴＝該喝水了」。"
               f"標題：渴了就喝就對了 副標題：身體的口渴機制比你想像的精準。不要吉祥物。"),

        "05": (f"{STYLE} 真實攝影背景：溫暖木桌上一杯清水和幾顆新鮮水果，Sony A7IV 淺景深。"
               f"圖卡上列出三個建議，每個前面圓形編號（鼠尾草綠底白字）：\n"
               f"❶ 渴了就喝，不用算杯數\n"
               f"❷ 尿液淡黃色＝喝夠了\n"
               f"❸ 運動流汗後多補充\n"
               f"文字加白色半透明底條確保可讀。"
               f"標題：三個喝水建議 副標題：簡單判斷喝夠沒。不要吉祥物。"),

        "06": (f"{STYLE} 柔和溫暖廚房背景，木桌散景中一杯水。"
               f"中央偏下：吉祥物小靜（{MASCOT_DESC}）坐在大玻璃水杯旁邊，"
               f"一隻手揮手道別，另一隻手抱著迷你水杯，表情溫暖微笑。僅一隻，佔畫面 50%。"
               f"標題：時時靜好 副標題：我是小靜，我們下次見！"),
    }

    for sid, prompt in card_prompts.items():
        log(f"Generating card_{sid}...")
        ref = MASCOT_REF if sid in ("01", "06") else None
        gen_card(f"card_{sid}", prompt, ref)
        time.sleep(12)


# ══════════════════════════════════════
# Phase 5: TTS 語音
# ══════════════════════════════════════
def generate_tts(text, out_path):
    if out_path.exists() and out_path.stat().st_size > 1000:
        log(f"  TTS exists: {out_path.name}")
        return True
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({
        "text": text, "model_id": "eleven_v3",
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.85, "style": 0.15,
                           "use_speaker_boost": True, "speed": 1.2},
    }).encode()
    req = urllib.request.Request(url, data=payload,
        headers={"Content-Type": "application/json", "xi-api-key": ELEVENLABS_KEY}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read())
            log(f"  TTS OK: {out_path.name}")
            return True
    except Exception as e:
        log(f"  TTS ERROR: {e}")
        return False


def probe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0


def generate_all_tts():
    log("=== Phase 5: TTS 語音 ===")
    for seg in EPISODE["voiceover_segments"]:
        sid = seg["id"]
        raw = TTS_DIR / f"seg_{sid:02d}_raw.mp3"
        final = TTS_DIR / f"seg_{sid:02d}.mp3"
        generate_tts(seg["text"], raw)
        time.sleep(0.5)
        if raw.exists() and raw.stat().st_size > 1000:
            subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-af", "atempo=1.1",
                           "-c:a", "libmp3lame", "-b:a", "128k", str(final)],
                          capture_output=True, timeout=15)
            log(f"  Accelerated: {final.name} (1.1x)")
        time.sleep(0.3)


# ══════════════════════════════════════
# Phase 6: 影片組裝
# ══════════════════════════════════════
CARD_RHYTHM = {"hook": 3.0, "flip": 5.0, "compare": 7.0, "evidence": 8.0, "reminder": 6.0, "closing": 4.0}


def to_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def auto_subtitles(narration, tts_dur, offset):
    parts = re.split(r'[。，、；！？]+', narration)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    total_chars = sum(len(p) for p in parts)
    if total_chars == 0:
        return []
    subs, t = [], offset
    for p in parts:
        dur = tts_dur * (len(p) / total_chars)
        subs.append({"text": p, "start": round(t, 2), "end": round(t + dur, 2)})
        t += dur
    return subs


def assemble():
    log("=== Phase 6: 影片組裝 ===")
    scenes = EPISODE["scenes"]
    segments = EPISODE["voiceover_segments"]

    card_videos, audio_segments, all_subs = [], [], []
    cum_time = 0.0

    for i, scene in enumerate(scenes):
        sid = scene["scene_id"]
        role = scene.get("scene_role", "")
        base_dur = CARD_RHYTHM.get(role, 5.0)

        tts_path = TTS_DIR / f"seg_{i+1:02d}.mp3"
        tts_dur = probe_duration(tts_path) if tts_path.exists() else 0.0
        card_dur = max(base_dur, tts_dur + 0.3)
        log(f"Scene {sid} ({role}): rhythm={base_dur}s, tts={tts_dur:.1f}s, actual={card_dur:.1f}s")

        # Card → video（禁止動畫，直接切）
        card_img = OUT / f"card_{sid}.jpg"
        card_vid = OUT / f"_card_{sid}.mp4"
        if card_img.exists():
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", str(card_img),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(card_dur),
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-r", str(FPS), "-pix_fmt", "yuv420p", "-shortest", str(card_vid),
            ], capture_output=True, timeout=60)
        card_videos.append(card_vid)

        # Audio normalize + pad
        if tts_path.exists() and tts_dur > 0:
            audio_out = OUT / f"_audio_{sid}.m4a"
            subprocess.run([
                "ffmpeg", "-y", "-i", str(tts_path),
                "-af", f"aresample=44100,apad=whole_dur={card_dur}",
                "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", str(audio_out),
            ], capture_output=True, timeout=30)
            audio_segments.append(audio_out)
        else:
            sil = OUT / f"_sil_{sid}.m4a"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                           "-t", str(card_dur), "-c:a", "aac", "-b:a", "128k", str(sil)],
                          capture_output=True, timeout=10)
            audio_segments.append(sil)

        # Subtitles
        if i < len(segments):
            subs = auto_subtitles(segments[i]["text"], tts_dur, cum_time)
            all_subs.extend(subs)
        cum_time += card_dur

    # Concat video
    log("Concat video...")
    vlist = OUT / "_vlist.txt"
    vlist.write_text("\n".join(f"file '{v.name}'" for v in card_videos), encoding="utf-8")
    concat_v = OUT / "_concat_v.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(concat_v)],
                  capture_output=True, timeout=30)

    # Concat audio
    log("Concat audio...")
    alist = OUT / "_alist.txt"
    alist.write_text("\n".join(f"file '{a.name}'" for a in audio_segments), encoding="utf-8")
    concat_a = OUT / "_concat_a.m4a"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(concat_a)],
                  capture_output=True, timeout=30)

    # Merge
    log("Merge video + audio...")
    merged = OUT / "_merged.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(concat_v), "-i", str(concat_a),
                   "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                   str(merged)], capture_output=True, timeout=30)

    total_dur = probe_duration(merged)
    log(f"Total duration: {total_dur:.1f}s")

    # ASS subtitles (FontSize 82, 黑框 5, MarginV 280)
    log("Burn subtitles...")
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
        f"Dialogue: 1,0:00:00.00,{to_ass_time(total_dur)},Watermark,,0,0,0,,時時靜好",
    ]
    for sub in all_subs:
        ass_lines.append(f"Dialogue: 0,{to_ass_time(sub['start'])},{to_ass_time(sub['end'])},Default,,0,0,0,,{sub['text']}")

    ass_file = OUT / "subs.ass"
    ass_file.write_text("\n".join(ass_lines), encoding="utf-8-sig")
    ass_escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")

    final = OUT / "ep57_water_myth.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(merged), "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", str(final),
    ], capture_output=True, timeout=120)

    final_size = final.stat().st_size / 1024 / 1024
    log(f"Done! {final} ({final_size:.1f}MB, {total_dur:.1f}s)")

    # Cleanup
    for f in OUT.glob("_*"):
        f.unlink(missing_ok=True)

    # Save episode JSON
    ep_json = OUT / "episode_ep57_water_myth.json"
    ep_json.write_text(json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Episode JSON: {ep_json}")


# ══════════════════════════════════════
# Main
# ══════════════════════════════════════
if __name__ == "__main__":
    if not GEMINI_KEY:
        log("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)
    if not ELEVENLABS_KEY:
        log("ERROR: ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    generate_all_cards()
    generate_all_tts()
    assemble()
