"""
3D 吉祥物「小靜」生成模組 — asset_gen agent 使用。

v3: 3D smooth matte plastic toy 風格，使用 exact reference image。
每次生成都必須附上 3d_reference.jpg 作為角色參考。
輸出透明背景 PNG，由 composer 階段合成到最終卡面。

用法:
  python scripts/generate_mascot.py <episode.json> --output-dir <assets_dir>

環境變數:
  GEMINI_API_KEY — Gemini API key
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CHARACTER_PATH = BASE / "characters" / "mascot" / "character.json"
REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference.jpg"
MASCOT_3D_SPEC = BASE / "configs" / "mascot_3d_spec.json"

GEMINI_API_KEY = os.environ.get("GEMINI_IMAGE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL_PRIMARY = "gemini-3.1-flash-image-preview"
IMAGE_MODEL_FALLBACK = "gemini-2.5-flash-image"
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", IMAGE_MODEL_PRIMARY)


def log(msg: str):
    print(f"[mascot-3d] {msg}", file=sys.stderr)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_character() -> dict:
    return load_json(CHARACTER_PATH)


def load_mascot_spec() -> dict:
    if MASCOT_3D_SPEC.exists():
        return load_json(MASCOT_3D_SPEC)
    return {}


def build_3d_mascot_prompt(character: dict, expression_key: str, pose_key: str,
                           outfit_key: str = "apron", prop: str = "") -> str:
    """Build prompt for 3D mascot generation with transparent background."""
    expr = character.get("expressions", {}).get(expression_key, {})
    expression_fragment = expr.get("prompt_fragment", "gentle warm smile")

    outfit = character.get("outfit", {}).get("options", {}).get(outfit_key, {})
    outfit_fragment = outfit.get("prompt_fragment", "wearing sage green apron with small white bowl-leaf icon on chest")

    # Pose description from mascot_3d_spec
    spec = load_mascot_spec()
    pose_desc = ""
    for p in spec.get("pose_family", []):
        if p.get("id") == pose_key:
            pose_desc = p.get("description", "")
            break

    negative = character.get("negative_prompt", "")

    prompt = f"""Generate a 3D character matching EXACTLY the reference image provided.

Character: 小靜 (Taiwanese leopard cat mascot)
Style: Smooth matte plastic toy figure, like a premium vinyl collectible (Pop Mart quality)
Material: Low gloss matte plastic, no fur texture, no pores, very soft shadows

Identity (MUST match reference exactly):
- Warm yellow-brown body with round dark spots (NOT stripes)
- Cream/off-white belly and cheeks
- Two thick white vertical stripes on forehead
- Black ears with tiny white spots on back
- Big round dark brown eyes with white highlight
- Small brick-pink nose
- {outfit_fragment}

Expression: {expression_fragment}
Pose: {pose_desc}
"""
    if prop:
        prompt += f"Holding in one paw: {prop} (simplified, matching the 3D toy style)\n"

    prompt += f"""
Output requirements:
- Pure white background (for transparent PNG extraction)
- Full body visible, character centered
- Studio softbox lighting, front-top slightly left
- Subtle warm rim light
- Character occupies 80-90% of frame height
- NO text, NO watermark, NO additional characters
- Single character only — exactly ONE mascot

Negative: {negative}, text, multiple characters, realistic fur, glossy material, harsh shadows"""

    return prompt


def build_closing_prompt(character: dict) -> str:
    """Build prompt for closing card mascot — fixed goodbye expression."""
    return build_3d_mascot_prompt(
        character,
        expression_key="goodbye",
        pose_key="greet_viewer",
        outfit_key="apron",
        prop=""
    )


def _call_gemini_image(prompt: str, model: str, contents_parts: list = None,
                       max_retries: int = 3) -> bytes | None:
    """Call Gemini image API with fallback, return image bytes or None."""
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
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())

            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    if len(img_bytes) > 10 * 1024:
                        return img_bytes
                    log(f"Image too small, retrying...")

            log(f"No image in response ({model}, attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            code = e.code
            log(f"HTTP {code} ({model}, attempt {attempt + 1}): {body}")
            if code in (503, 429) and model == IMAGE_MODEL_PRIMARY:
                log(f"{model} unavailable, falling back to {IMAGE_MODEL_FALLBACK}")
                return _call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, contents_parts, max_retries)
        except Exception as e:
            log(f"Error ({model}, attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1 and model == IMAGE_MODEL_PRIMARY:
                log(f"{model} failed, falling back to {IMAGE_MODEL_FALLBACK}")
                return _call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, contents_parts, max_retries)

        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    return None


def generate_3d_mascot(prompt: str, output_path: Path, max_retries: int = 3) -> bool:
    """Generate 3D mascot image using Gemini with exact reference."""
    if not GEMINI_API_KEY:
        log("Error: GEMINI_API_KEY not set")
        return False

    contents_parts = []

    # Always attach 3D reference image
    if REFERENCE_3D.exists():
        ref_bytes = REFERENCE_3D.read_bytes()
        ref_b64 = base64.b64encode(ref_bytes).decode()
        contents_parts.append({"text": "Use this image as the EXACT character reference. The generated character MUST look identical to this reference — same face, markings, material, apron, proportions:"})
        contents_parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": ref_b64,
            }
        })
    else:
        log("Warning: 3D reference image not found, generating without reference")

    contents_parts.append({"text": prompt})

    img_bytes = _call_gemini_image(prompt, IMAGE_MODEL, contents_parts, max_retries)
    if not img_bytes:
        return False

    output_path.write_bytes(img_bytes)
    log(f"Generated: {output_path.name} ({len(img_bytes) / 1024:.0f}KB)")
    return True


def _overlay_endcard_text(endcard_path: Path):
    """Overlay brand text on closing card using Pillow."""
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        log("Pillow not installed, skipping text overlay")
        return

    img = PILImage.open(str(endcard_path)).convert("RGBA")
    # Center-crop to 1080x1920
    target_w, target_h = 1080, 1920
    if img.size != (target_w, target_h):
        iw, ih = img.size
        target_ratio = target_w / target_h
        img_ratio = iw / ih
        if img_ratio > target_ratio:
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        elif img_ratio < target_ratio:
            new_h = int(iw / target_ratio)
            top = (ih - new_h) // 2
            img = img.crop((0, top, iw, top + new_h))
        img = img.resize((target_w, target_h), PILImage.LANCZOS)

    # Bottom gradient mask
    text_zone_h = int(target_h * 0.28)
    gradient = PILImage.new("RGBA", (target_w, text_zone_h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for row in range(text_zone_h):
        alpha = int(90 * (row / text_zone_h))
        gdraw.line([(0, row), (target_w, row)], fill=(246, 241, 231, alpha))
    img.paste(gradient, (0, target_h - text_zone_h), gradient)

    draw = ImageDraw.Draw(img)

    try:
        font_brand = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", 96)
        font_sub = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 36)
    except OSError:
        font_brand = ImageFont.load_default()
        font_sub = font_brand

    brand = "時時靜好"
    sub_text = "我們下次見"

    # Brand text position
    brand_bbox = draw.textbbox((0, 0), brand, font=font_brand)
    bw = brand_bbox[2] - brand_bbox[0]
    bh = brand_bbox[3] - brand_bbox[1]
    bx = (target_w - bw) // 2
    by = int(target_h * 0.76)

    # Shadow
    shadow_layer = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.text((bx + 2, by + 3), brand, font=font_brand, fill=(60, 30, 10, 80))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(5))
    img = PILImage.alpha_composite(img, shadow_layer)

    draw = ImageDraw.Draw(img)
    # Brand text in olive dark
    draw.text((bx, by), brand, font=font_brand, fill=(78, 85, 56, 255))

    # Separator
    line_y = by + bh + 20
    line_w = 140
    line_x = (target_w - line_w) // 2
    draw.line([(line_x, line_y), (line_x + line_w, line_y)],
              fill=(196, 168, 130, 160), width=2)

    # Subtitle
    sub_bbox = draw.textbbox((0, 0), sub_text, font=font_sub)
    sw = sub_bbox[2] - sub_bbox[0]
    sx = (target_w - sw) // 2
    sy = line_y + 22
    draw.text((sx, sy), sub_text, font=font_sub, fill=(78, 85, 56, 180))

    img.convert("RGB").save(str(endcard_path), quality=95)
    log("Closing card text overlaid (brand design)")


def generate_mascot_assets(episode: dict, output_dir: Path) -> dict:
    """Generate 3D mascot assets based on episode JSON (v3 mascot_strategy or legacy mascot)."""
    # Support both v3 mascot_strategy and legacy mascot field
    strategy = episode.get("mascot_strategy", {})
    legacy = episode.get("mascot", {})

    if not strategy and not legacy:
        log("No mascot_strategy or mascot in episode JSON, skipping")
        return {"success": True, "skipped": True}

    character = load_character()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {"success": True}

    # Determine expression and pose
    presence = strategy.get("presence", "both")
    opening_expr = strategy.get("opening_expression",
                                legacy.get("thumbnail", {}).get("expression", "thinking"))
    opening_pose = strategy.get("opening_pose", "hug_object_side")
    outfit = strategy.get("outfit", legacy.get("outfit", "apron"))
    prop = strategy.get("prop", legacy.get("prop", ""))

    # Cover mascot (transparent bg)
    if presence in ("opening_only", "both"):
        thumb_path = output_dir / "mascot_cover.png"
        if not thumb_path.exists():
            log(f"Generating cover mascot: expression={opening_expr}, pose={opening_pose}")
            prompt = build_3d_mascot_prompt(character, opening_expr, opening_pose, outfit, prop)
            ok = generate_3d_mascot(prompt, thumb_path)
            results["mascot_cover"] = str(thumb_path) if ok else None
            if not ok:
                results["success"] = False
        else:
            log(f"Cover mascot exists: {thumb_path.name}")
            results["mascot_cover"] = str(thumb_path)

    # Closing mascot
    if presence in ("closing_only", "both"):
        endcard_path = output_dir / "mascot_closing.png"
        if not endcard_path.exists():
            log("Generating closing mascot: expression=goodbye, pose=greet_viewer")
            prompt = build_closing_prompt(character)
            ok = generate_3d_mascot(prompt, endcard_path)
            if ok:
                _overlay_endcard_text(endcard_path)
            results["mascot_closing"] = str(endcard_path) if ok else None
            if not ok:
                results["success"] = False
            time.sleep(2)
        else:
            log(f"Closing mascot exists: {endcard_path.name}")
            results["mascot_closing"] = str(endcard_path)

    # Legacy compatibility
    if "mascot_cover" in results:
        results["mascot_thumbnail"] = results["mascot_cover"]
    if "mascot_closing" in results:
        results["mascot_endcard"] = results["mascot_closing"]

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate 3D mascot assets")
    parser.add_argument("episode", help="episode JSON path")
    parser.add_argument("--output-dir", "-o", required=True, help="output directory")
    args = parser.parse_args()

    ep = json.loads(Path(args.episode).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    results = generate_mascot_assets(ep, output_dir)

    print(json.dumps(results, ensure_ascii=False, indent=2))
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
