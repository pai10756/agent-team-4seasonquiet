"""
素材生成主控腳本 v3.2 — Gemini + Pillow Hybrid 模式。

流程：
  Step A: Gemini 生成「無文字」高品質視覺底圖（含 3D 小靜、hero object、背景）
  Step B: Pillow 品牌文字系統疊加（標題、副標、badge — 固定字體/字重/對齊/對比度）

Gemini 負責「美感」，Pillow 負責「品牌一致性 + 文字正確性」。

用法:
  python scripts/generate_assets.py <episode.json> --output-dir <assets_dir>

環境變數:
  GEMINI_API_KEY — Gemini API key
  JIMENG_SESSION_ID — 即夢 session ID（standard/hybrid）
  ELEVENLABS_API_KEY — ElevenLabs API key（TTS）
"""

import base64
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from submit_seedance import generate_seedance_video, check_api_health

GEMINI_API_KEY = os.environ.get("GEMINI_IMAGE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL_PRIMARY = "gemini-3.1-flash-image-preview"
IMAGE_MODEL_FALLBACK = "gemini-2.5-flash-image"
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", IMAGE_MODEL_PRIMARY)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "yC4SQtHeGxfvfsrKVdz9")  # Little Ching / 小靜

BRAND_TOKENS_PATH = BASE / "configs" / "brand_visual_tokens.json"
REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference.jpg"
REFERENCE_CARD = BASE / "characters" / "mascot" / "3d_main_card_reference.jpg"
CHARACTER_JSON = BASE / "characters" / "mascot" / "character.json"

CARD_W, CARD_H = 1080, 1920
SAFE_MARGIN = 72


def log(msg: str):
    print(f"[asset_gen] {msg}", file=sys.stderr)


def load_config(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def _load_brand_palette() -> dict:
    brand = load_config(BRAND_TOKENS_PATH)
    palette = brand.get("palette", {})
    return {
        "cream": _hex_to_rgb(palette.get("cream_white", {}).get("hex", "#F6F1E7")),
        "sage": _hex_to_rgb(palette.get("sage_green", {}).get("hex", "#A8B88A")),
        "olive": _hex_to_rgb(palette.get("olive_dark", {}).get("hex", "#4E5538")),
        "brown": _hex_to_rgb(palette.get("brown_text", {}).get("hex", "#3B2A1F")),
    }


# ── Gemini Image Generation ─────────────────────────────

def _call_gemini_image(prompt: str, model: str, contents_parts: list = None,
                       max_retries: int = 3) -> bytes | None:
    """Call Gemini image API with optional reference images, return image bytes or None."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    if contents_parts is None:
        contents_parts = [{"text": prompt}]

    payload = json.dumps({
        "contents": [{"parts": contents_parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())

            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    if len(img_bytes) > 10 * 1024:
                        return img_bytes
                    log(f"  Image too small, retrying...")

            log(f"  No image in response ({model}, attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            code = e.code
            log(f"  HTTP {code} ({model}, attempt {attempt + 1}): {body}")
            if code in (503, 429) and model == IMAGE_MODEL_PRIMARY:
                log(f"  Falling back to {IMAGE_MODEL_FALLBACK}")
                return _call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, contents_parts, max_retries)
        except Exception as e:
            log(f"  Error ({model}, attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1 and model == IMAGE_MODEL_PRIMARY:
                log(f"  Falling back to {IMAGE_MODEL_FALLBACK}")
                return _call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, contents_parts, max_retries)

        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    return None


def _build_reference_parts(include_card_ref: bool = True) -> list:
    """Build inlineData parts for reference images."""
    parts = []

    if REFERENCE_3D.exists():
        ref_b64 = base64.b64encode(REFERENCE_3D.read_bytes()).decode()
        parts.append({"text": "CHARACTER REFERENCE — the 3D mascot must look EXACTLY like this (same face, markings, matte plastic material, green apron, proportions):"})
        parts.append({
            "inlineData": {"mimeType": "image/jpeg", "data": ref_b64}
        })

    if include_card_ref and REFERENCE_CARD.exists():
        card_b64 = base64.b64encode(REFERENCE_CARD.read_bytes()).decode()
        parts.append({"text": "QUALITY REFERENCE — the output should match this level of quality, composition style, and visual polish:"})
        parts.append({
            "inlineData": {"mimeType": "image/jpeg", "data": card_b64}
        })

    return parts


def _load_character_block() -> str:
    """Load character identity block for prompt."""
    char = load_config(CHARACTER_JSON)
    locked = char.get("locked_identity", {})
    negative = char.get("negative_prompt", [])

    block = (
        "CHARACTER IDENTITY (locked):\n"
        f"- {locked.get('construction', '')}\n"
        f"- {locked.get('proportion', '')}\n"
        f"- Body: {locked.get('body', {}).get('base_color', '')}, "
        f"{locked.get('body', {}).get('pattern', '')}, "
        f"{locked.get('body', {}).get('material', '')}\n"
        f"- Forehead: {locked.get('head', {}).get('forehead', '')}\n"
        f"- Eyes: {locked.get('head', {}).get('eyes', '')}\n"
    )

    outfit = char.get("outfit_options", {}).get("apron", {})
    if outfit:
        block += f"- Outfit: {outfit.get('prompt_fragment', 'green apron')}\n"

    if negative:
        block += f"\nNEVER: {', '.join(negative)}\n"

    return block


# ══════════════════════════════════════════════════════════
# Step A: Gemini generates TEXT-FREE visual base
# ══════════════════════════════════════════════════════════

def _build_visual_prompt(scene: dict, episode: dict) -> tuple[str, bool]:
    """Build Gemini prompt for text-free visual. Returns (prompt, needs_mascot_ref)."""
    visual_type = scene.get("visual_type", "evidence_card")
    has_mascot = scene.get("mascot_presence", False)
    hero = scene.get("hero_object", "")
    bg_scene = scene.get("background_scene", "warm kitchen interior, soft natural light")
    expr = scene.get("mascot_expression", "thinking")
    pose = scene.get("mascot_pose", "hug_object_side")

    char_block = _load_character_block() if has_mascot else ""

    no_text_rule = (
        "\n\nCRITICAL: Generate ONLY the visual scene. "
        "Do NOT render any text, titles, headlines, labels, captions, watermarks, or letters on the image. "
        "The image must be completely text-free. Text will be added separately.\n"
    )

    if visual_type == "poster_cover":
        prompt = (
            f"A 9:16 vertical poster visual (1080x1920) for a health content card.\n"
            f"STYLE: 75% realistic photo + 25% 3D elements. Warm, trustworthy, mature.\n\n"
            f"SCENE: {bg_scene}\n"
            f"HERO OBJECT: realistic {hero}, prominently placed in center-lower area, occupying ~50-60% of frame.\n"
            f"Warm natural lighting, shallow depth of field.\n"
        )
        if has_mascot:
            prompt += (
                f"MASCOT: One 3D smooth matte plastic toy mascot (Taiwanese leopard cat), "
                f"expression: {expr}, pose: {pose}, beside the hero object as sidekick (20-30% of frame).\n"
                f"{char_block}\n"
                f"Only ONE mascot. Mascot must match reference exactly.\n"
            )
        prompt += (
            f"TOP 30% of image should be relatively clean/simple for text overlay later.\n"
            f"Background: warm cream or warm lifestyle scene. No clutter."
            f"{no_text_rule}"
        )
        return prompt, has_mascot

    elif visual_type == "brand_closing":
        prompt = (
            f"A 9:16 vertical farewell card visual (1080x1920).\n"
            f"STYLE: Clean, warm, minimal. Warm gradient from pale cream to gentle warm beige, "
            f"with very subtle soft bokeh circles.\n\n"
            f"CENTER: One 3D smooth matte plastic toy mascot (Taiwanese leopard cat) facing directly "
            f"at the viewer, looking warm and friendly. Expression: {expr}. "
            f"The mascot is actively waving goodbye with one hand raised, body slightly leaning forward "
            f"toward the viewer, eyes making direct eye contact, with a gentle warm smile. "
            f"The pose should feel like saying 'see you next time' to a friend, not a static display pose.\n"
            f"Mascot should be prominent (40-50% of frame).\n"
            f"{char_block}\n"
            f"Only ONE mascot. Clean background, no clutter, no decorative sparkles or stars.\n"
            f"Leave top 25% and bottom 15% empty for text overlay."
            f"{no_text_rule}"
        )
        return prompt, True

    elif visual_type == "comparison_card":
        comparison = scene.get("comparison_items", [])
        prompt = (
            f"A 9:16 vertical infographic visual (1080x1920) for comparing food items.\n"
            f"STYLE: Clean, warm, professional. Background: warm cream (#F6F1E7).\n\n"
            f"VISUAL: Show a clean comparison layout with realistic food photography.\n"
        )
        if comparison:
            items_desc = ", ".join(str(c) for c in comparison[:3])
            prompt += f"Items to compare: {items_desc}\n"
        elif hero:
            prompt += f"Related to: {hero}\n"
        prompt += (
            f"Use clean visual hierarchy. Max 2-3 items.\n"
            f"Leave top 25% empty for headline overlay.\n"
            f"No mascot, no animal character."
            f"{no_text_rule}"
        )
        return prompt, False

    elif visual_type == "evidence_card":
        prompt = (
            f"A 9:16 vertical evidence/data visual (1080x1920) for health content.\n"
            f"STYLE: Clean, warm, professional infographic. Background: warm cream (#F6F1E7).\n\n"
        )
        if hero:
            prompt += f"VISUAL: Show a simple, clear visual related to {hero}.\n"
        prompt += (
            f"Use simple icons or clean graphics, not complex charts.\n"
            f"Leave top 25% empty for headline overlay.\n"
            f"No mascot, no animal character."
            f"{no_text_rule}"
        )
        return prompt, False

    else:  # safety_reminder or fallback
        prompt = (
            f"A 9:16 vertical reminder card visual (1080x1920).\n"
            f"STYLE: Clean, warm, reassuring. Background: warm cream (#F6F1E7).\n\n"
            f"VISUAL: A simple, warm visual element (like a gentle icon or soft illustration) "
            f"that conveys care and safety.\n"
            f"Leave center area relatively open for text overlay.\n"
            f"No mascot, no animal character. Not alarmist."
            f"{no_text_rule}"
        )
        return prompt, False


def generate_visual_base(scene: dict, episode: dict, output_path: Path) -> bool:
    """Step A: Generate text-free visual via Gemini."""
    if not GEMINI_API_KEY:
        log("Error: GEMINI_API_KEY not set")
        return False

    prompt, needs_ref = _build_visual_prompt(scene, episode)

    parts = _build_reference_parts(include_card_ref=needs_ref) if needs_ref else []
    parts.append({"text": prompt})

    img_bytes = _call_gemini_image(prompt, IMAGE_MODEL, parts)
    if not img_bytes:
        return False

    output_path.write_bytes(img_bytes)
    log(f"  Visual base: {output_path.name} ({len(img_bytes) / 1024:.0f}KB)")
    return True


# ══════════════════════════════════════════════════════════
# Step B: Pillow Brand Text Overlay System (Level 2+3)
# ══════════════════════════════════════════════════════════

TEXT_TOKENS_PATH = BASE / "configs" / "text_style_tokens.json"


def _load_text_tokens() -> dict:
    return load_config(TEXT_TOKENS_PATH)


def _load_font(family: str, size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(family, size)
    except OSError:
        return ImageFont.load_default()


def _region_brightness(img, box: tuple) -> float:
    """Average brightness of a region (0-255). box=(left,top,right,bottom)."""
    try:
        import numpy as np
        crop = img.crop(box).convert("RGB")
        return float(np.array(crop).mean())
    except (ImportError, Exception):
        return 200  # assume light


def _smart_wrap(text: str, font, max_width: int, draw) -> list[str]:
    """Wrap Chinese text with poster-style line breaks.
    Prioritizes keeping punctuation with the preceding character.
    Never leaves a single punctuation mark alone on a line."""
    # Punctuation that should stay with the previous character
    trailing_punct = set("？！。，、：；」』）》")

    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and current:
            # Don't break if next char is trailing punctuation
            if char in trailing_punct:
                current = test
                continue
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)

    # Post-process: if last line is just punctuation, merge it back
    if len(lines) > 1 and len(lines[-1]) == 1 and lines[-1] in trailing_punct:
        lines[-2] += lines[-1]
        lines.pop()

    return lines


def _draw_local_frost(img, text_bbox: tuple, tokens: dict):
    """Draw a local frosted glass effect behind text area. Only used when background is very busy."""
    from PIL import Image, ImageFilter, ImageDraw as ID2

    pad_x = tokens.get("padding_x", 36)
    pad_y = tokens.get("padding_y", 20)
    radius = tokens.get("corner_radius", 16)
    blur_r = tokens.get("blur_radius", 25)
    opacity = tokens.get("frost_opacity", 100)
    frost_rgb = tuple(tokens.get("frost_color", [255, 255, 255]))

    left = max(0, text_bbox[0] - pad_x)
    top = max(0, text_bbox[1] - pad_y)
    right = min(CARD_W, text_bbox[2] + pad_x)
    bottom = min(CARD_H, text_bbox[3] + pad_y)

    region = img.crop((left, top, right, bottom)).convert("RGBA")
    blurred = region.filter(ImageFilter.GaussianBlur(blur_r))
    frost = Image.new("RGBA", blurred.size, (*frost_rgb, opacity))
    blurred = Image.alpha_composite(blurred, frost)

    mask = Image.new("L", blurred.size, 0)
    mask_draw = ID2.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, mask.width, mask.height], radius=radius, fill=255)

    base_region = img.crop((left, top, right, bottom)).convert("RGBA")
    base_region.paste(blurred, mask=mask)
    img.paste(base_region, (left, top))


def _draw_text_stroked(draw, xy, text, font, fill, stroke_width=0, stroke_fill=None,
                       shadow_offset=0, shadow_color=None):
    """Draw text with stroke outline + drop shadow for Level 3 poster quality."""
    x, y = xy
    # Drop shadow (very subtle)
    if shadow_offset and shadow_color:
        sc = tuple(shadow_color) if isinstance(shadow_color, list) else shadow_color
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font,
                  fill=sc, stroke_width=max(1, stroke_width - 1),
                  stroke_fill=sc if stroke_width else None)
    # Main text with stroke
    if stroke_width and stroke_fill:
        draw.text((x, y), text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        draw.text((x, y), text, font=font, fill=fill)


def _measure_text_block(draw, lines: list[str], font, line_spacing: int) -> tuple:
    """Measure total width and height of a text block. Returns (max_w, total_h)."""
    max_w = 0
    total_h = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_w = max(max_w, w)
        total_h += h
        if i < len(lines) - 1:
            total_h += line_spacing
    return max_w, total_h


def _draw_text_block_v2(draw, lines: list[str], font, x: int, y: int,
                        fill: tuple, stroke_width: int = 0, stroke_fill=None,
                        shadow_offset: int = 0, shadow_color=None,
                        line_spacing: int = 20, align: str = "left",
                        max_width: int = 0) -> int:
    """Draw text block with stroke + shadow. Returns y after last line."""
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if align == "center" and max_width:
            lx = x + (max_width - tw) // 2
        elif align == "right" and max_width:
            lx = x + max_width - tw
        else:
            lx = x
        _draw_text_stroked(draw, (lx, y), line, font, fill, stroke_width, stroke_fill,
                           shadow_offset, shadow_color)
        y += th + line_spacing
    return y


def _draw_badge_v2(draw, text: str, font, tokens: dict):
    """Draw badge — rounded rect or circle, from tokens config."""
    shape = tokens.get("shape", "rounded_rect")
    margin_r = tokens.get("margin_right", 72)
    margin_t = tokens.get("margin_top", 90)
    fill_rgb = _hex_to_rgb(tokens.get("fill", "#F3E9DA"))
    fill_opacity = tokens.get("fill_opacity", 230)
    stroke_rgb = _hex_to_rgb(tokens.get("stroke", "#B98E72"))
    stroke_w = tokens.get("stroke_width", 3)
    text_rgb = _hex_to_rgb(tokens.get("text_color", "#6C5B43"))

    lines = text.replace("\\n", "\n").split("\n")

    # Measure text to auto-size badge
    line_h = 32
    max_tw = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_tw = max(max_tw, bbox[2] - bbox[0])
    total_text_h = len(lines) * line_h

    pad_x, pad_y = 24, 16
    badge_w = max(max_tw + pad_x * 2, tokens.get("width", 160))
    badge_h = max(total_text_h + pad_y * 2, tokens.get("height", 72))
    corner_r = tokens.get("corner_radius", 14)

    # Position: top right
    right = CARD_W - margin_r
    left = right - badge_w
    top = margin_t
    bottom = top + badge_h
    cx = (left + right) // 2
    cy = (top + bottom) // 2

    if shape == "circle":
        r = max(badge_w, badge_h) // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(*fill_rgb, fill_opacity),
                     outline=(*stroke_rgb, 255), width=stroke_w)
    else:
        draw.rounded_rectangle([left, top, right, bottom], radius=corner_r,
                               fill=(*fill_rgb, fill_opacity),
                               outline=(*stroke_rgb, 255), width=stroke_w)

    # Draw text centered in badge
    start_y = cy - total_text_h // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = cx - tw // 2
        ty = start_y + i * line_h
        draw.text((tx, ty), line, font=font, fill=(*text_rgb, 255))


def overlay_brand_text(visual_path: Path, scene: dict, output_path: Path) -> bool:
    """Step B: Brand text overlay using Level 2+3 Pillow system."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        log("Pillow not installed, skipping text overlay")
        return False

    tokens = _load_text_tokens()
    hl_tok = tokens.get("headline", {})
    sub_tok = tokens.get("subtitle", {})
    badge_tok = tokens.get("badge", {})
    brand_tok = tokens.get("brand_name", {})
    frost_tok = tokens.get("text_backing", {})
    margin = tokens.get("safe_margin", SAFE_MARGIN)

    visual_type = scene.get("visual_type", "evidence_card")
    headline = scene.get("on_screen_text_main", "")
    sub = scene.get("on_screen_text_sub", "")
    badge_text = scene.get("badge_text", "")

    # Load fonts from tokens
    if visual_type == "poster_cover":
        hl_size = hl_tok.get("font_size_cover", 108)
    elif visual_type == "brand_closing":
        hl_size = hl_tok.get("font_size_closing", 96)
    else:
        hl_size = hl_tok.get("font_size_middle", 88)

    font_headline = _load_font(hl_tok.get("font_family", "C:/Windows/Fonts/msjhbd.ttc"), hl_size)
    font_subtitle = _load_font(sub_tok.get("font_family", "C:/Windows/Fonts/msjh.ttc"),
                               sub_tok.get("font_size", 48))
    font_badge = _load_font(badge_tok.get("font_family", "C:/Windows/Fonts/msjhbd.ttc"),
                            badge_tok.get("font_size", 30))
    font_brand = _load_font(brand_tok.get("font_family", "C:/Windows/Fonts/msjhbd.ttc"),
                            brand_tok.get("font_size", 80))

    # Colors + shadow from tokens
    hl_color = _hex_to_rgb(hl_tok.get("color", "#2E3326"))
    hl_stroke_w = hl_tok.get("stroke_width", 6)
    hl_stroke_fill = _hex_to_rgb(hl_tok.get("stroke_fill", "#F6F1E7"))
    hl_shadow_off = hl_tok.get("shadow_offset", 3)
    hl_shadow_col = tuple(hl_tok.get("shadow_color", [0, 0, 0, 50]))
    sub_color = _hex_to_rgb(sub_tok.get("color", "#5A4A3C"))
    sub_stroke_w = sub_tok.get("stroke_width", 4)
    sub_stroke_fill = _hex_to_rgb(sub_tok.get("stroke_fill", "#F6F1E7"))
    sub_shadow_off = sub_tok.get("shadow_offset", 2)
    sub_shadow_col = tuple(sub_tok.get("shadow_color", [0, 0, 0, 40]))
    brand_color = _hex_to_rgb(brand_tok.get("color", "#4E5538"))
    brand_stroke_w = brand_tok.get("stroke_width", 5)
    brand_stroke_fill = _hex_to_rgb(brand_tok.get("stroke_fill", "#F6F1E7"))
    brand_shadow_off = brand_tok.get("shadow_offset", 3)
    brand_shadow_col = tuple(brand_tok.get("shadow_color", [0, 0, 0, 40]))

    # --- Load and crop visual to canvas ---
    img = Image.open(visual_path).convert("RGBA")
    iw, ih = img.size
    target_ratio = CARD_W / CARD_H
    img_ratio = iw / ih
    if img_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        img = img.crop((left, 0, left + new_w, ih))
    elif img_ratio < target_ratio:
        new_h = int(iw / target_ratio)
        top = (ih - new_h) // 2
        img = img.crop((0, top, iw, top + new_h))
    img = img.resize((CARD_W, CARD_H), Image.Resampling.LANCZOS)

    # --- Measure text to compute layout ---
    measure = ImageDraw.Draw(img)
    max_text_w = int(CARD_W * hl_tok.get("max_width_ratio", 0.80))
    badge_reserve = (badge_tok.get("width", 160) + 30) if badge_text else 0
    hl_max_w = max_text_w - badge_reserve

    hl_lines = _smart_wrap(headline, font_headline, hl_max_w, measure) if headline else []
    sub_lines = _smart_wrap(sub, font_subtitle, max_text_w, measure) if sub else []

    hl_spacing = hl_tok.get("line_spacing", 22)
    sub_spacing = sub_tok.get("line_spacing", 12)

    hl_block_w, hl_block_h = _measure_text_block(measure, hl_lines, font_headline, hl_spacing) if hl_lines else (0, 0)
    sub_block_w, sub_block_h = _measure_text_block(measure, sub_lines, font_subtitle, sub_spacing) if sub_lines else (0, 0)

    # Determine anchor Y
    if visual_type == "poster_cover":
        anchor_y = hl_tok.get("anchor_y_cover", 90)
    elif visual_type == "brand_closing":
        anchor_y = hl_tok.get("anchor_y_closing", 100)
    else:
        anchor_y = hl_tok.get("anchor_y_middle", 72)

    gap = sub_tok.get("gap_from_headline", 20)

    # --- Adapt colors to background brightness ---
    total_text_h = hl_block_h + (gap + sub_block_h if sub_lines else 0)
    headline_region = (margin, anchor_y, CARD_W - margin,
                       min(CARD_H, anchor_y + total_text_h + 40))
    brightness = _region_brightness(img, headline_region)

    if brightness < 100:
        hl_color = (255, 255, 255)
        hl_stroke_fill = (40, 35, 30)
        sub_color = (240, 235, 225)
        sub_stroke_fill = (40, 35, 30)

    # --- Only use frost if background is very busy (high variance) ---
    frost_style = frost_tok.get("style", "none")
    if frost_style == "local_frost" and headline:
        frost_box = (margin, anchor_y,
                     margin + max(hl_block_w, sub_block_w) + badge_reserve,
                     anchor_y + total_text_h)
        _draw_local_frost(img, frost_box, frost_tok)

    # --- Create overlay for text ---
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- Draw headline (thick stroke + drop shadow = poster quality) ---
    cur_y = anchor_y
    if hl_lines:
        cur_y = _draw_text_block_v2(
            draw, hl_lines, font_headline, margin, cur_y,
            fill=hl_color, stroke_width=hl_stroke_w, stroke_fill=hl_stroke_fill,
            shadow_offset=hl_shadow_off, shadow_color=hl_shadow_col,
            line_spacing=hl_spacing, align=hl_tok.get("align", "left"),
            max_width=hl_max_w)
        cur_y += gap

    # --- Draw subtitle ---
    if sub_lines:
        _draw_text_block_v2(
            draw, sub_lines, font_subtitle, margin, cur_y,
            fill=sub_color, stroke_width=sub_stroke_w, stroke_fill=sub_stroke_fill,
            shadow_offset=sub_shadow_off, shadow_color=sub_shadow_col,
            line_spacing=sub_spacing, align=sub_tok.get("align", "left"),
            max_width=max_text_w)

    # --- Draw badge ---
    if badge_text:
        _draw_badge_v2(draw, badge_text, font_badge, badge_tok)

    # --- Brand closing: NO duplicate bottom brand name ---
    # The brand name is already in the headline position for closing cards

    # --- Alpha composite ---
    result = Image.alpha_composite(img, overlay)
    result.convert("RGB").save(str(output_path), quality=95)
    log(f"  Composed: {output_path.name}")
    return True


# ══════════════════════════════════════════════════════════
# Complete Card Pipeline: Gemini visual + Pillow text
# ══════════════════════════════════════════════════════════

def generate_complete_card(scene: dict, episode: dict, asset_dir: Path) -> bool:
    """Generate complete card: Gemini visual base + Pillow text overlay."""
    sid = scene["scene_id"]
    visual_path = asset_dir / f"visual_{sid}.png"
    card_path = asset_dir / f"card_{sid}.jpg"

    if card_path.exists():
        log(f"  Card {sid} exists, skipping")
        return True

    # Step A: Generate text-free visual
    if not visual_path.exists():
        ok = generate_visual_base(scene, episode, visual_path)
        if not ok:
            return False
    else:
        log(f"  Visual {sid} exists, skipping generation")

    # Step B: Overlay brand text
    ok = overlay_brand_text(visual_path, scene, card_path)
    return ok


def generate_all_scene_cards(episode: dict, asset_dir: Path) -> list[dict]:
    """Generate all scene cards via Gemini + Pillow hybrid pipeline."""
    scenes = episode.get("scenes", [])
    results = []

    for scene in scenes:
        sid = scene["scene_id"]
        role = scene.get("scene_role", "")
        vtype = scene.get("visual_type", "")
        log(f"Card {sid} ({role}/{vtype})...")

        ok = generate_complete_card(scene, episode, asset_dir)
        card_path = asset_dir / f"card_{sid}.jpg"
        results.append({
            "scene_id": sid,
            "path": str(card_path) if ok else None,
            "success": ok,
        })
        time.sleep(10)  # Gemini image gen: 10-12s interval to avoid 429 on free tier

    return results


# ══════════════════════════════════════════════════════════
# ElevenLabs TTS
# ══════════════════════════════════════════════════════════

def generate_tts_elevenlabs(text: str, output_path: Path, voice_id: str = None) -> bool:
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
            "style": 0.15, "use_speaker_boost": True, "speed": 1.15,
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


def generate_subtitle_tts(episode: dict, asset_dir: Path) -> dict:
    """Per-subtitle TTS generation with manifest."""
    subtitles = episode.get("subtitles", [])
    if not subtitles:
        return {"success": False, "error": "no subtitles"}

    tts_dir = asset_dir / "tts_segments"
    manifest_path = asset_dir / "tts_manifest.json"

    if manifest_path.exists():
        log(f"  TTS manifest exists, skipping")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"success": True, "manifest": str(manifest_path), "segments": manifest}

    tts_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    for i, sub in enumerate(subtitles):
        text = sub.get("text", "") if isinstance(sub, dict) else str(sub)
        start = sub.get("start", 0) if isinstance(sub, dict) else 0
        end = sub.get("end", 0) if isinstance(sub, dict) else 0
        if not text:
            continue

        seg_path = tts_dir / f"tts_{i:03d}.mp3"
        if not seg_path.exists():
            log(f"  TTS [{i}] ({start:.1f}-{end:.1f}s): {text[:20]}...")
            generate_tts_elevenlabs(text, seg_path)
            time.sleep(0.5)

        segments.append({"index": i, "start": start, "end": end, "text": text, "path": str(seg_path)})

    manifest_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  TTS: {len(segments)} segments generated")
    return {"success": True, "manifest": str(manifest_path), "segments": segments}


# ══════════════════════════════════════════════════════════
# Legacy & Supporting: Scene images, ranking cards, Seedance
# ══════════════════════════════════════════════════════════

def generate_legacy_scene_images(episode: dict, asset_dir: Path) -> list[dict]:
    """Generate scene images from legacy scene_images[] field."""
    results = []
    ep_type = episode.get("type", "standard")
    no_face = " No human faces visible, no portraits." if ep_type != "quick_cut" else ""

    for scene in episode.get("scene_images", []):
        sid = scene["id"]
        prompt = scene["prompt"]
        if no_face and "no human face" not in prompt.lower():
            prompt += no_face
        out_path = asset_dir / f"scene_{sid}.jpg"

        if out_path.exists():
            results.append({"id": sid, "path": str(out_path), "success": True})
            continue

        log(f"Legacy scene {sid}: {scene.get('description', '')[:30]}")
        img_bytes = _call_gemini_image(prompt, IMAGE_MODEL)
        if img_bytes:
            out_path.write_bytes(img_bytes)
            results.append({"id": sid, "path": str(out_path), "success": True})
        else:
            results.append({"id": sid, "path": None, "success": False})
        time.sleep(10)  # Gemini image gen: 10s+ interval to avoid 429

    return results


def generate_ranking_cards(episode: dict, asset_dir: Path) -> list[dict]:
    """Generate ranking cards with brand-consistent styling."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log("Pillow not installed")
        return []

    ranking_data = episode.get("ranking_data", [])
    if not ranking_data:
        return []

    palette = _load_brand_palette()
    results = []

    for item in ranking_data:
        rank = item["rank"]
        out_path = asset_dir / f"ranking_card_{rank}.jpg"
        if out_path.exists():
            results.append({"rank": rank, "path": str(out_path), "success": True})
            continue

        log(f"Ranking card #{rank}: {item['food']}")

        img = Image.new("RGB", (CARD_W, CARD_H), palette["cream"])
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()

        try:
            font_rank = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", 200)
            font_food = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", 90)
            font_value = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 56)
            font_comp = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 44)
        except OSError:
            font_rank = ImageFont.load_default()
            font_food = font_rank
            font_value = font_rank
            font_comp = font_rank

        rank_text = f"#{rank}"
        bbox = draw.textbbox((0, 0), rank_text, font=font_rank)
        rx = (CARD_W - (bbox[2] - bbox[0])) // 2
        draw.text((rx, 300), rank_text, font=font_rank, fill=palette["sage"])

        food_text = item["food"]
        bbox = draw.textbbox((0, 0), food_text, font=font_food)
        fx = (CARD_W - (bbox[2] - bbox[0])) // 2
        draw.text((fx, 600), food_text, font=font_food, fill=palette["olive"])

        value_text = f"{item['value']} {item['unit']}"
        bbox = draw.textbbox((0, 0), value_text, font=font_value)
        vx = (CARD_W - (bbox[2] - bbox[0])) // 2
        draw.text((vx, 750), value_text, font=font_value, fill=palette["olive"])

        try:
            val = float(item["value"]) if isinstance(item["value"], (int, float)) else float(str(item["value"]).split("-")[-1].strip())
            max_val = max(float(d["value"]) if isinstance(d["value"], (int, float)) else float(str(d["value"]).split("-")[-1].strip()) for d in ranking_data)
            bar_ratio = val / max_val if max_val > 0 else 0.5
        except (ValueError, ZeroDivisionError):
            bar_ratio = 0.5
        bar_w = int((CARD_W - 200) * min(bar_ratio, 1.0))
        bar_y = 880
        draw.rounded_rectangle([100, bar_y, CARD_W - 100, bar_y + 60], radius=12, fill=(230, 225, 215))
        if bar_w > 0:
            draw.rounded_rectangle([100, bar_y, 100 + bar_w, bar_y + 60], radius=12, fill=palette["sage"])

        comp = item.get("comparison", "")
        if comp:
            bbox = draw.textbbox((0, 0), comp, font=font_comp)
            cx = (CARD_W - (bbox[2] - bbox[0])) // 2
            draw.text((cx, 980), comp, font=font_comp, fill=palette["olive"])

        img.save(str(out_path), quality=95)
        results.append({"rank": rank, "path": str(out_path), "success": True})

    return results


def generate_seedance_scene_images(episode: dict, asset_dir: Path) -> list[dict]:
    """Generate Seedance scene reference images using Gemini (EP09 workflow).

    讀取 episode.json 中的 seedance_scenes[] 定義，用 Gemini 以
    character_turnaround 和/或 mascot_turnaround 為 ref 生成場景圖。

    EP09 成熟版流程：
    - live_scene01~05: 人物場景圖（ref = character_turnaround）
    - live_scene06_mascot: 人物+小靜同框（ref = character_turnaround + mascot_turnaround）
    """
    scenes = episode.get("seedance_scenes", [])
    if not scenes:
        return []

    char_ref = asset_dir / "character_turnaround.png"
    mascot_ref = asset_dir / "mascot_turnaround.png"
    if not mascot_ref.exists():
        mascot_ref = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"

    results = []
    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        out_path = asset_dir / f"live_scene{scene_id}.png"
        if out_path.exists():
            results.append({"scene_id": scene_id, "path": str(out_path), "success": True})
            continue

        prompt = scene.get("prompt", "")
        if not prompt:
            continue

        refs = []
        if char_ref.exists():
            refs.append(char_ref)
        if scene.get("include_mascot") and mascot_ref.exists():
            refs.append(mascot_ref)

        log(f"Generating scene {scene_id} ({len(refs)} refs)...")
        img_bytes = call_gemini_image_with_refs(prompt, refs)
        if img_bytes:
            out_path.write_bytes(img_bytes)
            log(f"  Saved: {out_path.name} ({len(img_bytes) // 1024} KB)")
            results.append({"scene_id": scene_id, "path": str(out_path), "success": True})
        else:
            log(f"  FAILED: scene {scene_id}")
            results.append({"scene_id": scene_id, "path": None, "success": False})

        time.sleep(10)  # Gemini image gen: 10s+ interval to avoid 429

    return results


def call_gemini_image_with_refs(prompt: str, ref_paths: list[Path],
                                 model: str = None, max_retries: int = 3) -> bytes | None:
    """Call Gemini image generation with reference images (EP09 pattern)."""
    model = model or IMAGE_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    parts = []
    for ref in ref_paths:
        if ref.exists():
            b64 = __import__("base64").b64encode(ref.read_bytes()).decode()
            mime = "image/png" if str(ref).endswith(".png") else "image/jpeg"
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    parts.append({"text": prompt})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    if len(img_bytes) > 10 * 1024:
                        return img_bytes
                    log(f"  Image too small, retrying...")
            log(f"  No image in response ({model}, attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} ({model}, attempt {attempt + 1}): {body}")
            if e.code in (503, 429) and model == IMAGE_MODEL_PRIMARY:
                return call_gemini_image_with_refs(prompt, ref_paths, IMAGE_MODEL_FALLBACK, max_retries)
        except Exception as e:
            log(f"  Error ({model}, attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1 and model == IMAGE_MODEL_PRIMARY:
                return call_gemini_image_with_refs(prompt, ref_paths, IMAGE_MODEL_FALLBACK, max_retries)
        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))
    return None


# ══════════════════════════════════════════════════════════
# Main Pipeline
# ══════════════════════════════════════════════════════════

def generate_all_assets(episode: dict, asset_dir: Path) -> dict:
    """Run Gemini + Pillow hybrid pipeline (or legacy path)."""
    asset_dir.mkdir(parents=True, exist_ok=True)
    ep_type = episode.get("type", "standard")
    has_v3_scenes = bool(episode.get("scenes"))

    results = {
        "type": ep_type,
        "asset_dir": str(asset_dir),
        "success": True,
        "fallback_note": None,
        "pipeline": "v3_gemini_pillow_hybrid" if has_v3_scenes else "legacy",
    }

    if has_v3_scenes:
        log("=== v3 Gemini + Pillow Hybrid Pipeline ===")
        log(f"  Step A: Gemini generates text-free visuals (model: {IMAGE_MODEL})")
        log(f"  Step B: Pillow overlays brand text system")
        log(f"  Reference 3D: {REFERENCE_3D.exists()}")
        log(f"  Reference Card: {REFERENCE_CARD.exists()}")

        card_results = generate_all_scene_cards(episode, asset_dir)
        results["cards"] = card_results

        if not all(r["success"] for r in card_results):
            failed = [r["scene_id"] for r in card_results if not r["success"]]
            log(f"Warning: Failed cards: {failed}")
            results["success"] = False

    else:
        log("=== Legacy Pipeline ===")
        log("[1] Generating scene images...")
        scene_results = generate_legacy_scene_images(episode, asset_dir)
        results["scene_images"] = scene_results

    # Type-specific assets: Seedance scene reference images
    if ep_type in ("standard", "hybrid") and episode.get("seedance_scenes"):
        log("[Seedance] Generating scene reference images...")
        scene_results = generate_seedance_scene_images(episode, asset_dir)
        results["seedance_scenes"] = scene_results
        if scene_results and not all(r["success"] for r in scene_results):
            failed = [r["scene_id"] for r in scene_results if not r["success"]]
            log(f"Warning: Failed Seedance scenes: {failed}")
        # NOTE: 影片生成由即夢平台手動提交，此處只生成場景參考圖

    if ep_type in ("ranking", "hybrid"):
        log("[Ranking] Generating cards + TTS...")
        results["ranking_cards"] = generate_ranking_cards(episode, asset_dir)

    if ELEVENLABS_API_KEY:
        log("[TTS] Generating subtitle TTS...")
        results["tts_narration"] = generate_subtitle_tts(episode, asset_dir)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate assets (v3 Gemini + Pillow hybrid)")
    parser.add_argument("episode", help="episode JSON path")
    parser.add_argument("--output-dir", "-o", required=True, help="output directory")
    args = parser.parse_args()

    ep = json.loads(Path(args.episode).read_text(encoding="utf-8"))
    asset_dir = Path(args.output_dir)
    results = generate_all_assets(ep, asset_dir)

    output = json.dumps(results, ensure_ascii=False, indent=2)
    print(output)

    meta_path = asset_dir / "asset_manifest.json"
    meta_path.write_text(output, encoding="utf-8")
    log(f"Asset manifest saved: {meta_path}")

    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
