"""EP56 週末補眠 — 靜態圖卡組裝（管線 A 新規格）

依據 CLAUDE.md 管線 A 更新規格：
- TTS: ElevenLabs eleven_v3, voice yC4SQtHeGxfvfsrKVdz9, speed 1.2
- 卡片影片化: 時長 = max(原始節奏, TTS+0.3s), 僅 fade in/out, 禁止 zoompan
- 音訊: normalize 44100Hz/stereo → pad 到卡片時長 → concat（禁用 amix）
- 字幕: ASS FontSize 68, 白字黑框寬5, MarginV 280
- 輸出: 1080x1920, 30fps, H.264 CRF 18, AAC 128k
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
TTS_DIR = OUT / "tts_v2"
TTS_DIR.mkdir(exist_ok=True)

# ── Config ──
ELEVENLABS_API_KEY = os.environ.get(
    "ELEVENLABS_API_KEY",
    "79bb81ed336cd406cb273ed1b9917258d8d9ac1fd9717f01224d9a54da355a3d"
)
VOICE_ID = "yC4SQtHeGxfvfsrKVdz9"
WIDTH, HEIGHT, FPS = 1080, 1920, 30

# v3 卡片節奏模板
CARD_RHYTHM = {
    "hook": 3.0, "flip": 5.0, "compare": 7.0,
    "evidence": 8.0, "reminder": 6.0, "closing": 4.0,
}

EPISODE = json.loads(
    (BASE / "test_output" / "episode_ep56_weekend_sleep.json").read_text(encoding="utf-8")
)

# 精簡版旁白（原版66.9s，目標≤60s：砍字+atempo 1.1加速）
NARRATION_SLIM = {
    1: "週末多睡兩小時，你以為在補眠？研究說反而更傷。",
    2: "實驗發現，週末補眠的人，胰島素敏感度反而持續下降。補眠無法逆轉代謝損傷。",
    3: "還有社會時差效應。起床時間每差一小時，肥胖風險就增加百分之十一。",
    4: "與其週末賴床，不如每天提早二十分鐘上床。真的累，午睡二十分鐘就好。",
    5: "三個建議。每天多睡二十分鐘。起床時間差不超過一小時。累了午睡就好。",
    6: "好好睡，規律睡。時時靜好，我們下次見。",
}


def log(msg):
    print(f"[assemble_v2] {msg}", file=sys.stderr, flush=True)


# ── Phase 5: TTS ──
def generate_tts(text: str, out_path: Path) -> bool:
    if out_path.exists() and out_path.stat().st_size > 1000:
        log(f"  TTS exists: {out_path.name}")
        return True
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.35, "similarity_boost": 0.85,
            "style": 0.15, "use_speaker_boost": True, "speed": 1.2,
        }
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read())
            log(f"  TTS OK: {out_path.name} ({out_path.stat().st_size // 1024}KB)")
            return True
    except Exception as e:
        log(f"  TTS ERROR: {e}")
        return False


def probe_duration(path: Path) -> float:
    """用 ffprobe 測量音訊/影片實際秒數"""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=10
    )
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0


# ── Phase 6: 組裝 ──
def make_card_video(card_img: Path, duration: float, out_video: Path):
    """靜態圖 → mp4，禁止任何動畫/zoompan/fade，直接切換"""
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(card_img),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-vf", (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"
        ),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-r", str(FPS), "-pix_fmt", "yuv420p", "-shortest",
        str(out_video),
    ], capture_output=True, timeout=60)


def normalize_audio(tts_path: Path, duration: float, out_path: Path):
    """normalize 44100Hz/stereo → pad 到卡片時長"""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(tts_path),
        "-af", f"aresample=44100,apad=whole_dur={duration}",
        "-ac", "2", "-ar", "44100",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ], capture_output=True, timeout=30)


def build_ass(subtitles: list, total_duration: float) -> str:
    """ASS 字幕：FontSize 68, 白字黑框寬5, MarginV 280"""
    lines = [
        "[Script Info]",
        f"PlayResX: {WIDTH}",
        f"PlayResY: {HEIGHT}",
        "ScriptType: v4.00+",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        # 主字幕
        "Style: Default,Microsoft JhengHei,82,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,5,1,2,20,20,280,1",
        # 浮水印
        "Style: Watermark,Microsoft JhengHei,22,&H80FFFFFF,&H000000FF,"
        "&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,2,0,9,0,20,20,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    # 浮水印全程
    lines.append(f"Dialogue: 1,0:00:00.00,{to_ass_time(total_duration)},Watermark,,0,0,0,,時時靜好")
    # 字幕
    for sub in subtitles:
        lines.append(
            f"Dialogue: 0,{to_ass_time(sub['start'])},{to_ass_time(sub['end'])},"
            f"Default,,0,0,0,,{sub['text']}"
        )
    return "\n".join(lines)


def to_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def auto_subtitles(narration: str, tts_dur: float, offset: float) -> list:
    """根據旁白標點自動切字幕，時間按字數比例分配"""
    parts = re.split(r'[。，、；！？]+', narration)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    total_chars = sum(len(p) for p in parts)
    if total_chars == 0:
        return []
    subs = []
    t = offset
    for p in parts:
        ratio = len(p) / total_chars
        dur = tts_dur * ratio
        subs.append({"text": p, "start": round(t, 2), "end": round(t + dur, 2)})
        t += dur
    return subs


def main():
    scenes = EPISODE["scenes"]
    voiceover = EPISODE.get("voiceover", {})
    segments = voiceover.get("segments", [])

    # ── Phase 5: 生成 TTS（精簡版旁白 + atempo 1.1 加速）──
    log("=== Phase 5: TTS 語音 ===")
    for seg in segments:
        sid = seg['id']
        text = NARRATION_SLIM.get(sid, seg["text"])
        tts_raw = TTS_DIR / f"seg_{sid:02d}_raw.mp3"
        tts_path = TTS_DIR / f"seg_{sid:02d}.mp3"

        # Generate TTS with slim narration
        generate_tts(text, tts_raw)
        time.sleep(0.5)

        # ffmpeg atempo 1.1 加速 10%
        if tts_raw.exists() and tts_raw.stat().st_size > 1000:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(tts_raw),
                "-af", "atempo=1.1",
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(tts_path),
            ], capture_output=True, timeout=15)
            log(f"  Accelerated: {tts_path.name} (1.1x)")
        time.sleep(0.3)

    # ── Phase 6: 組裝 ──
    log("=== Phase 6: 影片組裝 ===")

    card_videos = []
    audio_segments = []
    all_subtitles = []
    cumulative_time = 0.0

    for i, scene in enumerate(scenes):
        sid = scene["scene_id"]
        role = scene.get("scene_role", "")
        base_dur = CARD_RHYTHM.get(role, 5.0)

        # TTS 時長
        tts_path = TTS_DIR / f"seg_{i + 1:02d}.mp3"
        tts_dur = probe_duration(tts_path) if tts_path.exists() else 0.0

        # 卡片時長 = max(原始節奏, TTS+0.3s)
        card_dur = max(base_dur, tts_dur + 0.3)
        log(f"Scene {sid} ({role}): rhythm={base_dur}s, tts={tts_dur:.1f}s, actual={card_dur:.1f}s")

        # 卡片影片化（僅 fade, 禁止 zoompan）
        card_img = OUT / f"card_{sid}.jpg"
        card_video = OUT / f"card_{sid}_v2.mp4"
        make_card_video(card_img, card_dur, card_video)
        card_videos.append(card_video)

        # 音訊 normalize + pad
        if tts_path.exists() and tts_dur > 0:
            audio_norm = OUT / f"audio_{sid}.m4a"
            normalize_audio(tts_path, card_dur, audio_norm)
            audio_segments.append(audio_norm)
        else:
            # 靜音段
            silence = OUT / f"silence_{sid}.m4a"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"anullsrc=r=44100:cl=stereo",
                "-t", str(card_dur), "-c:a", "aac", "-b:a", "128k",
                str(silence),
            ], capture_output=True, timeout=10)
            audio_segments.append(silence)

        # 字幕（根據 TTS probe 動態對齊，使用精簡版旁白）
        if i < len(segments):
            slim_text = NARRATION_SLIM.get(segments[i]["id"], segments[i]["text"])
            subs = auto_subtitles(slim_text, tts_dur, cumulative_time)
            all_subtitles.extend(subs)

        cumulative_time += card_dur

    # ── 影片 concat ──
    log("Concat video segments...")
    concat_list = OUT / "_concat_v.txt"
    concat_list.write_text(
        "\n".join(f"file '{v.name}'" for v in card_videos), encoding="utf-8"
    )
    concat_video = OUT / "_concat_v.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(concat_video),
    ], capture_output=True, timeout=30)

    # ── 音訊 concat（禁用 amix，會降音量）──
    log("Concat audio segments...")
    concat_alist = OUT / "_concat_a.txt"
    concat_alist.write_text(
        "\n".join(f"file '{a.name}'" for a in audio_segments), encoding="utf-8"
    )
    concat_audio = OUT / "_concat_a.m4a"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_alist), "-c", "copy", str(concat_audio),
    ], capture_output=True, timeout=30)

    # ── 合併影音 ──
    log("Merge video + audio...")
    merged = OUT / "_merged.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(concat_video), "-i", str(concat_audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        str(merged),
    ], capture_output=True, timeout=30)

    total_dur = probe_duration(merged)
    log(f"Total duration: {total_dur:.1f}s")

    # ── 字幕燒入 ──
    log("Burn subtitles...")
    ass_content = build_ass(all_subtitles, total_dur)
    ass_file = OUT / "subs_v2.ass"
    ass_file.write_text(ass_content, encoding="utf-8-sig")

    final = OUT / "ep56_weekend_sleep_v2.mp4"
    ass_escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(merged),
        "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",
        str(final),
    ], capture_output=True, timeout=120)

    final_size = final.stat().st_size / 1024 / 1024
    log(f"Done! {final} ({final_size:.1f}MB, {total_dur:.1f}s)")

    # Cleanup temp files
    for f in OUT.glob("_concat*"):
        f.unlink(missing_ok=True)
    for f in OUT.glob("_merged*"):
        f.unlink(missing_ok=True)
    for f in OUT.glob("card_*_v2.mp4"):
        f.unlink(missing_ok=True)
    for f in OUT.glob("audio_*.m4a"):
        f.unlink(missing_ok=True)
    for f in OUT.glob("silence_*.m4a"):
        f.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
