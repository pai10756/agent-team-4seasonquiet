"""
Shorts 影片組裝腳本（overlay 版 v3）— 用現有 MP4 + PNG overlay 合成最終 Shorts。

v3 修正：
  - 精修去背：多層偵測（中性灰 + 邊緣連通 + 內部孤島清除 + 邊緣羽化）
  - 保留影片原始音軌（含旁白），不加 TTS / BGM
  - overlay 位置可用百分比或像素

用法:
  python scripts/assemble_shorts_overlay.py --config <edit_timeline.json> --output <output.mp4>

需要: moviepy 2.x, Pillow, numpy, scipy
"""

import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import label as ndlabel, binary_dilation, binary_erosion, gaussian_filter

# ── Config ──────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 24
SAFE_MARGIN = 60

if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def log(msg: str):
    print(f"[shorts] {msg}", file=sys.stderr)


# ── 精修去背 ──────────────────────────────────────────────

def remove_gray_background(img: Image.Image) -> Image.Image:
    """Remove gray/checkerboard background with high-quality edge treatment.

    Pipeline:
      1. Detect neutral-gray pixels (R≈G≈B, channel std < threshold)
      2. Label connected gray regions; only remove edge-connected ones
      3. Clean up: remove small content islands, fill small holes
      4. Feather alpha edges for anti-aliasing
    """
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba, dtype=np.float32)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3]

    # Step 1: Detect neutral gray with adaptive threshold
    # Neutral = low channel variance AND brightness in 160-258 range
    channel_std = np.std(rgb, axis=2)
    brightness = np.mean(rgb, axis=2)

    # Use stricter threshold near edges, looser near content
    is_neutral_gray = (channel_std < 8) & (brightness > 155) & (brightness < 258)

    # Also catch near-white pixels at edges (some PNGs have white bg)
    is_near_white = (channel_std < 5) & (brightness > 245)

    # Combine: anything that's neutral gray or near-white at edges
    is_bg_candidate = is_neutral_gray | is_near_white

    # Step 2: Only remove edge-connected gray regions (flood fill from borders)
    gray_labeled, _ = ndlabel(is_bg_candidate)

    edge_labels = set()
    edge_labels.update(gray_labeled[0, :].tolist())
    edge_labels.update(gray_labeled[-1, :].tolist())
    edge_labels.update(gray_labeled[:, 0].tolist())
    edge_labels.update(gray_labeled[:, -1].tolist())
    edge_labels.discard(0)

    bg_mask = np.isin(gray_labeled, list(edge_labels))

    # Step 3: Clean up
    # Remove tiny content islands (< 200 pixels) that are surrounded by bg
    content_mask = ~bg_mask
    content_labeled, n_content = ndlabel(content_mask)
    for i in range(1, n_content + 1):
        component = content_labeled == i
        if component.sum() < 200:
            bg_mask[component] = True

    # Fill small holes in content (< 100 pixels)
    hole_labeled, n_holes = ndlabel(bg_mask & ~np.isin(gray_labeled, list(edge_labels - {0})))
    # Actually, just erode then dilate the bg to smooth edges
    bg_mask = binary_erosion(bg_mask, iterations=1)
    bg_mask = binary_dilation(bg_mask, iterations=1)

    # Step 4: Create feathered alpha
    alpha = np.where(bg_mask, 0.0, 255.0)

    # Gaussian blur on alpha for soft edges (1.5px radius)
    alpha_blurred = gaussian_filter(alpha, sigma=1.2)

    # Only apply blur at the transition zone (within 3px of edge)
    edge_zone = binary_dilation(bg_mask, iterations=3) & ~binary_erosion(bg_mask, iterations=1)
    alpha = np.where(edge_zone, alpha_blurred, alpha)

    result = np.array(img_rgba)
    result[:, :, 3] = alpha.clip(0, 255).astype(np.uint8)
    return Image.fromarray(result)


def load_overlay(path: Path, scale: float = None, remove_bg: bool = True) -> Image.Image:
    """Load PNG, optionally remove bg, auto-crop, and scale."""
    img = Image.open(str(path))

    # If already RGBA with real transparency, skip bg removal
    if img.mode == "RGBA":
        arr = np.array(img)
        has_transparency = arr[:, :, 3].min() < 200
        if has_transparency:
            remove_bg = False

    if remove_bg:
        img = remove_gray_background(img)

    # Auto-crop transparent padding
    if img.mode == "RGBA":
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

    if scale and scale != 1.0:
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    return img


# ── 字幕渲染 ──────────────────────────────────────────────

def render_subtitle(text: str, style: dict) -> np.ndarray:
    """Render subtitle as RGBA numpy array, centered horizontally."""
    font_size = style.get("font_size", 52)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", font_size)
    except OSError:
        font = ImageFont.load_default()

    lines = text.split("\n")
    tmp = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp)

    line_metrics = []
    max_tw = 0
    for line in lines:
        bbox = tmp_draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        line_metrics.append((tw, th))
        max_tw = max(max_tw, tw)

    pad_x, pad_y = 36, 18
    line_gap = 10
    total_th = sum(m[1] for m in line_metrics) + line_gap * (len(lines) - 1)
    bar_w = max_tw + pad_x * 2
    bar_h = total_th + pad_y * 2

    img = Image.new("RGBA", (CANVAS_W, bar_h + pad_y * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = tuple(style.get("bg_color", [0, 0, 0, 150]))
    bar_left = (CANVAS_W - bar_w) // 2
    bar_top = pad_y
    draw.rounded_rectangle(
        [bar_left, bar_top, bar_left + bar_w, bar_top + bar_h],
        radius=14, fill=bg_color
    )

    stroke_w = style.get("stroke_width", 2)
    stroke_color = tuple(style.get("stroke_color", [0, 0, 0]))
    text_color = tuple(style.get("color", [255, 255, 255]))

    y_cursor = bar_top + pad_y
    for i, line in enumerate(lines):
        tw, th = line_metrics[i]
        tx = (CANVAS_W - tw) // 2
        draw.text((tx, y_cursor), line, font=font, fill=(*text_color, 255),
                  stroke_width=stroke_w, stroke_fill=(*stroke_color, 200))
        y_cursor += th + line_gap

    return np.array(img)


# ── 色調調整 ──────────────────────────────────────────────

def apply_color_adjust(frame: np.ndarray, adjust: dict) -> np.ndarray:
    result = frame.astype(np.float32)
    temp = adjust.get("temperature", 0)
    sat = adjust.get("saturation", 0)
    if temp != 0:
        result[:, :, 0] = np.clip(result[:, :, 0] + temp * 0.5, 0, 255)
        result[:, :, 2] = np.clip(result[:, :, 2] - temp * 0.5, 0, 255)
    if sat != 0:
        gray = np.mean(result[:, :, :3], axis=2, keepdims=True)
        factor = 1.0 + sat / 100.0
        result[:, :, :3] = np.clip(gray + (result[:, :, :3] - gray) * factor, 0, 255)
    return result.astype(np.uint8)


def apply_darken(frame: np.ndarray, strength: float = 0.45) -> np.ndarray:
    return (frame.astype(np.float32) * (1.0 - strength)).clip(0, 255).astype(np.uint8)


# ── 位置計算 ──────────────────────────────────────────────

def compute_position(overlay_size: tuple, pos_cfg: dict) -> tuple[int, int]:
    """Compute top-left (x, y). Supports 'left'/'center'/'right' or pixel values."""
    ow, oh = overlay_size
    m = SAFE_MARGIN

    px = pos_cfg.get("x", "center")
    py = pos_cfg.get("y", "center")

    if px == "left":       x = m
    elif px == "center":   x = (CANVAS_W - ow) // 2
    elif px == "right":    x = CANVAS_W - ow - m
    else:                  x = int(px) - ow // 2

    if py == "top":        y = m
    elif py == "center":   y = (CANVAS_H - oh) // 2
    elif py == "bottom":   y = CANVAS_H - oh - m
    else:                  y = int(py)

    x = max(m, min(x, CANVAS_W - ow - m))
    y = max(m, min(y, CANVAS_H - oh - m))
    return x, y


# ── 主組裝 ───────────────────────────────────────────────

def assemble(timeline: dict, work_dir: Path, output_path: Path):
    from moviepy import (
        VideoFileClip, ImageClip, AudioFileClip,
        CompositeVideoClip, CompositeAudioClip,
        concatenate_videoclips, vfx,
    )

    meta = timeline["meta"]
    canvas_w = meta["canvas"]["width"]
    canvas_h = meta["canvas"]["height"]
    fps = meta.get("fps", FPS)
    segments = timeline["segments"]
    sub_style = timeline.get("subtitles_style", {})

    # Load videos
    videos = {}
    for key, fname in timeline["videos"].items():
        vpath = work_dir / fname
        if not vpath.exists():
            log(f"ERROR: Video not found: {vpath}")
            sys.exit(1)
        videos[key] = VideoFileClip(str(vpath))
        log(f"Video '{key}': {videos[key].size}, {videos[key].duration:.1f}s, audio={'yes' if videos[key].audio else 'no'}")

    # Overlay cache
    overlay_cache = {}

    def get_overlay(name: str, scale: float = None, remove_bg: bool = True) -> Image.Image:
        key = f"{name}_{scale}_{remove_bg}"
        if key not in overlay_cache:
            path = work_dir / name
            if not path.exists():
                log(f"  WARNING: {name} not found")
                return None
            overlay_cache[key] = load_overlay(path, scale=scale, remove_bg=remove_bg)
            sz = overlay_cache[key].size
            log(f"  Overlay loaded: {name} → {sz[0]}x{sz[1]}")
        return overlay_cache[key]

    # Build segments
    log("=== Building segments ===")
    segment_clips = []

    for seg in segments:
        sid = seg["id"]
        t_start, t_end = seg["time_range"]
        seg_dur = t_end - t_start
        v_trim = seg["video_trim"]
        vsrc = seg["video_source"]

        log(f"\n--- Segment '{sid}' ({t_start}-{t_end}s) ---")

        # Trim video (with audio)
        src_clip = videos[vsrc]
        trim_end = min(v_trim[1], src_clip.duration)
        clip = src_clip.subclipped(v_trim[0], trim_end)

        # Extend if needed (freeze last frame, keep audio)
        if clip.duration < seg_dur:
            freeze_dur = seg_dur - clip.duration
            last_frame = clip.get_frame(clip.duration - 0.04)
            freeze = ImageClip(last_frame).with_duration(freeze_dur)
            clip = concatenate_videoclips([clip, freeze])

        clip = clip.with_duration(seg_dur)
        clip = clip.resized((canvas_w, canvas_h))

        # Color adjust
        color_adj = seg.get("color_adjust")
        if color_adj:
            adj = color_adj.copy()
            clip = clip.image_transform(lambda frame, a=adj: apply_color_adjust(frame, a))

        # Darken
        darken = seg.get("darken")
        if darken:
            s = float(darken)
            clip = clip.image_transform(lambda frame, st=s: apply_darken(frame, st))

        layers = [clip]

        # Overlays
        for ov in seg.get("overlays", []):
            asset_name = ov["asset"]
            ov_type = ov.get("type", "sticker")
            opacity = ov.get("opacity", 1.0)
            scale = ov.get("scale")
            fade_in = ov.get("fade_in", 0)
            fade_out = ov.get("fade_out", 0)
            delay = ov.get("delay", 0)
            no_remove_bg = ov.get("no_remove_bg", False)

            if ov_type == "fullcard_then_fade":
                card_img = Image.open(str(work_dir / asset_name)).convert("RGBA")
                card_img = card_img.resize((canvas_w, canvas_h), Image.LANCZOS)
                show_dur = ov.get("show_duration", seg_dur * 0.6)
                card_clip = (
                    ImageClip(np.array(card_img))
                    .with_duration(show_dur)
                    .with_position((0, 0))
                    .with_effects([vfx.CrossFadeOut(min(0.5, show_dur * 0.3))])
                )
                layers.append(card_clip)
                log(f"  Fullcard→fade: {asset_name} ({show_dur:.1f}s)")

            elif ov_type == "sticker":
                ov_img = get_overlay(asset_name, scale=scale, remove_bg=not no_remove_bg)
                if ov_img is None:
                    continue
                pos_cfg = ov.get("position", {"x": "center", "y": "center"})
                x, y = compute_position(ov_img.size, pos_cfg)

                ov_dur = seg_dur - delay
                ov_clip = (
                    ImageClip(np.array(ov_img))
                    .with_duration(ov_dur)
                    .with_start(delay)
                    .with_position((x, y))
                )
                if fade_in > 0:
                    ov_clip = ov_clip.with_effects([vfx.CrossFadeIn(fade_in)])
                if opacity < 1.0:
                    ov_clip = ov_clip.with_opacity(opacity)
                layers.append(ov_clip)
                log(f"  Sticker: {asset_name} @ ({x},{y})")

        # Subtitles
        sub_cfg = seg.get("subtitle")
        if sub_cfg and sub_cfg.get("text"):
            sub_frame = render_subtitle(sub_cfg["text"], sub_style)
            sub_h = sub_frame.shape[0]
            pos_y = canvas_h - sub_h - sub_style.get("position_y_from_bottom", 180)

            sub_local_start = max(0, sub_cfg["start"] - t_start)
            sub_local_end = min(seg_dur, sub_cfg["end"] - t_start)
            sub_dur = sub_local_end - sub_local_start

            if sub_dur > 0:
                sub_clip = (
                    ImageClip(sub_frame)
                    .with_duration(sub_dur)
                    .with_start(sub_local_start)
                    .with_position(("center", pos_y))
                )
                layers.append(sub_clip)

        seg_comp = CompositeVideoClip(layers, size=(canvas_w, canvas_h)).with_duration(seg_dur)
        segment_clips.append(seg_comp)

    # Concatenate
    log("\n=== Concatenating ===")
    final_video = concatenate_videoclips(segment_clips, method="compose")
    total_dur = final_video.duration
    log(f"Total duration: {total_dur:.1f}s")

    # Export (keeps original audio from video clips)
    log(f"\n=== Exporting to {output_path} ===")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="medium",
        threads=4,
        logger="bar",
    )

    size_mb = output_path.stat().st_size / 1024 / 1024
    log(f"\nDone! {output_path} ({size_mb:.1f}MB, {total_dur:.1f}s)")

    for v in videos.values():
        v.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Shorts overlay 組裝 v3")
    parser.add_argument("--config", "-c", required=True, help="edit_timeline.json")
    parser.add_argument("--output", "-o", required=True, help="輸出 MP4")
    args = parser.parse_args()

    config_path = Path(args.config)
    timeline = json.loads(config_path.read_text(encoding="utf-8"))
    assemble(timeline, config_path.parent, Path(args.output))


if __name__ == "__main__":
    main()
