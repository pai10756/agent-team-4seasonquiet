"""
EP52 低脂迷思 組裝腳本
TTS → 合成 MP4 → 字幕（白色字黑色描邊，略大，畫面下半部中間）
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = "ffmpeg"

# ── Config ──────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "r6qgCCGI7RWKXCagm158")

CARD_W, CARD_H = 1080, 1920
FPS = 30


def log(msg: str):
    print(f"[assemble] {msg}", file=sys.stderr)


# ── TTS ─────────────────────────────────────────────────
SPEED_FACTOR = 1.25


def generate_tts(text: str, output_path: Path) -> bool:
    if output_path.exists() and output_path.stat().st_size > 1000:
        log(f"  TTS cache hit: {output_path.name}")
        return True

    voice_id = ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.35, "similarity_boost": 0.85,
            "style": 0.15, "use_speaker_boost": True,
        },
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY},
        method="POST",
    )
    try:
        raw_path = output_path.with_suffix(".raw.mp3")
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            raw_path.write_bytes(audio_data)

        subprocess.run([
            FFMPEG, "-y", "-i", str(raw_path),
            "-filter:a", f"atempo={SPEED_FACTOR}",
            "-vn", str(output_path),
        ], capture_output=True, check=True)
        raw_path.unlink()
        log(f"  TTS OK: {output_path.name} ({output_path.stat().st_size / 1024:.0f}KB, {SPEED_FACTOR}x)")
        return True
    except Exception as e:
        log(f"  TTS error: {e}")
        return False


# ── Narration → subtitle segments ───────────────────────
def narration_to_subtitles(narration: str, audio_dur: float) -> list[dict]:
    parts = re.split(r'[。，、；！？]+', narration)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []

    total_chars = sum(len(p) for p in parts)
    if total_chars == 0:
        return []

    subs = []
    t = 0.0
    for p in parts:
        ratio = len(p) / total_chars
        seg_dur = audio_dur * ratio
        subs.append({
            "text": p,
            "start": round(t, 2),
            "end": round(t + seg_dur, 2),
        })
        t += seg_dur
    return subs


# ── Subtitle rendering (auto-wrap) ───────────────────────
MAX_CHARS_PER_LINE = 12  # ~12 Chinese chars fit 1080px at font_size=72


def wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE) -> str:
    if len(text) <= max_chars:
        return text
    mid = len(text) // 2
    # find nearest punctuation or space near middle
    best = mid
    for offset in range(0, mid):
        for pos in [mid + offset, mid - offset]:
            if 0 < pos < len(text):
                if text[pos] in '，、；！？。 ':
                    best = pos + 1
                    return text[:best].rstrip() + '\n' + text[best:].lstrip()
    # no punctuation found, just split at middle
    return text[:mid] + '\n' + text[mid:]


def render_subtitle_frame(text: str, width: int = CARD_W, font_size: int = 72) -> "numpy.ndarray":
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    text = wrap_text(text)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", font_size)
    except OSError:
        font = ImageFont.load_default()

    tmp = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_y = 16
    img = Image.new("RGBA", (width, th + pad_y * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    tx = (width - tw) // 2
    ty = pad_y
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255),
              stroke_width=4, stroke_fill=(0, 0, 0, 255),
              align="center")

    return np.array(img)


# ── Main Assembly ───────────────────────────────────────
def assemble():
    from moviepy import (
        ImageClip, AudioFileClip, CompositeVideoClip,
        concatenate_videoclips,
    )
    import numpy as np

    base_dir = Path(__file__).parent
    project_dir = base_dir.parent.parent
    config = json.loads((base_dir / "assembly_config.json").read_text(encoding="utf-8"))
    scenes = config["scenes"]

    tts_dir = base_dir / "tts"
    tts_dir.mkdir(exist_ok=True)
    output_path = base_dir / "ep52_full_fat_myth.mp4"

    # Step 1: Generate TTS
    log("=== Step 1: TTS Generation ===")
    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        if narration:
            tts_path = tts_dir / f"scene_{i + 1:02d}.mp3"
            generate_tts(narration, tts_path)
            time.sleep(0.3)

    # Step 2: Build scene clips
    log("=== Step 2: Building Scene Clips ===")
    scene_clips = []

    for i, scene in enumerate(scenes):
        sid = scene["scene_id"]
        img_path = project_dir / scene["image"]
        config_duration = scene["duration"]
        narration = scene.get("narration", "")

        if not img_path.exists():
            log(f"  ERROR: {img_path} not found")
            sys.exit(1)

        # Audio
        tts_path = tts_dir / f"scene_{i + 1:02d}.mp3"
        audio_clip = None
        audio_dur = 0
        if tts_path.exists():
            audio_clip = AudioFileClip(str(tts_path))
            audio_dur = audio_clip.duration

        padding = 0.5
        duration = max(config_duration, audio_dur + padding)
        log(f"  Scene {sid}: config={config_duration}s, audio={audio_dur:.1f}s -> {duration:.1f}s")

        base = ImageClip(str(img_path)).with_duration(duration).resized((CARD_W, CARD_H))

        # Subtitles
        subtitles = narration_to_subtitles(narration, audio_dur) if narration and audio_dur > 0 else []
        sub_clips = []
        for sub in subtitles:
            sub_dur = sub["end"] - sub["start"]
            if sub_dur <= 0:
                continue
            sub_frame = render_subtitle_frame(sub["text"])
            sub_h = sub_frame.shape[0]
            sub_clip = (
                ImageClip(sub_frame)
                .with_duration(sub_dur)
                .with_start(sub["start"])
                .with_position(("center", CARD_H - sub_h - 300))
            )
            sub_clips.append(sub_clip)

        all_clips = [base] + sub_clips
        scene_comp = CompositeVideoClip(all_clips, size=(CARD_W, CARD_H)).with_duration(duration)
        if audio_clip:
            scene_comp = scene_comp.with_audio(audio_clip)
        scene_clips.append(scene_comp)

    # Step 3: Concatenate
    log("=== Step 3: Concatenating ===")
    final = concatenate_videoclips(scene_clips, method="compose")
    log(f"  Total: {final.duration:.1f}s")

    # Step 4: Export
    log(f"=== Step 4: Exporting -> {output_path} ===")
    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="medium",
        threads=4,
        logger="bar",
    )
    log(f"Done! {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f}MB)")


if __name__ == "__main__":
    assemble()
