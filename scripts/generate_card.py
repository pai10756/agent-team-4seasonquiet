"""
Card Generator v4 — Single-prompt Gemini full card generation.

Reads an episode JSON scene, builds a comprehensive prompt incorporating
brand tokens + mascot reference + layout + text, and sends to Gemini
to generate the complete card in one shot (no Pillow composition).

Usage:
  python scripts/generate_card.py <episode.json> --scene 01 [--output-dir <dir>]
  python scripts/generate_card.py <episode.json> --all [--output-dir <dir>]

Environment:
  GEMINI_API_KEY — Gemini API key
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL = "gemini-3.1-flash-image-preview"
IMAGE_MODEL_FALLBACK = "gemini-3-pro-image-preview"  # fallback: 不同配額路徑，429 時自動切換

REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
REFERENCE_CARD = BASE / "characters" / "mascot" / "3d_main_card_reference.jpg"

# Brand constants
PALETTE = {
    "cream": "#F6F1E7",
    "sage": "#A8B88A",
    "olive_dark": "#4E5538",
    "brown": "#3B2A1F",
}


def log(msg: str):
    print(f"[card_gen] {msg}", file=sys.stderr)


# ── Gemini API ───────────────────────────────────────────

def call_gemini(parts: list, max_retries: int = 3) -> bytes | None:
    """Call Gemini image API with auto-fallback: flash → pro if 429."""
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

    for model in [IMAGE_MODEL, IMAGE_MODEL_FALLBACK]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        for attempt in range(max_retries):
            try:
                start = time.time()
                req = urllib.request.Request(url, data=payload,
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                elapsed = time.time() - start

                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        img_bytes = base64.b64decode(part["inlineData"]["data"])
                        if len(img_bytes) > 10 * 1024:
                            log(f"  OK ({len(img_bytes)//1024}KB, {elapsed:.0f}s, {model})")
                            return img_bytes
                        log(f"  Image too small ({len(img_bytes)} bytes), retrying...")
                log(f"  No image (attempt {attempt+1}, {elapsed:.0f}s, {model})")
            except urllib.error.HTTPError as e:
                code = e.code
                log(f"  HTTP {code} (attempt {attempt+1}, {model})")
                if code == 429:
                    log(f"  → 429 on {model}, trying fallback...")
                    break  # skip to next model
                if code == 503:
                    wait = 15 * (attempt + 1)
                    log(f"  503 — waiting {wait}s...")
                    time.sleep(wait)
                    continue
            except Exception as e:
                log(f"  Error (attempt {attempt+1}): {e}")

            if attempt < max_retries - 1:
                time.sleep(12)

    return None


# ── Reference image parts ────────────────────────────────

def _compress_ref_image(path: Path, max_size: int = 800) -> str:
    """Compress reference image to ~20KB base64 to avoid API quota issues."""
    from PIL import Image
    import io
    img = Image.open(path)
    ratio = min(max_size / img.width, max_size / max(img.height, 1))
    if ratio < 1:
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    log(f"  Compressed {path.name}: {path.stat().st_size:,} → {len(buf.getvalue()):,} bytes")
    return base64.b64encode(buf.getvalue()).decode()


def build_reference_parts(include_card_ref: bool = True) -> list:
    """Build inlineData parts for mascot + card quality reference images."""
    parts = []
    if REFERENCE_3D.exists():
        ref_b64 = _compress_ref_image(REFERENCE_3D)
        parts.append({"text": (
            "MASCOT REFERENCE — the 3D mascot must look EXACTLY like this "
            "(same face, markings, matte plastic material, green apron, proportions):"
        )})
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": ref_b64}})
    else:
        log("WARNING: 3d_reference.jpg not found")

    if include_card_ref and REFERENCE_CARD.exists():
        card_b64 = _compress_ref_image(REFERENCE_CARD)
        parts.append({"text": (
            "CARD QUALITY REFERENCE — the output should match this level of "
            "quality, composition, and visual polish:"
        )})
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": card_b64}})

    return parts


# ── Prompt builders per card type ────────────────────────

BRAND_STYLE_BLOCK = f"""生成一張 1080x1920 的 9:16 直式圖卡。
品牌視覺系統（必須嚴格遵守）：
- 背景：儘量使用真實攝影照片填滿整張圖卡，搭配適度的圖表或插圖
- 標題：大號粗體繁體中文，深橄欖色 {PALETTE['olive_dark']}，必須是畫面中最大最醒目的元素
- 副標題：較小字，棕色 {PALETTE['brown']}，在標題下方
- 徽章：鼠尾草綠 {PALETTE['sage']} 圓角矩形，右上角區域
- 色盤：米白 {PALETTE['cream']}、鼠尾草綠 {PALETTE['sage']}、深橄欖 {PALETTE['olive_dark']}、棕色 {PALETTE['brown']}
- 整體風格：溫暖、可信賴、成熟、乾淨，不廉價、不恐嚇、不幼稚
- 底部 20% 是安全區，不放文字，但可以有背景圖片延伸，不要刻意留白底色
- 在照片背景上的文字加白色半透明陰影或深色底條，確保清晰可讀
"""

NEGATIVE_BLOCK = """
禁止出現以下任何元素：
- 不要浮水印、商標、簽名
- 不要星星符號、閃光、鑽石形狀、角落裝飾點
- 不要 SynthID 標記、AI 浮水印、角落小圖示
- 不要重複的吉祥物（每張圖最多一隻）
- 不要霓虹色、強烈陰影、純白背景
- 不要漫畫風格效果、漸層覆蓋
- 絕對不要出現任何英文文字
- 不要手機介面、導航列、按鈕元素
- 圖片四角和邊緣必須完全乾淨
"""

MASCOT_IDENTITY_BLOCK = """
吉祥物「小靜」身份規格（3D 光滑磨砂塑膠玩具，Pop Mart 品質）：
- 台灣石虎，大圓頭，小身體，頭身比約 1:1
- 溫暖黃棕色身體，帶有圓形深棕色斑點（不是條紋，不是虎斑）
- 額頭有兩條明顯的粗白色垂直條紋
- 黑色耳尖，耳後有小白斑
- 粉紅色三角形鼻子，大圓深棕色眼睛帶白色高光
- 光滑磨砂塑膠材質，低光澤，無毛皮質感
- 預設穿著鼠尾草綠色圍裙，胸前有白色碗葉圖示
- 必須與附上的參考圖完全一致
"""


def build_poster_cover_prompt(scene: dict, episode: dict) -> str:
    """Build complete card prompt for poster_cover (Card 01)."""
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    badge = scene.get("badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "warm kitchen interior, soft natural light")
    has_mascot = scene.get("mascot_presence", False)
    expr = scene.get("mascot_expression", "thinking")
    pose = scene.get("mascot_pose", "hug_object_side")

    prompt = f"""Generate a COMPLETE vertical 9:16 health content card (1080x1920) with ALL text rendered directly on the image.

{BRAND_STYLE_BLOCK}

LAYOUT:
- Top area (top 30%): Large bold Chinese headline text and subtitle, left-aligned with safe margin
- Top-right corner: Badge in sage green rounded shape
- Center-lower area (50-60%): Hero object as the dominant visual element
- Background: {bg}

TEXT TO RENDER ON THE IMAGE (Chinese, Traditional):
- HEADLINE (largest, bold, dark olive {PALETTE['olive_dark']}): 「{main_text}」
- SUBTITLE (smaller, brown {PALETTE['brown']}, below headline): 「{sub_text}」
"""
    if badge:
        prompt += f"- BADGE (top-right, sage green {PALETTE['sage']} rounded rectangle, small text): 「{badge}」\n"

    prompt += f"""
HERO OBJECT: {hero}
The hero object must be realistic, prominently placed, and visually dominant.
"""

    if has_mascot:
        prompt += f"""
MASCOT (ONE only, as sidekick — smaller than hero object, ~20-30% of frame):
{MASCOT_IDENTITY_BLOCK}
- Expression: {expr}
- Pose: {pose}
- Position: beside or slightly behind the hero object
"""

    prompt += NEGATIVE_BLOCK
    return prompt


def build_comparison_card_prompt(scene: dict, episode: dict) -> str:
    """Build complete card prompt for comparison_card (Card 02/03)."""
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    badge = scene.get("badge_text", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")

    prompt = f"""Generate a COMPLETE vertical 9:16 health comparison card (1080x1920) with ALL text rendered directly on the image. ALL text must be in Traditional Chinese (繁體中文). Do NOT use any English text.

{BRAND_STYLE_BLOCK}

LAYOUT:
- Top area: Large bold headline and subtitle
- Center: Split comparison layout with clear visual contrast

TEXT TO RENDER ON THE IMAGE (must be Traditional Chinese 繁體中文, no English):
- HEADLINE (largest, bold, dark olive {PALETTE['olive_dark']}): 「{main_text}」
- SUBTITLE (smaller, brown {PALETTE['brown']}): 「{sub_text}」
"""
    if badge:
        prompt += f"- BADGE (top-right, sage green rounded rectangle): 「{badge}」\n"
    else:
        prompt += "- NO badge in top-right corner. Leave that area empty.\n"

    if source_badge:
        prompt += f"- SOURCE BADGE (bottom area, sage green rounded rectangle, Chinese text): 「{source_badge}」\n"

    prompt += f"""
COMPARISON VISUAL: {hero}

No mascot on this card. Clean infographic style.
All labels, descriptions, and badges on the image MUST be in Traditional Chinese. No English anywhere.
{NEGATIVE_BLOCK}"""
    return prompt


def build_evidence_card_prompt(scene: dict, episode: dict) -> str:
    """Build complete card prompt for evidence_card (Card 04)."""
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "clean minimalist background, cream base")

    prompt = f"""Generate a COMPLETE vertical 9:16 health evidence card (1080x1920) with ALL text rendered directly on the image.

{BRAND_STYLE_BLOCK}

LAYOUT:
- Top area: Large bold headline and subtitle
- Center: Data visualization or evidence presentation
- Bottom-right: Source citation badge

TEXT TO RENDER ON THE IMAGE (Chinese, Traditional):
- HEADLINE (largest, bold, dark olive {PALETTE['olive_dark']}): 「{main_text}」
- SUBTITLE (smaller, brown {PALETTE['brown']}): 「{sub_text}」
"""
    if source_badge:
        prompt += f"- SOURCE BADGE (bottom-right, sage green {PALETTE['sage']} rounded rectangle): 「{source_badge}」\n"

    prompt += f"""
EVIDENCE VISUAL: {hero}
Background: {bg}

No mascot on this card. Clean, authoritative, modern data visualization style.
{NEGATIVE_BLOCK}"""
    return prompt


def build_safety_reminder_prompt(scene: dict, episode: dict) -> str:
    """Build complete card prompt for safety_reminder (Card 05)."""
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "warm morning kitchen table")

    prompt = f"""Generate a vertical 9:16 photograph (1080x1920) with text overlay, styled as a real photograph with professional camera parameters.

PHOTOGRAPHY STYLE:
- Camera: Sony A7IV or Canon R5 equivalent
- Lens: 50mm f/1.8 for natural perspective
- Aperture: f/2.8 — soft bokeh background, sharp subject
- ISO: 200-400, clean and noise-free
- White balance: 5500K warm daylight
- Lighting: soft natural window light from left side, gentle fill light from right, no harsh shadows
- Color grade: warm cream tone, slightly desaturated, Fujifilm Pro 400H film emulation
- Depth of field: shallow, subject in focus, background gently blurred

COMPOSITION (9:16 vertical):
- Top 40% of image: HEADLINE TEXT ZONE — large bold Chinese headline and subtitle, on a clean or slightly blurred background area so text is highly readable. The headline font size must be as large as a movie poster title.
- Lower 40%: Main subject — real food photography, can extend slightly behind text area with blur
- Bottom 20%: Empty/clean (will be covered by YouTube UI)

TEXT OVERLAY ON THE IMAGE (Chinese, Traditional):
- HEADLINE (VERY LARGE, bold, dark olive {PALETTE['olive_dark']}, must occupy at least 25% of image width, with subtle drop shadow for readability. This must be the BIGGEST and most dominant element on the entire image, same size as previous cards): 「{main_text}」
- SUBTITLE (medium size, brown {PALETTE['brown']}, below headline): 「{sub_text}」
"""
    if source_badge:
        prompt += f"- SOURCE BADGE (lower-middle area, sage green rounded rectangle): 「{source_badge}」\n"

    prompt += f"""
SUBJECT: {hero}
SCENE: {bg}

Mood: Warm, peaceful, inviting — like a weekend morning brunch scene in a lifestyle magazine.
The photograph should feel real and tangible, as if shot by a food photographer.
No 3D elements, no mascot, no illustration, no infographic — pure photography with text overlay.
All text must be in Traditional Chinese. No English.
{NEGATIVE_BLOCK}"""
    return prompt


def build_brand_closing_prompt(scene: dict, episode: dict) -> str:
    """Build complete card prompt for brand_closing (Card 06)."""
    main_text = scene.get("on_screen_text_main", "時時靜好")
    sub_text = scene.get("on_screen_text_sub", "我是小靜，我們下次見！")
    bg = scene.get("background_scene", "soft warm gradient background")
    expr = scene.get("mascot_expression", "goodbye")
    pose = scene.get("mascot_pose", "greet_viewer")
    interaction = scene.get("mascot_interaction_mode", "")

    pose_desc = interaction if interaction else f"{pose} — facing viewer, one paw raised waving goodbye, friendly and approachable"

    prompt = f"""Generate a COMPLETE vertical 9:16 brand closing card (1080x1920) with ALL text rendered directly on the image. ALL text must be in Traditional Chinese.

LAYOUT (follow exactly):
- Top center: Brand name 「{main_text}」 in large bold dark olive ({PALETTE['olive_dark']}), must be the LARGEST text on the card
- Below brand name: Tagline 「陪你安心懂健康」 in brown ({PALETTE['brown']}), smaller than brand name
- Center-left: A soft white rounded speech bubble with text 「嗨，我是小靜，我們下次見！」 in brown ({PALETTE['brown']}). The bubble tail points toward the mascot.
- Center to bottom: 3D mascot prominently placed, occupying 50-60% of the frame
- Background: {bg}, with strong bokeh/depth of field effect, dreamy and soft

MASCOT (ONE only, this is the STAR of the card):
{MASCOT_IDENTITY_BLOCK}
- Expression: {expr} — warm gentle smile
- Pose: {pose_desc}
- The mascot should be large, prominent, and centered in the lower portion of the image
- Outfit: sage green apron (default)

IMPORTANT RULES:
- Only render EXACTLY the text specified above. Do NOT add any extra text, labels, buttons, tags, or badges.
- Do NOT add navigation buttons, source links, or category labels at the bottom.
- Do NOT repeat any text that is already shown.
- The bottom fifth of the image should have no text (YouTube UI will cover it).
- No English text anywhere.
- One mascot only, no duplicates.
{NEGATIVE_BLOCK}"""
    return prompt


# ── Prompt router ────────────────────────────────────────

# v5: 使用全中文 prompt builders（防止手機截圖風格+prompt洩露）
# 英文版保留為 fallback，但預設用中文版
try:
    from card_prompts_zh import PROMPT_BUILDERS_ZH
    PROMPT_BUILDERS = PROMPT_BUILDERS_ZH
    log("Using Chinese prompt builders (card_prompts_zh)")
except ImportError:
    PROMPT_BUILDERS = {
        "poster_cover": build_poster_cover_prompt,
        "comparison_card": build_comparison_card_prompt,
        "evidence_card": build_evidence_card_prompt,
        "safety_reminder": build_safety_reminder_prompt,
        "brand_closing": build_brand_closing_prompt,
    }
    log("Fallback to English prompt builders")


def build_prompt_for_scene(episode: dict, scene: dict, prompt_override: str = None) -> list:
    """Build Gemini API parts for a scene. Used by auto_improve_card.py.

    If prompt_override is given, use it instead of the default prompt builder.
    Returns list of parts (reference images + text prompt).
    """
    visual_type = scene.get("visual_type", "evidence_card")
    has_mascot = scene.get("mascot_presence", False)

    if prompt_override:
        prompt_text = prompt_override
    else:
        builder = PROMPT_BUILDERS.get(visual_type, build_comparison_card_prompt)
        prompt_text = builder(scene, episode)

    parts = []
    if has_mascot or visual_type == "brand_closing":
        parts.extend(build_reference_parts(include_card_ref=True))
    parts.append({"text": prompt_text})
    return parts


def generate_card(scene: dict, episode: dict, output_dir: Path) -> Path | None:
    """Generate a single complete card image from a scene definition."""
    scene_id = scene.get("scene_id", "00")
    visual_type = scene.get("visual_type", "evidence_card")
    has_mascot = scene.get("mascot_presence", False)

    log(f"Card {scene_id} ({visual_type}) — building prompt...")

    builder = PROMPT_BUILDERS.get(visual_type)
    if not builder:
        log(f"  Unknown visual_type: {visual_type}, using comparison_card")
        builder = build_comparison_card_prompt

    prompt = builder(scene, episode)

    # Build parts: reference images first, then prompt
    parts = []
    if has_mascot or visual_type == "brand_closing":
        parts.extend(build_reference_parts(include_card_ref=True))
    parts.append({"text": prompt})

    log(f"Card {scene_id} — calling Gemini ({IMAGE_MODEL})...")
    img_bytes = call_gemini(parts)

    if img_bytes:
        out_path = output_dir / f"card{scene_id}.png"
        out_path.write_bytes(img_bytes)
        log(f"Card {scene_id} — OK ({out_path}, {len(img_bytes)} bytes)")
        return out_path
    else:
        log(f"Card {scene_id} — FAILED")
        return None


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate complete cards from episode JSON")
    parser.add_argument("episode_json", help="Path to episode JSON file")
    parser.add_argument("--scene", help="Scene ID to generate (e.g., 01)")
    parser.add_argument("--all", action="store_true", help="Generate all scenes")
    parser.add_argument("--output-dir", "-o", help="Output directory")
    args = parser.parse_args()

    episode_path = Path(args.episode_json)
    if not episode_path.exists():
        print(f"Error: {episode_path} not found", file=sys.stderr)
        sys.exit(1)

    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    scenes = episode.get("scenes", [])

    if not scenes:
        print("Error: No scenes found in episode JSON", file=sys.stderr)
        sys.exit(1)

    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ep_num = episode.get("episode", 0)
        output_dir = BASE / "test_output" / f"cards_ep{ep_num:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    if args.scene:
        # Single scene
        target = [s for s in scenes if s.get("scene_id") == args.scene]
        if not target:
            print(f"Error: Scene {args.scene} not found", file=sys.stderr)
            sys.exit(1)
        generate_card(target[0], episode, output_dir)
    elif args.all:
        # All scenes
        for scene in scenes:
            generate_card(scene, episode, output_dir)
            time.sleep(10)  # Gemini image gen: 10s+ interval to avoid 429
        log("All cards done!")
    else:
        print("Error: Specify --scene <id> or --all", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
