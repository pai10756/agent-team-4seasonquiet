"""
EP13 抗發炎飲食 — 組裝最終影片
TTS 旁白 + 大白字黑邊框字幕 + 圖卡 slideshow

用法: python assemble_ep13.py
"""

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import imageio_ffmpeg
from PIL import Image

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(__file__).resolve().parents[2]
ASSET_DIR = Path(__file__).resolve().parent
EPISODE_PATH = BASE / "test_output" / "episode_ep13_anti_inflammatory.json"

WIDTH, HEIGHT = 1080, 1920
FPS = 24

# Load .env
for line in (BASE / ".env").read_text(encoding="utf-8").strip().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Card files mapping
CARD_FILES = {
    "01": "card_01_hook.jpg",
    "02": "card_02_flip.jpg",
    "03": "card_03_compare.jpg",
    "04": "card_04_evidence.jpg",
    "05": "card_05_reminder.jpg",
    "06": "card_06_closing.jpg",
}

CARD_RHYTHM = {
    "hook": 3.0,
    "flip": 5.0,
    "compare": 7.0,
    "evidence": 8.0,
    "reminder": 6.0,
    "closing": 4.0,
}


def log(msg):
    print(f"[assemble] {msg}", file=sys.stderr)


def run_ff(cmd, label=""):
    """Run ffmpeg command."""
    r = subprocess.run(cmd, capture_output=True, text=False)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", errors="replace")[-500:]
        log(f"  FFMPEG ERROR ({label}): {err}")
        return False
    return True


def to_ff(p: Path) -> str:
    """Convert Windows path for ffmpeg."""
    return str(p).replace("\\", "/")


def prepare_image(src: Path, dst: Path):
    """Resize/crop to 1080x1920."""
    img = Image.open(str(src)).convert("RGB")
    iw, ih = img.size
    target_ratio = WIDTH / HEIGHT

    img_ratio = iw / ih
    if img_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        img = img.crop((left, 0, left + new_w, ih))
    elif img_ratio < target_ratio:
        new_h = int(iw / target_ratio)
        top = (ih - new_h) // 2
        img = img.crop((0, top, iw, top + new_h))

    img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
    img.save(str(dst), quality=95)


def to_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(subtitles: list, total_duration: float) -> str:
    """Build ASS subtitle: large white text, black outline."""
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
        # 大白字、黑邊框 — FontSize 68, Outline 5, Bold
        # PrimaryColour=白 &H00FFFFFF, OutlineColour=黑 &H00000000
        # Alignment=2 (bottom center), MarginV=280 (above Shorts title area)
        "Style: Main,Microsoft JhengHei,68,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,5,2,2,40,40,280,1",
        # 數據強調樣式 — 稍大
        "Style: Data,Microsoft JhengHei,72,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,5,2,2,40,40,280,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for sub in subtitles:
        start = to_ass_time(sub["start"])
        end = to_ass_time(sub["end"])
        style = "Data" if sub.get("style") in ("data", "comparison") else "Main"
        lines.append(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{sub['text']}")

    return "\n".join(lines)


# ── TTS via ElevenLabs ──────────────────────────────────

def generate_tts(text: str, output_path: Path) -> bool:
    """Generate TTS via ElevenLabs with speed 1.2."""
    if not ELEVENLABS_API_KEY:
        log(f"  TTS: no API key, skipping")
        return False

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "yC4SQtHeGxfvfsrKVdz9")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    payload = json.dumps({
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.35,
            "similarity_boost": 0.85,
            "style": 0.15,
            "use_speaker_boost": True,
            "speed": 1.2
        }
    }).encode()

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "xi-api-key": ELEVENLABS_API_KEY,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio = resp.read()
            if len(audio) > 1000:
                output_path.write_bytes(audio)
                return True
    except Exception as e:
        log(f"  TTS error: {e}")

    return False


def probe_duration(path: Path) -> float:
    """Get audio duration in seconds via ffmpeg."""
    cmd = [
        FFMPEG, "-i", str(path),
        "-f", "null", "-"
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # Parse "time=00:00:05.23" from stderr
        import re
        matches = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if matches:
            h, m, s = matches[-1]
            return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0


# ── Main Assembly ───────────────────────────────────────

def main():
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    scenes = episode["scenes"]
    voiceover = episode.get("voiceover", {})
    vo_segments = voiceover.get("segments", [])
    subtitles = episode.get("subtitles", [])

    log(f"EP{episode['episode']} | {episode['topic_title']}")
    log(f"Cards: {len(scenes)}, VO segments: {len(vo_segments)}, Subtitles: {len(subtitles)}")

    with tempfile.TemporaryDirectory(prefix="ep13_assemble_") as tmpdir:
        tmp = Path(tmpdir)

        # ── Step 1: Generate TTS audio segments ──
        log("\n=== Step 1: TTS 旁白生成 ===")
        tts_dir = tmp / "tts"
        tts_dir.mkdir()
        tts_files = {}

        for seg in vo_segments:
            seg_id = seg["id"]
            tts_path = tts_dir / f"vo_{seg_id:02d}.mp3"
            log(f"  TTS [{seg_id}] {seg['part']}: {seg['text'][:20]}...")
            if generate_tts(seg["text"], tts_path):
                tts_files[seg["part"]] = tts_path
                log(f"    OK ({tts_path.stat().st_size / 1024:.0f}KB)")
            else:
                log(f"    FAILED")
            time.sleep(0.5)

        log(f"  TTS完成: {len(tts_files)}/{len(vo_segments)} segments")

        # ── Step 2: Build silent card video segments ──
        log("\n=== Step 2: 圖卡影片化（靜態無音訊） ===")
        card_videos = []
        cumulative_time = 0.0
        # Track start time of each scene role for TTS alignment
        role_start_times = {}

        for scene in scenes:
            sid = scene["scene_id"]
            role = scene["scene_role"]
            duration = CARD_RHYTHM.get(role, 5.0)
            role_start_times[role] = cumulative_time

            card_file = CARD_FILES.get(sid)
            if not card_file:
                log(f"  Card {sid}: no file mapping, skip")
                continue

            card_path = ASSET_DIR / card_file
            if not card_path.exists():
                log(f"  Card {sid}: {card_file} not found, skip")
                continue

            # Prepare image
            prepared = tmp / f"prep_{sid}.jpg"
            prepare_image(card_path, prepared)

            # Static — no animation, just fade in/out
            vf = (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fade=in:0:d=0.3,fade=out:st={duration - 0.3}:d=0.3"
            )

            card_video = tmp / f"card_{sid}.mp4"
            cmd = [
                FFMPEG, "-y",
                "-loop", "1", "-i", to_ff(prepared),
                "-t", str(duration),
                "-vf", vf,
                "-an",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
                "-pix_fmt", "yuv420p",
                to_ff(card_video),
            ]

            if run_ff(cmd, f"card {sid}"):
                card_videos.append(card_video)
                log(f"  Card {sid} ({role}, {duration}s): OK")
            else:
                log(f"  Card {sid}: FAILED")

            cumulative_time += duration

        log(f"  Total: {len(card_videos)} cards, {cumulative_time:.0f}s")

        # ── Step 3: Concat all cards into silent video ──
        log("\n=== Step 3: 接合影片 ===")
        concat_file = tmp / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{to_ff(v)}'" for v in card_videos),
            encoding="utf-8",
        )
        concat_out = tmp / "concat.mp4"
        run_ff([
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0",
            "-i", to_ff(concat_file),
            "-c", "copy",
            to_ff(concat_out),
        ], "concat")
        log("  接合完成")

        # ── Step 4: Probe TTS durations & rebuild card videos to match ──
        log("\n=== Step 4: 測量 TTS 時長，重建影片配合語音 ===")
        tts_order = []  # [(role, tts_path, duration)]
        for seg in vo_segments:
            role = seg["part"]
            tts_path = tts_files.get(role)
            if tts_path and tts_path.exists():
                dur = probe_duration(tts_path)
                tts_order.append((role, tts_path, dur))
                log(f"  TTS [{role}] {dur:.1f}s")

        if tts_order:
            # Rebuild card videos with TTS-matched durations
            log("\n  重建卡片影片（配合語音長度）...")
            card_videos_v2 = []
            actual_starts = {}  # role -> actual start time
            cursor = 0.0

            for role, tts_path, tts_dur in tts_order:
                # Find matching scene
                scene = next((s for s in scenes if s["scene_role"] == role), None)
                if not scene:
                    continue
                sid = scene["scene_id"]
                card_file = CARD_FILES.get(sid)
                if not card_file:
                    continue
                prepared = tmp / f"prep_{sid}.jpg"
                if not prepared.exists():
                    card_path = ASSET_DIR / card_file
                    if not card_path.exists():
                        continue
                    prepare_image(card_path, prepared)

                # Card duration = max(original rhythm, TTS duration + 0.3s buffer)
                orig_dur = CARD_RHYTHM.get(role, 5.0)
                card_dur = max(orig_dur, tts_dur + 0.3)
                actual_starts[role] = cursor

                vf = (
                    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                    f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"fade=in:0:d=0.3,fade=out:st={card_dur - 0.3}:d=0.3"
                )
                card_video = tmp / f"card_v2_{sid}.mp4"
                cmd = [
                    FFMPEG, "-y",
                    "-loop", "1", "-i", to_ff(prepared),
                    "-t", str(card_dur),
                    "-vf", vf,
                    "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
                    "-pix_fmt", "yuv420p",
                    to_ff(card_video),
                ]
                if run_ff(cmd, f"card_v2 {sid}"):
                    card_videos_v2.append(card_video)
                    log(f"    Card {sid} ({role}): {card_dur:.1f}s (TTS {tts_dur:.1f}s)")

                cursor += card_dur

            total_video_dur = cursor
            log(f"  影片總長: {total_video_dur:.1f}s")

            # Re-concat
            concat_file_v2 = tmp / "concat_v2.txt"
            concat_file_v2.write_text(
                "\n".join(f"file '{to_ff(v)}'" for v in card_videos_v2),
                encoding="utf-8",
            )
            concat_v2 = tmp / "concat_v2.mp4"
            run_ff([
                FFMPEG, "-y",
                "-f", "concat", "-safe", "0",
                "-i", to_ff(concat_file_v2),
                "-c", "copy",
                to_ff(concat_v2),
            ], "concat_v2")

            # Concatenate TTS audio files sequentially (no amix, preserves volume)
            log("\n  串接 TTS 音訊（concat，不降音量）...")
            tts_concat_file = tmp / "tts_concat.txt"
            tts_concat_file.write_text(
                "\n".join(f"file '{to_ff(tp)}'" for _, tp, _ in tts_order),
                encoding="utf-8",
            )
            tts_concat_audio = tmp / "tts_concat.wav"
            # Normalize all TTS to same format first, then concat
            normalized_tts = []
            for i, (role, tp, dur) in enumerate(tts_order):
                norm_path = tmp / f"tts_norm_{i}.wav"
                run_ff([
                    FFMPEG, "-y", "-i", to_ff(tp),
                    "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
                    to_ff(norm_path),
                ], f"normalize tts {role}")
                # Pad with silence to match card duration
                card_role_dur = None
                for cv_role, _, cv_dur in tts_order:
                    if cv_role == role:
                        scene = next((s for s in scenes if s["scene_role"] == role), None)
                        orig_dur = CARD_RHYTHM.get(role, 5.0)
                        card_role_dur = max(orig_dur, cv_dur + 0.3)
                        break
                if card_role_dur and card_role_dur > dur:
                    padded_path = tmp / f"tts_pad_{i}.wav"
                    run_ff([
                        FFMPEG, "-y", "-i", to_ff(norm_path),
                        "-af", f"apad=whole_dur={card_role_dur}",
                        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
                        to_ff(padded_path),
                    ], f"pad tts {role}")
                    normalized_tts.append(padded_path)
                else:
                    normalized_tts.append(norm_path)

            # Concat all padded TTS
            tts_list_file = tmp / "tts_list.txt"
            tts_list_file.write_text(
                "\n".join(f"file '{to_ff(p)}'" for p in normalized_tts),
                encoding="utf-8",
            )
            run_ff([
                FFMPEG, "-y",
                "-f", "concat", "-safe", "0",
                "-i", to_ff(tts_list_file),
                "-c", "copy",
                to_ff(tts_concat_audio),
            ], "concat TTS")

            # Merge video + audio
            mixed_out = tmp / "mixed.mp4"
            run_ff([
                FFMPEG, "-y",
                "-i", to_ff(concat_v2),
                "-i", to_ff(tts_concat_audio),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                to_ff(mixed_out),
            ], "merge audio+video")
            concat_out = mixed_out
            log("  音訊合併完成")
        else:
            total_video_dur = cumulative_time
            actual_starts = role_start_times
            log("  無 TTS，使用靜音影片")

        # ── Step 5: Build subtitles aligned to actual TTS timing ──
        log("\n=== Step 5: 字幕燒入（對齊語音） ===")

        # Rebuild subtitle timing based on actual TTS positions
        if tts_order:
            # Map each scene_role to its actual start and duration
            role_timing = {}
            for role, _, dur in tts_order:
                scene = next((s for s in scenes if s["scene_role"] == role), None)
                orig_dur = CARD_RHYTHM.get(role, 5.0)
                card_dur = max(orig_dur, dur + 0.3)
                role_timing[role] = {"start": actual_starts[role], "card_dur": card_dur, "tts_dur": dur}

            # Assign subtitles proportionally within each segment
            roles_in_order = ["hook", "flip", "compare", "evidence", "reminder", "closing"]
            # Group subtitles by their original time ranges to each role
            role_subs = {r: [] for r in roles_in_order}
            orig_boundaries = [0, 3, 8, 15, 23, 29, 33]
            for sub in subtitles:
                mid = (sub["start"] + sub["end"]) / 2
                for i, r in enumerate(roles_in_order):
                    if mid >= orig_boundaries[i] and mid < orig_boundaries[i + 1]:
                        role_subs[r].append(sub)
                        break

            new_subtitles = []
            for role in roles_in_order:
                if role not in role_timing:
                    continue
                rt = role_timing[role]
                subs = role_subs.get(role, [])
                if not subs:
                    continue
                # Distribute subtitles evenly across the TTS duration
                seg_start = rt["start"]
                seg_dur = rt["tts_dur"]
                n = len(subs)
                per_sub = seg_dur / n
                for j, sub in enumerate(subs):
                    new_subtitles.append({
                        "text": sub["text"],
                        "start": seg_start + j * per_sub,
                        "end": seg_start + (j + 1) * per_sub,
                        "style": sub.get("style", "main"),
                    })

            log(f"  字幕重新對齊: {len(new_subtitles)} 條")
        else:
            new_subtitles = subtitles

        ass_content = build_ass(new_subtitles, total_video_dur)
        ass_file = tmp / "subs.ass"
        ass_file.write_text(ass_content, encoding="utf-8-sig")
        ass_escaped = to_ff(ass_file).replace(":", "\\:")

        final_tmp = tmp / "ep13_anti_inflammatory_final.mp4"
        run_ff([
            FFMPEG, "-y",
            "-i", to_ff(concat_out),
            "-vf", f"ass='{ass_escaped}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-c:a", "copy",
            to_ff(final_tmp),
        ], "subtitle burn")

        # ── Copy to final output ──
        final_dir = ASSET_DIR / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / "ep13_anti_inflammatory.mp4"
        shutil.copy2(str(final_tmp), str(final_path))

        size_mb = final_path.stat().st_size / 1024 / 1024
        log(f"\n完成: {final_path} ({size_mb:.1f}MB, {cumulative_time:.0f}s)")
        print(f"Output: {final_path}")


if __name__ == "__main__":
    main()
