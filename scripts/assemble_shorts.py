"""
Shorts 組裝腳本 — 將手動生成的圖卡 + TTS 旁白 + 字幕合成為完整 MP4。

用法:
  python scripts/assemble_shorts.py --config <config_json> --output <output.mp4>

需要: ffmpeg, moviepy 2.x, Pillow, numpy
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ──────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get(
    "ELEVENLABS_API_KEY",
    "sk_852728a8c248dfe08f1a7fcb71183a893c019a2b499aa253"  # fallback
)
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "r6qgCCGI7RWKXCagm158")

CARD_W, CARD_H = 1080, 1920
FPS = 30


def log(msg: str):
    print(f"[assemble] {msg}", file=sys.stderr)


# ── TTS Generation ──────────────────────────────────────
def generate_tts(text: str, output_path: Path, voice_id: str = None) -> bool:
    """Generate TTS audio via ElevenLabs API."""
    if output_path.exists() and output_path.stat().st_size > 1000:
        log(f"  TTS exists: {output_path.name}")
        return True

    if not ELEVENLABS_API_KEY:
        log("Error: ELEVENLABS_API_KEY not set")
        return False

    voice_id = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.35, "similarity_boost": 0.85,
            "style": 0.15, "use_speaker_boost": True, "speed": 1.25,
        }
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            output_path.write_bytes(audio_data)
            log(f"  TTS: {output_path.name} ({len(audio_data) / 1024:.0f}KB)")
            return True
    except Exception as e:
        log(f"  TTS error: {e}")
        return False


# ── Narration to subtitles ──────────────────────────────
def narration_to_subtitles(narration: str, audio_dur: float) -> list[dict]:
    """Split narration into subtitle segments, evenly timed across audio duration.
    Strips phonetic hints like (ㄓㄨˇ) from display text.
    Splits on Chinese punctuation: 。，、；！？"""
    # Split by punctuation, keeping non-empty segments
    parts = re.split(r'[。，、；！？]+', narration)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []

    # Clean display text: remove phonetic hints, restore display-only substitutions
    tts_to_display = {"醫主": "醫囑"}
    def clean_for_display(t):
        t = re.sub(r'\([^)]*\)', '', t).strip()
        for k, v in tts_to_display.items():
            t = t.replace(k, v)
        return t
    clean_parts = [clean_for_display(p) for p in parts]

    # Distribute time evenly by character count
    total_chars = sum(len(p) for p in clean_parts)
    if total_chars == 0:
        return []

    subs = []
    t = 0.0
    for cp in clean_parts:
        ratio = len(cp) / total_chars
        seg_dur = audio_dur * ratio
        subs.append({
            "text": cp,
            "start": round(t, 2),
            "end": round(t + seg_dur, 2),
        })
        t += seg_dur

    return subs


# ── Subtitle rendering with Pillow ──────────────────────
def render_subtitle_frame(text: str, width: int = CARD_W, font_size: int = 52) -> "numpy.ndarray":
    """Render subtitle text as a transparent-background RGBA numpy array."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", font_size)
    except OSError:
        font = ImageFont.load_default()

    # Measure text
    tmp = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x, pad_y = 32, 16
    img_w = tw + pad_x * 2
    img_h = th + pad_y * 2

    img = Image.new("RGBA", (width, img_h + pad_y * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Semi-transparent background bar
    bar_left = (width - img_w) // 2
    bar_top = pad_y
    draw.rounded_rectangle(
        [bar_left, bar_top, bar_left + img_w, bar_top + img_h],
        radius=12, fill=(0, 0, 0, 160)
    )

    # Text with stroke
    tx = (width - tw) // 2
    ty = bar_top + pad_y
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255),
              stroke_width=2, stroke_fill=(0, 0, 0, 200))

    return np.array(img)


# ── Main Assembly ───────────────────────────────────────
def assemble_shorts(config: dict, output_path: Path):
    """Assemble complete Shorts video from config."""
    from moviepy import (
        ImageClip, AudioFileClip, CompositeVideoClip,
        CompositeAudioClip, concatenate_videoclips,
    )
    import numpy as np

    scenes = config["scenes"]
    bgm_path = config.get("bgm")
    bgm_volume = config.get("bgm_volume", 0.08)
    tts_dir = output_path.parent / "tts_narration"
    tts_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate all TTS narration
    log("=== Step 1: TTS Narration ===")
    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        if narration:
            tts_path = tts_dir / f"narration_{i + 1:02d}.mp3"
            generate_tts(narration, tts_path)
            time.sleep(0.3)

    # Step 2: Build each scene clip
    log("=== Step 2: Building Scene Clips ===")
    scene_clips = []

    for i, scene in enumerate(scenes):
        sid = scene["scene_id"]
        img_path = Path(scene["image"])
        config_duration = scene["duration"]
        narration = scene.get("narration", "")
        explicit_subs = scene.get("subtitles")

        if not img_path.exists():
            log(f"  ERROR: Image not found: {img_path}")
            sys.exit(1)

        # Audio — determine actual duration from narration length
        tts_path = tts_dir / f"narration_{i + 1:02d}.mp3"
        audio_clip = None
        audio_dur = 0
        if tts_path.exists():
            audio_clip = AudioFileClip(str(tts_path))
            audio_dur = audio_clip.duration

        # Scene duration = max(config, narration + padding) so audio never overflows
        padding = 0.5
        duration = max(config_duration, audio_dur + padding)
        log(f"Scene {sid}: config={config_duration}s, audio={audio_dur:.1f}s, actual={duration:.1f}s")

        # Static image clip (no zoom/pan)
        base = ImageClip(str(img_path)).with_duration(duration).resized((CARD_W, CARD_H))

        # Subtitles: use explicit if provided, otherwise auto-generate from narration
        if explicit_subs:
            subtitles = explicit_subs
        elif narration and audio_dur > 0:
            subtitles = narration_to_subtitles(narration, audio_dur)
            log(f"  Auto-subs: {len(subtitles)} segments")
        else:
            subtitles = []

        sub_clips = []
        for sub in subtitles:
            sub_text = sub["text"]
            sub_start = sub["start"]
            sub_end = sub["end"]
            sub_dur = sub_end - sub_start

            if sub_end > duration:
                sub_end = duration
                sub_dur = sub_end - sub_start
            if sub_dur <= 0:
                continue

            sub_frame = render_subtitle_frame(sub_text)
            sub_h = sub_frame.shape[0]

            sub_clip = (
                ImageClip(sub_frame)
                .with_duration(sub_dur)
                .with_start(sub_start)
                .with_position(("center", CARD_H - sub_h - 120))
            )
            sub_clips.append(sub_clip)

        # Composite scene
        all_clips = [base] + sub_clips
        scene_comp = CompositeVideoClip(all_clips, size=(CARD_W, CARD_H)).with_duration(duration)

        if audio_clip:
            scene_comp = scene_comp.with_audio(audio_clip)

        scene_clips.append(scene_comp)

    # Step 3: Concatenate all scenes
    log("=== Step 3: Concatenating ===")
    final = concatenate_videoclips(scene_clips, method="compose")
    total_dur = final.duration
    log(f"  Total duration: {total_dur:.1f}s")

    # Step 4: Mix BGM (very low volume, loop/trim to match video length)
    if bgm_path and Path(bgm_path).exists():
        log(f"=== Step 4: Mixing BGM (volume={bgm_volume}) ===")
        bgm = AudioFileClip(bgm_path)
        # Trim BGM to video length (BGM is longer, just cut it)
        if bgm.duration > total_dur:
            bgm = bgm.subclipped(0, total_dur)
        bgm = bgm.with_volume_scaled(bgm_volume)

        # Combine narration audio with BGM
        if final.audio:
            final = final.with_audio(CompositeAudioClip([final.audio, bgm]))
        else:
            final = final.with_audio(bgm)
    else:
        log("  No BGM configured or file not found, skipping")

    # Step 5: Export
    log(f"=== Step 5: Exporting to {output_path} ===")
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Assemble Shorts video")
    parser.add_argument("--config", "-c", required=True, help="Assembly config JSON")
    parser.add_argument("--output", "-o", required=True, help="Output MP4 path")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    assemble_shorts(config, output_path)


if __name__ == "__main__":
    main()
