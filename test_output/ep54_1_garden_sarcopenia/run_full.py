"""EP54-1 園藝治療長肌肉、抗肌少症 — 全自動管線

事實查核完成：
- QJM 2026 (DOI: 10.1093/qjmed/hcag094, PMID: 41904665)：12週園藝治療增加肌力肌肉量
- PLoS ONE 2022 系統性回顧：園藝治療改善長輩身體功能和心理健康
- 園藝活動 MET 3.5-5.0（British J Sports Med 2022）— EP54 已引用
- 不補腦具體肌力提升百分比（原文未公開完整數據）
"""
import json, subprocess, base64, os, sys, time, re, io
import urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
TTS_DIR = OUT / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
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
MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
WIDTH, HEIGHT, FPS = 1080, 1920, 30


def log(msg):
    print(f"[ep54-1] {msg}", file=sys.stderr, flush=True)


# ══════════════════════════════════════
# Episode Data
# ══════════════════════════════════════
EPISODE = {
    "series": "時時靜好｜健康新知",
    "episode": "54-1",
    "topic_id": 26,
    "type": "quick_cut",
    "topic_title": "種花種草也能長肌肉？園藝治療抗肌少症的新發現",

    "core_claim": "2026年QJM期刊研究發現，有肌少症風險的年長女性參與12週園藝治療課程後，肌肉力量和肌肉量都有顯著改善。園藝活動MET值3.5-5.0，屬於中等強度運動，挖土、搬盆、蹲站等動作天然包含阻力訓練元素，加上培育植物的成就感對心理健康有額外益處。",
    "single_takeaway": "種花種草不只是休閒，12週園藝治療就能有效增加肌力、對抗肌少症。",

    "scenes": [
        {
            "scene_id": "01", "scene_role": "hook", "visual_type": "poster_cover",
            "on_screen_text_main": "種花也能長肌肉？",
            "on_screen_text_sub": "園藝治療抗肌少症新發現",
            "hero_object": "Elderly woman's hands in garden gloves planting flowers in a terracotta pot, warm golden light, soil and green plants visible",
            "background_scene": "Warm community garden morning light, raised beds with flowers",
            "mascot_presence": True, "mascot_expression": "surprised", "mascot_pose": "think_with_object",
            "mascot_interaction_mode": "小靜站在花盆旁，一手摸下巴思考，表情驚訝",
            "badge_text": "2026\nQJM 研究",
        },
        {
            "scene_id": "02", "scene_role": "flip", "visual_type": "comparison_card",
            "on_screen_text_main": "12 週園藝治療",
            "on_screen_text_sub": "肌力和肌肉量顯著改善",
            "hero_object": "Clean infographic: left side shows a wilting plant icon labeled 肌少症風險, right side shows a blooming flower icon labeled 園藝治療12週 with upward arrow showing 肌力↑ 肌肉量↑. Below: 挖土搬盆蹲站=天然阻力訓練",
            "source_badge_text": "QJM 2026｜肌少症風險年長女性",
        },
        {
            "scene_id": "03", "scene_role": "compare", "visual_type": "comparison_card",
            "on_screen_text_main": "園藝 = 中等強度運動",
            "on_screen_text_sub": "MET 值 3.5-5.0，跟快走差不多",
            "hero_object": "Side by side comparison: left shows garden tools (shovel spade pruner) with MET 3.5-5.0, right shows walking shoes with MET 3.5-4.0, equals sign between them. Below: 挖土搬盆栽更到高強度",
            "source_badge_text": "Br J Sports Med 2022",
        },
        {
            "scene_id": "04", "scene_role": "evidence", "visual_type": "evidence_card",
            "on_screen_text_main": "身體和心理雙重效果",
            "on_screen_text_sub": "成就感是跑步機給不了的",
            "hero_object": "Split visual: top half shows strong arm muscle icon with 肌力提升, bottom half shows happy brain icon with 心理健康改善. Center highlight: 種出來的成就感 is unique benefit",
        },
        {
            "scene_id": "05", "scene_role": "reminder", "visual_type": "safety_reminder",
            "on_screen_text_main": "三個園藝養生建議",
            "on_screen_text_sub": "安全又有效的園藝運動",
            "hero_object": "Real photography background: warm wooden table with garden gloves small potted herbs and pruning shears. Three numbered tips overlaid: 1 every day 30 min gardening 2 squat with knees not waist 3 sunscreen and hydrate",
            "background_scene": "Warm garden scene natural light",
        },
        {
            "scene_id": "06", "scene_role": "closing", "visual_type": "brand_closing",
            "on_screen_text_main": "時時靜好",
            "on_screen_text_sub": "我是小靜，我們下次見！",
            "background_scene": "Warm garden scene with flower pots in soft bokeh",
            "mascot_presence": True, "mascot_expression": "goodbye", "mascot_pose": "greet_viewer",
            "mascot_interaction_mode": "小靜坐在大花盆上，一手揮手道別，另一手抱著小鏟子，表情溫暖開心",
        },
    ],

    "voiceover_segments": [
        {"id": 1, "text": "種花種草也能長肌肉？最新研究說，是真的。"},
        {"id": 2, "text": "二零二六年 QJM 期刊發現，有肌少症風險的長輩，參加十二週園藝治療後，肌力和肌肉量都明顯提升。"},
        {"id": 3, "text": "為什麼？因為園藝活動的運動強度跟快走差不多，挖土搬盆蹲站，天然就是阻力訓練。"},
        {"id": 4, "text": "而且園藝對心理健康也有幫助。種出東西的那種成就感，是跑步機給不了的。"},
        {"id": 5, "text": "三個建議。每天園藝三十分鐘。蹲下用膝蓋不要彎腰。記得防曬補水。"},
        {"id": 6, "text": "你家的花園就是最好的健身房。時時靜好，我們下次見。"},
    ],

    "youtube_metadata": {
        "title": "種花也能長肌肉？12週園藝治療抗肌少症｜QJM 2026最新研究｜時時靜好",
        "description": "種花種草不只是休閒，最新研究發現還能對抗肌少症！\n\n❶ QJM 2026研究：12週園藝治療顯著增加肌少症風險長輩的肌力和肌肉量\n❷ 園藝MET值3.5-5.0，等同快走的中等強度運動\n❸ 挖土搬盆蹲站＝天然阻力訓練，加上成就感的心理效益\n\n三個建議：\n• 每天園藝30分鐘\n• 蹲下用膝蓋、背打直\n• 記得防曬補水\n\n研究來源：\n• QJM 2026 (DOI: 10.1093/qjmed/hcag094)\n• Br J Sports Med 2022\n\n#園藝 #肌少症 #長輩運動 #健康 #養生 #時時靜好 #Shorts",
    },
}


# ══════════════════════════════════════
# Phase 3: 圖卡生成（英文 prompt 打 API）
# ══════════════════════════════════════
def gen_card(name, prompt, ref_path=None):
    parts = [{"text": prompt}]
    if ref_path:
        from PIL import Image
        img = Image.open(ref_path)
        img = img.resize((800, 450), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        parts = [
            {"text": "EXACT REFERENCE - replicate this mascot identically:"},
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
                        log(f"  OK {name} ({len(img_bytes)//1024}KB, {elapsed:.0f}s)")
                        return True
            log(f"  {name} #{attempt+1}: no image ({elapsed:.0f}s)")
        except urllib.error.HTTPError as e:
            log(f"  {name} #{attempt+1}: HTTP {e.code}")
        except Exception as e:
            log(f"  {name} #{attempt+1}: {e}")
        time.sleep(20)
    log(f"  FAILED {name}")
    return False


STYLE = ("Generate a 1080x1920 vertical 9:16 card. "
"Background: use real photography filling entire card with moderate infographic overlays. "
"Headline: large bold Traditional Chinese in dark olive #4E5538 with white text shadow. "
"Subtitle: smaller brown #3B2A1F. "
"Bottom 20% safety zone: no text but background photo extends, no blank white area. "
"All visible text must be Traditional Chinese. No English on the card. No phone UI elements.")

MASCOT_PROMPT = ("The EXACT 3D mascot from reference: smooth matte plastic leopard cat toy, "
"sage green apron with bowl-leaf icon, white forehead stripes, dark round spots not stripes, "
"big round dark brown eyes, pink triangle nose. Only ONE mascot.")


def generate_all_cards():
    log("=== Phase 3: 圖卡生成 ===")

    cards = [
        ("card_01", True,
         f"{STYLE} Background: warm community garden with golden morning light, real photography. "
         f"Elderly hands in garden gloves planting flowers in terracotta pot, soil and green plants. "
         f"{MASCOT_PROMPT} Standing beside pot, one paw on chin thinking, surprised expression, about 20% of frame. "
         f"Top-right badge sage green rounded rectangle: 2026 QJM 研究. "
         f"Headline: 種花也能長肌肉？ Subtitle: 園藝治療抗肌少症新發現"),

        ("card_02", False,
         f"{STYLE} Background: soft warm garden photo with bokeh greenery. "
         f"Center infographic: left side wilting plant icon in gray labeled 肌少症風險, "
         f"right side blooming flower icon in sage green labeled 園藝治療12週 with upward arrow 肌力↑ 肌肉量↑. "
         f"Below both: text 挖土搬盆蹲站＝天然阻力訓練. "
         f"Source badge in center area: QJM 2026｜肌少症風險年長女性. "
         f"Headline: 12週園藝治療 Subtitle: 肌力和肌肉量顯著改善. No mascot."),

        ("card_03", False,
         f"{STYLE} Background: real photo of garden tools on dark rich soil. "
         f"Center comparison: left side garden tools (shovel pruner gloves) with label MET 3.5-5.0, "
         f"right side walking shoes with label MET 3.5-4.0, equals sign between them. "
         f"Below: 挖土搬盆栽更到高強度. Source: Br J Sports Med 2022. "
         f"Headline: 園藝＝中等強度運動 Subtitle: MET值3.5-5.0，跟快走差不多. No mascot."),

        ("card_04", False,
         f"{STYLE} Background: real photo of blooming garden with colorful flowers in golden light. "
         f"Center split: top section strong arm muscle icon with 肌力提升 text, "
         f"bottom section happy smiling brain icon with 心理健康改善 text. "
         f"Highlight badge: 種出來的成就感 跑步機給不了. "
         f"Headline: 身體和心理雙重效果 Subtitle: 成就感是跑步機給不了的. No mascot."),

        ("card_05", False,
         f"{STYLE} Background: real photography warm wooden table with garden gloves, "
         f"small potted herbs, pruning shears, Sony A7IV 50mm f/1.8 shallow DOF warm tones. "
         f"Overlay three numbered tips with sage green circle numbers and bold Traditional Chinese, "
         f"white semi-transparent background bar for readability: "
         f"❶ 每天園藝 30 分鐘 ❷ 蹲下用膝蓋，不要彎腰 ❸ 記得防曬補水. "
         f"Headline: 三個園藝養生建議 Subtitle: 安全又有效的園藝運動. No mascot."),

        ("card_06", True,
         f"{STYLE} Background: soft warm garden with flower pots in beautiful bokeh, golden light. "
         f"{MASCOT_PROMPT} Sitting on a large terracotta flower pot, one paw waving goodbye, "
         f"other paw holding a tiny garden trowel, sweet warm smile crescent eyes. About 50% of frame. "
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
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
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
    scenes = EPISODE["scenes"]
    segments = EPISODE["voiceover_segments"]

    card_vids, audio_segs, all_subs = [], [], []
    cum = 0.0

    for i, sc in enumerate(scenes):
        sid = sc["scene_id"]; role = sc.get("scene_role", "")
        base = CARD_RHYTHM.get(role, 5.0)
        tts = TTS_DIR / f"seg_{i+1:02d}.mp3"
        tts_dur = probe_duration(tts) if tts.exists() else 0.0
        dur = max(base, tts_dur + 0.3)
        log(f"Scene {sid} ({role}): rhythm={base}s, tts={tts_dur:.1f}s, actual={dur:.1f}s")

        card_img = OUT / f"card_{sid}.jpg"
        card_vid = OUT / f"_cv_{sid}.mp4"
        if card_img.exists():
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", str(card_img),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(dur),
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-r", str(FPS), "-pix_fmt", "yuv420p", "-shortest", str(card_vid),
            ], capture_output=True, timeout=60)
        card_vids.append(card_vid)

        if tts.exists() and tts_dur > 0:
            ao = OUT / f"_au_{sid}.m4a"
            subprocess.run(["ffmpeg", "-y", "-i", str(tts), "-af", f"aresample=44100,apad=whole_dur={dur}",
                           "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", str(ao)],
                          capture_output=True, timeout=30)
            audio_segs.append(ao)
        else:
            sl = OUT / f"_sl_{sid}.m4a"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                           "-t", str(dur), "-c:a", "aac", "-b:a", "128k", str(sl)],
                          capture_output=True, timeout=10)
            audio_segs.append(sl)

        if i < len(segments):
            subs = auto_subtitles(segments[i]["text"], tts_dur, cum)
            all_subs.extend(subs)
        cum += dur

    # Concat
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

    # ASS
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

    af = OUT / "subs.ass"
    af.write_text("\n".join(ass), encoding="utf-8-sig")
    ae = str(af).replace("\\", "/").replace(":", "\\:")

    final = OUT / "ep54_1_garden_sarcopenia.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(mg), "-vf", f"ass='{ae}'",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", str(final)],
                  capture_output=True, timeout=120)

    sz = final.stat().st_size / 1024 / 1024
    log(f"Done! {final} ({sz:.1f}MB, {total:.1f}s)")

    # Save episode JSON
    ep_json = OUT / "episode_ep54_1.json"
    ep_json.write_text(json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cleanup
    for f in OUT.glob("_*"): f.unlink(missing_ok=True)


if __name__ == "__main__":
    if not GEMINI_KEY: log("ERROR: GEMINI_API_KEY not set"); sys.exit(1)
    if not ELEVENLABS_KEY: log("ERROR: ELEVENLABS_API_KEY not set"); sys.exit(1)
    generate_all_cards()
    generate_all_tts()
    assemble()
