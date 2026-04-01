"""
影片組裝腳本 — assembler agent 使用。

v3: 支援 scenes[] 場景卡模式（固定節奏模板）及舊版 scene_images[] 相容。
根據 episode JSON + asset_paths 組裝最終影片。
支援 4 種型態：standard / ranking / hybrid / quick_cut。

用法:
  python scripts/assemble_episode.py <episode.json> --assets-dir <dir> [--output <path>]

v3 卡片節奏模板（~33s Shorts）:
  01 hook      0-3s    poster_cover
  02 flip      3-8s    comparison_card
  03 compare   8-15s   comparison_card
  04 evidence  15-23s  evidence_card
  05 reminder  23-29s  safety_reminder
  06 closing   29-33s  brand_closing

依賴:
  ffmpeg（透過 imageio-ffmpeg 或系統安裝）
  Pillow
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

WIDTH, HEIGHT = 1080, 1920  # v3: upgraded to 1080x1920
FPS = 24
TITLE_DURATION = 3.0
ENDCARD_DURATION = 4.0  # v3: closing card 29-33s = 4s

# v3 card rhythm template — scene_role → (duration, animation_type)
CARD_RHYTHM = {
    "hook": 3.0,       # 0-3s
    "flip": 5.0,       # 3-8s
    "compare": 7.0,    # 8-15s
    "evidence": 8.0,   # 15-23s
    "reminder": 6.0,   # 23-29s
    "closing": 4.0,    # 29-33s
}
DEFAULT_CARD_DURATION = 5.0

FONT_BOLD = "C:/Windows/Fonts/msjhbd.ttc"
FONT_REGULAR = "C:/Windows/Fonts/msjh.ttc"
WATERMARK_TEXT = "時時靜好"


def _prepare_image_for_video(img_path: Path, out_path: Path):
    """Resize/crop any image to exactly WIDTHxHEIGHT for video use."""
    img = Image.open(str(img_path)).convert("RGB")
    iw, ih = img.size
    target_ratio = WIDTH / HEIGHT  # 0.5625

    # Crop to target aspect ratio (center crop)
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
    img.save(str(out_path), quality=95)


def log(msg: str):
    print(f"[assembler] {msg}", file=sys.stderr)


def to_ffmpeg_path(p) -> str:
    return str(p).replace("\\", "/")


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def run_ffmpeg(cmd: list[str], step_name: str = ""):
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        log(f"  {step_name} 失敗:")
        log(result.stderr[-800:])
        sys.exit(1)
    return result


# ── 片頭標題卡 ──────────────────────────────────────────

def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """Break text into lines that fit within max_width."""
    if not text:
        return []
    # Try as single line first
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return [text]
    # Split by punctuation or midpoint
    mid = len(text) // 2
    # Try to split at punctuation near middle
    best_split = mid
    for i in range(mid - 3, mid + 4):
        if 0 < i < len(text) and text[i] in "，。、！？：；":
            best_split = i + 1
            break
    return [text[:best_split], text[best_split:]]


def _auto_font_size(text: str, font_path: str, max_width: int, max_size: int, draw) -> ImageFont.FreeTypeFont:
    """Find largest font size that fits text in max_width, with word wrap."""
    for size in range(max_size, 20, -4):
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            continue
        lines = _wrap_text(text, font, max_width, draw)
        fits = all(draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] <= max_width for line in lines)
        if fits:
            return font
    return ImageFont.truetype(font_path, 28)


def _draw_outlined_text(draw, text, font, color, outline_color, outline_width, y_center, max_width=None):
    max_width = max_width or (WIDTH - 60)
    lines = _wrap_text(text, font, max_width, draw)
    line_height = draw.textbbox((0, 0), "測", font=font)[3] + 8
    total_height = line_height * len(lines)
    y_start = int(y_center - total_height // 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (WIDTH - tw) // 2
        y = y_start + i * line_height
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            draw.text((x + dx * outline_width, y + dy * outline_width),
                      line, font=font, fill=outline_color)
        draw.text((x, y), line, font=font, fill=color)


def create_title_card(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """生成 3 秒片頭標題卡影片。"""
    ffmpeg_exe = get_ffmpeg_exe()
    title_card_cfg = episode.get("title_card", {})
    line1 = title_card_cfg.get("line1", episode.get("hook_text", ""))
    line2 = title_card_cfg.get("line2", episode.get("topic_title", ""))
    source_text = title_card_cfg.get("source_text", "")

    # 背景：v3 card_01 composed image，或 legacy scene_images，或純色
    bg_img = None
    # v3: try composed card image first
    card_01 = asset_dir / "card_01_composed.png"
    if card_01.exists():
        bg_img = Image.open(str(card_01)).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    else:
        for scene in episode.get("scene_images", []):
            p = asset_dir / f"scene_{scene['id']}.jpg"
            if p.exists():
                bg_img = Image.open(str(p)).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
                break

    if bg_img:
        bg_img = ImageEnhance.Brightness(bg_img).enhance(0.30)
        bg_img = ImageEnhance.Color(bg_img).enhance(0.4)
        overlay = Image.new("RGB", (WIDTH, HEIGHT), (30, 15, 5))
        bg_img = Image.blend(bg_img, overlay, 0.25)
    else:
        bg_img = Image.new("RGB", (WIDTH, HEIGHT), (20, 12, 8))

    draw = ImageDraw.Draw(bg_img)
    max_w = WIDTH - 80  # 左右留 40px padding

    try:
        font1 = _auto_font_size(line1, FONT_BOLD, max_w, 90, draw)
        font2 = _auto_font_size(line2, FONT_BOLD, max_w, 72, draw)
        font_src = ImageFont.truetype(FONT_REGULAR, 28)
    except OSError:
        font1 = ImageFont.load_default()
        font2 = font1
        font_src = font1

    _draw_outlined_text(draw, line1, font1,
                        color=(255, 200, 50), outline_color=(0, 0, 0),
                        outline_width=5, y_center=HEIGHT * 0.38, max_width=max_w)
    _draw_outlined_text(draw, line2, font2,
                        color=(255, 255, 255), outline_color=(0, 0, 0),
                        outline_width=4, y_center=HEIGHT * 0.54, max_width=max_w)
    if source_text:
        _draw_outlined_text(draw, source_text, font_src,
                            color=(180, 150, 100), outline_color=(0, 0, 0),
                            outline_width=2, y_center=HEIGHT * 0.68, max_width=max_w)

    img_path = out_dir / "title_card.png"
    bg_img.save(str(img_path), quality=95)

    # 封面圖
    cover_path = out_dir / "cover.png"
    bg_img.save(str(cover_path), quality=95)

    # 靜態圖 → 3s 影片
    video_path = out_dir / "title_card.mp4"
    run_ffmpeg([
        ffmpeg_exe, "-y",
        "-loop", "1", "-i", to_ffmpeg_path(img_path),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(TITLE_DURATION),
        "-vf", f"fade=in:0:d=0.5,fade=out:st={TITLE_DURATION - 0.5}:d=0.5",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "yuv420p", "-shortest",
        to_ffmpeg_path(video_path),
    ], "片頭影片")

    log(f"片頭: {video_path.name} ({TITLE_DURATION}s)")
    return video_path


# ── 片尾 ────────────────────────────────────────────────

def create_endcard(asset_dir: Path, out_dir: Path) -> Path | None:
    """mascot_endcard / mascot_closing → endcard 影片。"""
    # v3: mascot_closing.png; legacy: mascot_endcard.png
    endcard_img = asset_dir / "mascot_closing.png"
    if not endcard_img.exists():
        endcard_img = asset_dir / "mascot_endcard.png"
    if not endcard_img.exists():
        log("無片尾吉祥物，跳過")
        return None

    # Pre-process endcard to exact dimensions
    prepared = out_dir / "endcard_prepared.jpg"
    _prepare_image_for_video(endcard_img, prepared)

    ffmpeg_exe = get_ffmpeg_exe()
    video_path = out_dir / "endcard.mp4"
    run_ffmpeg([
        ffmpeg_exe, "-y",
        "-loop", "1", "-i", to_ffmpeg_path(prepared),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(ENDCARD_DURATION),
        "-vf", f"fade=in:0:d=0.3,fade=out:st={ENDCARD_DURATION - 0.3}:d=0.3",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "yuv420p", "-shortest",
        to_ffmpeg_path(video_path),
    ], "片尾影片")

    log(f"片尾: {video_path.name} ({ENDCARD_DURATION}s)")
    return video_path


# ── ASS 字幕 ────────────────────────────────────────────

def to_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(subtitles: list[dict], total_duration: float) -> str:
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
        # 浮水印
        "Style: Watermark,Microsoft JhengHei,22,&H80FFFFFF,&H000000FF,"
        "&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,2,0,9,0,20,20,1",
    ]

    # 字幕樣式
    for i, sub in enumerate(subtitles):
        size = sub.get("size", 48)
        margin_v = 220
        lines.append(
            f"Style: Sub{i},Microsoft JhengHei,{size},&HFFFFFF,&H000000FF,"
            f"&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,4,1,2,20,20,{margin_v},1"
        )

    lines += [
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    # 浮水印
    wm_start = to_ass_time(TITLE_DURATION)
    wm_end = to_ass_time(total_duration)
    lines.append(f"Dialogue: 1,{wm_start},{wm_end},Watermark,,0,0,0,,{WATERMARK_TEXT}")

    # 字幕
    for i, sub in enumerate(subtitles):
        start = to_ass_time(sub["start"])
        end = to_ass_time(sub["end"])
        lines.append(f"Dialogue: 0,{start},{end},Sub{i},,0,0,0,,{sub['text']}")

    return "\n".join(lines)


# ── Standard 組裝（片頭 + Part1 + Part2 + 片尾） ─────────

def assemble_standard(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """接合 title + seedance_part1 + seedance_part2 + endcard（舊版，含 TTS）。"""
    ffmpeg_exe = get_ffmpeg_exe()

    part1 = asset_dir / "seedance_part1.mp4"
    part2 = asset_dir / "seedance_part2.mp4"
    if not part1.exists() or not part2.exists():
        log(f"缺少 Seedance 影片: Part1={part1.exists()}, Part2={part2.exists()}")
        sys.exit(1)

    title_card = create_title_card(episode, asset_dir, out_dir)
    endcard = create_endcard(asset_dir, out_dir)

    segments = [title_card, part1, part2]
    if endcard:
        segments.append(endcard)

    return _concat_and_subtitle(episode, segments, out_dir, ffmpeg_exe, asset_dir)


def build_seedance_ass(subtitles: list[dict], total_duration: float) -> str:
    """Build ASS subtitle file for Seedance pipeline B.

    規格：白色字黑色描邊、字體略大、畫面下半部中間位置。
    不含浮水印（Seedance 影片自帶品牌收尾）。
    不含 TITLE_DURATION offset（無片頭卡）。
    """
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
        # 字幕樣式：白字黑描邊、粗體、字體略大(56)、下半部中間(Alignment=2, MarginV=280)
        "Style: SeedanceSub,Microsoft JhengHei,56,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,5,1,2,30,30,280,1",
    ]

    lines += [
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for sub in subtitles:
        start = to_ass_time(sub["start"])
        end = to_ass_time(sub["end"])
        lines.append(f"Dialogue: 0,{start},{end},SeedanceSub,,0,0,0,,{sub['text']}")

    return "\n".join(lines)


def assemble_seedance(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """Seedance 管線 B 組裝（EP09 成熟版）。

    只做 Part1 + Part2 concat → ASS 字幕燒入。
    不用 TTS（Seedance 內建配音），不用片頭/片尾卡。
    """
    ffmpeg_exe = get_ffmpeg_exe()

    part1 = asset_dir / "seedance_part1.mp4"
    part2 = asset_dir / "seedance_part2.mp4"
    if not part1.exists() or not part2.exists():
        log(f"缺少 Seedance 影片: Part1={part1.exists()}, Part2={part2.exists()}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="4sq_seedance_") as tmpdir:
        tmp = Path(tmpdir)

        # 統一格式
        normalized = []
        for i, seg in enumerate([part1, part2]):
            dst = tmp / f"seg_{i:02d}.mp4"
            shutil.copy2(str(seg), str(dst))
            norm = tmp / f"norm_{i:02d}.mp4"
            run_ffmpeg([
                ffmpeg_exe, "-y", "-i", to_ffmpeg_path(dst),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
                "-pix_fmt", "yuv420p",
                to_ffmpeg_path(norm),
            ], f"統一格式 Part{i + 1}")
            normalized.append(norm)

        # concat
        concat_file = tmp / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{to_ffmpeg_path(n)}'" for n in normalized),
            encoding="utf-8",
        )
        concat_out = tmp / "concat.mp4"
        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", to_ffmpeg_path(concat_file),
            "-c", "copy",
            to_ffmpeg_path(concat_out),
        ], "接合 Part1 + Part2")

        # 計算總時長
        from moviepy import VideoFileClip
        with VideoFileClip(str(concat_out)) as clip:
            total_duration = clip.duration
        log(f"接合完成: {total_duration:.1f}s")

        # ASS 字幕（白字黑描邊，畫面下半部中間，無 TTS offset）
        subtitles = episode.get("subtitles", [])
        ass_content = build_seedance_ass(subtitles, total_duration)
        ass_file = tmp / "subs.ass"
        ass_file.write_text(ass_content, encoding="utf-8-sig")
        ass_escaped = to_ffmpeg_path(ass_file).replace(":", "\\:")

        vf = f"ass='{ass_escaped}'"

        ep_num = episode.get("episode", 0)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_name = f"ep{ep_num:02d}_seedance_{ts}.mp4"
        final_tmp = tmp / final_name

        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-i", to_ffmpeg_path(concat_out),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-c:a", "copy",
            to_ffmpeg_path(final_tmp),
        ], "字幕燒入")

        final_dir = out_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / final_name
        shutil.copy2(str(final_tmp), str(final_path))

    size_mb = final_path.stat().st_size / 1024 / 1024
    log(f"完成: {final_path} ({size_mb:.1f}MB, {total_duration:.1f}s)")
    return final_path


# ── Ranking 組裝（片頭 + 圖卡 slideshow + TTS + 片尾） ──

def assemble_ranking(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """圖卡 xfade + TTS 語音 + 字幕。"""
    ffmpeg_exe = get_ffmpeg_exe()

    title_card = create_title_card(episode, asset_dir, out_dir)
    endcard = create_endcard(asset_dir, out_dir)

    # 排行榜卡圖 → 影片
    ranking_data = episode.get("ranking_data", [])
    card_videos = []

    for item in sorted(ranking_data, key=lambda x: x["rank"], reverse=True):
        rank = item["rank"]
        card_img = asset_dir / f"ranking_card_{rank}.jpg"
        if not card_img.exists():
            log(f"排行榜卡 #{rank} 不存在，跳過")
            continue

        card_duration = 4.0  # 每張卡 4 秒
        card_video = out_dir / f"card_{rank}.mp4"
        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", to_ffmpeg_path(card_img),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(card_duration),
            "-vf", f"fade=in:0:d=0.3,fade=out:st={card_duration - 0.3}:d=0.3",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "yuv420p", "-shortest",
            to_ffmpeg_path(card_video),
        ], f"卡片 #{rank}")
        card_videos.append(card_video)

    segments = [title_card] + card_videos
    if endcard:
        segments.append(endcard)

    return _concat_and_subtitle(episode, segments, out_dir, ffmpeg_exe, asset_dir)


# ── Quick Cut 組裝（片頭 + 靜態圖 slideshow + 片尾） ────

def assemble_quick_cut(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """靜態場景圖 slideshow + Ken Burns + 字幕。"""
    ffmpeg_exe = get_ffmpeg_exe()

    title_card = create_title_card(episode, asset_dir, out_dir)
    endcard = create_endcard(asset_dir, out_dir)

    scene_videos = []
    scenes = episode.get("scene_images", [])
    duration_per_scene = 30.0 / max(len(scenes), 1)
    total_frames = int(duration_per_scene * FPS)

    for scene in scenes:
        img_path = asset_dir / f"scene_{scene['id']}.jpg"
        if not img_path.exists():
            continue

        # Pre-process: crop/resize to exact 720x1280
        prepared = out_dir / f"prepared_{scene['id']}.jpg"
        _prepare_image_for_video(img_path, prepared)

        scene_video = out_dir / f"scene_{scene['id']}.mp4"
        # Simple scale + fade, no zoompan (zoompan causes black frames with non-square input)
        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", to_ffmpeg_path(prepared),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_per_scene),
            "-vf", (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fade=in:0:d=0.5,fade=out:st={duration_per_scene - 0.5}:d=0.5"
            ),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "yuv420p", "-shortest",
            to_ffmpeg_path(scene_video),
        ], f"場景 {scene['id']}")
        scene_videos.append(scene_video)

    segments = [title_card] + scene_videos
    if endcard:
        segments.append(endcard)

    return _concat_and_subtitle(episode, segments, out_dir, ffmpeg_exe, asset_dir)


# ── v3 場景卡模式 ──────────────────────────────────────

def assemble_card_scenes(episode: dict, asset_dir: Path, out_dir: Path) -> Path:
    """v3: 根據 scenes[] 組裝圖卡 slideshow，按固定節奏模板分配時長。"""
    ffmpeg_exe = get_ffmpeg_exe()
    scenes = episode.get("scenes", [])

    card_videos = []
    for scene in scenes:
        sid = scene.get("scene_id", "00")
        role = scene.get("scene_role", "")
        duration = CARD_RHYTHM.get(role, DEFAULT_CARD_DURATION)

        # Parse time_range if provided (e.g., "0-3s")
        time_range = scene.get("time_range", "")
        if time_range:
            import re as _re
            m = _re.match(r"(\d+)-(\d+)s?", time_range)
            if m:
                duration = float(m.group(2)) - float(m.group(1))

        # Find the composed card image (output of generate_assets.py stage 4)
        card_img = asset_dir / f"card_{sid}_composed.png"
        if not card_img.exists():
            card_img = asset_dir / f"card_{sid}.png"
        if not card_img.exists():
            card_img = asset_dir / f"scene_{sid}.jpg"
        if not card_img.exists():
            log(f"場景 {sid} 圖片不存在，跳過")
            continue

        # Pre-process to exact dimensions
        prepared = out_dir / f"prepared_{sid}.jpg"
        _prepare_image_for_video(card_img, prepared)

        # Animation filter based on scene spec
        animation = scene.get("animation", "slow_push_in")
        if animation == "slow_push_in":
            # Gentle 3% zoom over duration
            total_frames = int(duration * FPS)
            vf = (
                f"scale=1120:1984,zoompan=z='min(zoom+0.0003,1.03)'"
                f":x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
                f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
                f"fade=in:0:d=0.3,fade=out:st={duration - 0.3}:d=0.3"
            )
        elif animation == "slight_drift":
            total_frames = int(duration * FPS)
            vf = (
                f"scale=1120:1984,zoompan=z='1.02'"
                f":x='(iw-iw/zoom)/2+sin(on/{total_frames}*3.14)*20'"
                f":y='(ih-ih/zoom)/2'"
                f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
                f"fade=in:0:d=0.3,fade=out:st={duration - 0.3}:d=0.3"
            )
        else:
            # simple_cut / slide_in / none — just static with fade
            vf = (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fade=in:0:d=0.3,fade=out:st={duration - 0.3}:d=0.3"
            )

        card_video = out_dir / f"card_{sid}.mp4"
        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", to_ffmpeg_path(prepared),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "yuv420p", "-shortest",
            to_ffmpeg_path(card_video),
        ], f"場景卡 {sid} ({role}, {duration}s)")
        card_videos.append(card_video)

    if not card_videos:
        log("無場景卡可組裝")
        sys.exit(1)

    return _concat_and_subtitle(episode, card_videos, out_dir, ffmpeg_exe, asset_dir)


# ── 共用：接合 + 字幕 ───────────────────────────────────

def _concat_and_subtitle(episode: dict, segments: list[Path],
                         out_dir: Path, ffmpeg_exe: str,
                         asset_dir: Path = None) -> Path:
    """統一格式 → concat → 混入旁白 → 燒入字幕 → 輸出最終檔。"""

    with tempfile.TemporaryDirectory(prefix="4sq_assemble_") as tmpdir:
        tmp = Path(tmpdir)

        # 統一格式
        normalized = []
        for i, seg in enumerate(segments):
            dst = tmp / f"seg_{i:02d}.mp4"
            shutil.copy2(str(seg), str(dst))
            norm = tmp / f"norm_{i:02d}.mp4"
            run_ffmpeg([
                ffmpeg_exe, "-y", "-i", to_ffmpeg_path(dst),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-r", str(FPS), "-s", f"{WIDTH}x{HEIGHT}",
                "-pix_fmt", "yuv420p",
                to_ffmpeg_path(norm),
            ], f"統一格式 {i}")
            normalized.append(norm)

        # concat
        concat_file = tmp / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{to_ffmpeg_path(n)}'" for n in normalized),
            encoding="utf-8",
        )
        concat_out = tmp / "concat.mp4"
        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", to_ffmpeg_path(concat_file),
            "-c", "copy",
            to_ffmpeg_path(concat_out),
        ], "接合")

        # 計算總時長
        from moviepy import VideoFileClip
        with VideoFileClip(str(concat_out)) as clip:
            total_duration = clip.duration
        log(f"接合完成: {total_duration:.1f}s")

        # 字幕
        subtitles = episode.get("subtitles", [])
        for sub in subtitles:
            sub.setdefault("size", 48)

        ass_content = build_ass(subtitles, total_duration)
        ass_file = tmp / "subs.ass"
        ass_file.write_text(ass_content, encoding="utf-8-sig")
        ass_escaped = to_ffmpeg_path(ass_file).replace(":", "\\:")

        vf = f"ass='{ass_escaped}'"

        ep_num = episode.get("episode", 0)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_name = f"ep{ep_num:02d}_{ts}.mp4"
        final_tmp = tmp / final_name

        # 混入旁白音訊 — 逐句對齊字幕時間軸
        tts_manifest_path = None
        if asset_dir:
            mp = asset_dir / "tts_manifest.json"
            if mp.exists():
                tts_manifest_path = mp

        if tts_manifest_path:
            import json as _json
            tts_segments = _json.loads(tts_manifest_path.read_text(encoding="utf-8"))
            log(f"混入 {len(tts_segments)} 段 TTS 旁白...")

            # 用 ffmpeg 的 adelay 把每段 TTS 放到對應時間點
            inputs = ["-i", to_ffmpeg_path(concat_out)]
            filter_parts = []
            for idx, seg in enumerate(tts_segments):
                seg_path = Path(seg["path"])
                if not seg_path.exists():
                    continue
                inp_idx = len(inputs) // 2  # input index (0=video, 1..N=audio segments)
                inputs.extend(["-i", to_ffmpeg_path(seg_path)])
                # TITLE_DURATION offset: subtitles are timed from content start, but video has title card prepended
                delay_ms = int((seg["start"] + TITLE_DURATION) * 1000)
                filter_parts.append(f"[{inp_idx}:a]adelay={delay_ms}|{delay_ms},apad[a{idx}]")

            if filter_parts:
                # Mix all segments together
                mix_inputs = "".join(f"[a{i}]" for i in range(len(filter_parts)))
                filter_complex = ";".join(filter_parts) + \
                    f";[0:a]{mix_inputs}amix=inputs={len(filter_parts) + 1}:duration=first:dropout_transition=0[aout]"

                mixed_tmp = tmp / "mixed.mp4"
                cmd = [ffmpeg_exe, "-y"] + inputs + [
                    "-filter_complex", filter_complex,
                    "-map", "0:v", "-map", "[aout]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    to_ffmpeg_path(mixed_tmp),
                ]
                run_ffmpeg(cmd, "混入旁白")
                concat_out = mixed_tmp

        run_ffmpeg([
            ffmpeg_exe, "-y",
            "-i", to_ffmpeg_path(concat_out),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-c:a", "copy",
            to_ffmpeg_path(final_tmp),
        ], "字幕燒入")

        final_dir = out_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / final_name
        shutil.copy2(str(final_tmp), str(final_path))

    size_mb = final_path.stat().st_size / 1024 / 1024
    log(f"完成: {final_path} ({size_mb:.1f}MB, {total_duration:.1f}s)")
    return final_path


# ── 主流程 ──────────────────────────────────────────────

ASSEMBLERS = {
    "standard": assemble_seedance,     # EP09 成熟版：concat + ASS 字幕，無 TTS
    "hybrid": assemble_seedance,
    "ranking": assemble_ranking,
    "quick_cut": assemble_quick_cut,
}

# v3 assemblers: scenes[]-based card assembly
ASSEMBLERS_V3 = {
    "ranking": assemble_card_scenes,
    "quick_cut": assemble_card_scenes,
    "hybrid": assemble_card_scenes,    # card scenes for non-seedance part
    "standard": assemble_seedance,     # EP09 成熟版：concat + ASS 字幕，無 TTS
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="組裝最終影片")
    parser.add_argument("episode", help="episode JSON 路徑")
    parser.add_argument("--assets-dir", "-a", required=True, help="素材目錄")
    parser.add_argument("--output-dir", "-o", help="輸出目錄（預設素材目錄的 parent）")
    args = parser.parse_args()

    ep_path = Path(args.episode)
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    asset_dir = Path(args.assets_dir)

    # 檢查是否有 asset_manifest（可能記錄了降級資訊）
    manifest_path = asset_dir / "asset_manifest.json"
    actual_type = ep.get("type", "standard")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("type"):
            actual_type = manifest["type"]
            if actual_type != ep.get("type"):
                log(f"注意: 型態已從 {ep['type']} 降級為 {actual_type}")

    out_dir = Path(args.output_dir) if args.output_dir else asset_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # v3 auto-detect: if episode has scenes[] field, use card-based assembly
    is_v3 = bool(ep.get("scenes"))
    if is_v3:
        assembler = ASSEMBLERS_V3.get(actual_type)
        log(f"v3 模式: 使用 scenes[] 場景卡組裝")
    else:
        assembler = ASSEMBLERS.get(actual_type)
        log(f"Legacy 模式: 使用 scene_images[] 組裝")

    if not assembler:
        log(f"未知型態: {actual_type}")
        sys.exit(1)

    ep_num = ep.get("episode", "?")
    topic = ep.get("topic_title", "")
    log(f"EP{ep_num} | {topic} | 型態: {actual_type}")

    final_path = assembler(ep, asset_dir, out_dir)

    # YouTube 元資料
    yt = ep.get("youtube_metadata", {})
    result = {
        "final_video": str(final_path),
        "cover": str(out_dir / "cover.png"),
        "type": actual_type,
        "youtube_title": yt.get("title", ""),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
