"""
Seedance 影片測試 — 定裝照 + 場景圖生成

主題：飯菜放涼才能進冰箱？
人物：3/22 農民曆風格模特兒（白色針織毛衣）

生成內容：
  1. character_turnaround.png — 多角度定裝照（3:2 橫版，白底網格）
  2. scene_part1.png — Part1 場景底圖（廚房 + 冒蒸氣飯菜）
  3. scene_part2.png — Part2 場景底圖（放進冰箱動作）

用法:
  python scripts/gen_seedance_test.py

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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL_PRIMARY = "gemini-3.1-flash-image-preview"
IMAGE_MODEL_FALLBACK = "gemini-2.5-flash-image"
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", IMAGE_MODEL_PRIMARY)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "test_output" / "seedance_fridge_test"


def log(msg: str):
    print(f"[gen] {msg}", file=sys.stderr)


def call_gemini_image(prompt: str, model: str = None,
                      max_retries: int = 3) -> bytes | None:
    model = model or IMAGE_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
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
                log(f"  Falling back to {IMAGE_MODEL_FALLBACK}")
                return call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, max_retries)
        except Exception as e:
            log(f"  Error ({model}, attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1 and model == IMAGE_MODEL_PRIMARY:
                log(f"  Falling back to {IMAGE_MODEL_FALLBACK}")
                return call_gemini_image(prompt, IMAGE_MODEL_FALLBACK, max_retries)

        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    return None


# ── 人物描述 ──

CHARACTER_DESC = (
    "Beautiful adult Asian female fashion model, age 23 (adult, 20-26). "
    "Face: gentle square face shape, gentle downturned eyes, fluffy textured brows, "
    "higher bridge nose, subtle pout, petite delicate features. "
    "Signature: perfectly clear skin. "
    "Hair: long loose waves, dark chocolate brown. "
    "Makeup: dewy glass skin, soft peach blush, gradient glossy lips. "
    "Realistic editorial makeup, not cartoon. "
    "Outfit: white oversized knit sweater, slightly off-shoulder. "
    "No logos, no loud prints, no streetwear."
)

# ── Prompt 1: 多角度定裝照（3:2 橫版白底） ──

TURNAROUND_PROMPT = (
    "3:2 horizontal character turnaround sheet / model sheet, pure clean white background.\n"
    f"Character: {CHARACTER_DESC}\n\n"
    "Face shape (jawline, cheekbones, chin), eye shape, brow shape, nose bridge and nostrils, "
    "lip thickness and mouth corner shape, age and aura must be strictly consistent across all views. "
    "Hairline and hairstyle must remain consistent. Only ONE character, no face swapping, no facial drift.\n\n"
    "Layout (single composite image, clean grid, unified lighting and color):\n"
    "Left side (~60% width): two large images stacked vertically:\n"
    "1) Full-body front view standing pose (neutral stance, arms relaxed at sides, white knit sweater)\n"
    "2) Full-body 90-degree side view standing pose (neutral stance)\n\n"
    "Right side (~40% width): 2x3 grid of six head close-ups:\n"
    "1) Head front view (neutral expression)\n"
    "2) Head back view (back of head, for hairstyle and head shape consistency)\n"
    "3) Head left 45-degree view (neutral)\n"
    "4) Head right 45-degree view (neutral)\n"
    "5) Expression close-up: happy / warm smile (gentle, inviting)\n"
    "6) Expression close-up: thoughtful / concentrated (slight lip press, focused eyes)\n\n"
    "Quality: high-end realistic studio photography / cinematic portrait quality, "
    "eyes sharp and in focus, real skin micro-texture (pores and fine lines, no airbrushing, no plastic), "
    "consistent exposure and color across all panels, 8K detail, light film grain, "
    "ultra-clean white background, clean soft shadow under feet.\n\n"
    "Hard constraints: NO readable text in the image (no FRONT/SIDE labels), "
    "no subtitles, no logos, no UI overlays, no watermark blocks; "
    "no cartoon or anime style; no extra people; "
    "no deformed fingers / extra limbs / face collapse; "
    "all six small images must show the same face with the same hairline."
)

# ── Prompt 2: Part1 場景底圖（廚房 + 飯菜蒸氣，無人） ──

SCENE_PART1_PROMPT = (
    "Generate a high-quality vertical portrait image (9:16 ratio, 1080x1920). "
    "Empty warm modern home kitchen scene, NO PEOPLE, no human figure.\n"
    "A wooden kitchen countertop with a glass meal prep container filled with freshly cooked "
    "steaming white rice. Steam rises gently and swirls upward from the rice. "
    "A wall clock is visible in the background showing afternoon time.\n"
    "Kitchen details: cream-toned walls, warm wood countertop and cabinets, "
    "soft pendant light overhead, open shelving with sage green ceramic bowls, "
    "a window with soft diffused daylight.\n"
    "Lighting: overcast soft diffused daylight from window, no harsh shadows, "
    "gentle and airy atmosphere. Warm color palette: cream, wood tones, sage green accents.\n"
    "Composition: eye-level, centered on the steaming rice container, "
    "kitchen environment fills the frame, inviting and cozy.\n"
    "Style: lifestyle editorial photography, photorealistic, shallow depth of field.\n"
    "No text, no watermark, no logos, no cartoon elements. Absolutely no people."
)

# ── Prompt 3: Part2 場景底圖（冰箱打開，無人） ──

SCENE_PART2_PROMPT = (
    "Generate a high-quality vertical portrait image (9:16 ratio, 1080x1920). "
    "Empty warm modern home kitchen scene, NO PEOPLE, no human figure.\n"
    "An open stainless steel refrigerator with cool white-blue interior light. "
    "The fridge shelves are neatly organized with fresh vegetables, bottles, and containers. "
    "One shelf at mid-height is clearly empty, ready to receive a container. "
    "A slight cold mist is visible near the fridge opening.\n"
    "Kitchen background: cream-toned walls, warm wood elements, "
    "soft pendant lighting creating warm ambient glow behind the fridge.\n"
    "Lighting: dramatic warm-cool contrast — cool white-blue light from fridge interior "
    "meets warm amber kitchen light from behind. No harsh shadows.\n"
    "Composition: eye-level, slightly angled, fridge door open to the right side, "
    "interior well-lit and inviting.\n"
    "Style: lifestyle editorial photography, photorealistic, shallow depth of field.\n"
    "No text, no watermark, no logos, no cartoon elements. Absolutely no people."
)


def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Set regen_only=True to skip turnaround if it already exists
    turnaround_path = OUTPUT_DIR / "character_turnaround.png"
    regen_only = turnaround_path.exists()

    tasks = []
    if not regen_only:
        tasks.append(("character_turnaround.png", TURNAROUND_PROMPT, "Character turnaround sheet"))
    tasks.extend([
        ("scene_part1.png", SCENE_PART1_PROMPT, "Part1 scene: kitchen + steaming rice (no people)"),
        ("scene_part2.png", SCENE_PART2_PROMPT, "Part2 scene: open fridge (no people)"),
    ])

    for filename, prompt, desc in tasks:
        output_path = OUTPUT_DIR / filename
        log(f"Generating: {desc} ...")

        img_bytes = call_gemini_image(prompt)
        if img_bytes:
            output_path.write_bytes(img_bytes)
            log(f"  Saved: {output_path} ({len(img_bytes) // 1024} KB)")
        else:
            log(f"  FAILED: {desc}")

        time.sleep(5)

    log("Done! Check output in: " + str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
