"""
EP13 抗發炎飲食 — 直接 Gemini 生圖（含文字），不走 Pillow 合成。
用法: python gen_cards_direct.py
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
EPISODE_PATH = BASE / "test_output" / "episode_ep13_anti_inflammatory.json"
OUTPUT_DIR = Path(__file__).resolve().parent
REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
REFERENCE_CARD = BASE / "characters" / "mascot" / "3d_main_card_reference.jpg"
CHARACTER_JSON = BASE / "characters" / "mascot" / "character.json"

# Load API key from .env
ENV_PATH = BASE / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_IMAGE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL = "gemini-3.1-flash-image-preview"

def log(msg):
    print(f"[gen] {msg}", file=sys.stderr)

def call_gemini(prompt: str, ref_parts: list = None, max_retries: int = 3) -> bytes | None:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    parts = list(ref_parts or [])
    parts.append({"text": prompt})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
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
                    if len(img_bytes) > 5 * 1024:
                        return img_bytes
                    log(f"  Image too small ({len(img_bytes)}B), retrying...")

            log(f"  No image in response (attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} (attempt {attempt + 1}): {body}")
        except Exception as e:
            log(f"  Error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            time.sleep(5 * (attempt + 1))

    return None


def build_ref_parts(need_mascot: bool) -> list:
    parts = []
    if need_mascot and REFERENCE_3D.exists():
        ref_b64 = base64.b64encode(REFERENCE_3D.read_bytes()).decode()
        parts.append({"text": "CHARACTER REFERENCE — the 3D mascot 小靜 must look EXACTLY like this (same face, spots not stripes, matte plastic, green apron, proportions):"})
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": ref_b64}})

    if REFERENCE_CARD.exists():
        card_b64 = base64.b64encode(REFERENCE_CARD.read_bytes()).decode()
        parts.append({"text": "STYLE REFERENCE — match this visual quality, composition style, and warm color palette (cream #F6F1E7, sage #A8B88A, olive #4E5538, brown #3B2A1F):"})
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": card_b64}})

    return parts


GLOBAL_STYLE = (
    "Style: 75% photorealistic + 25% 3D elements. "
    "Canvas: 1080x1920 (9:16 vertical). "
    "Color palette: cream #F6F1E7, sage green #A8B88A, olive dark #4E5538, brown #3B2A1F. "
    "Warm natural lighting. NO neon, NO high-saturation red, NO pure white background. "
    "Text must be in 繁體中文 (Traditional Chinese), large and readable. "
    "Typography: bold sans-serif for headlines, clean and high contrast against background. "
)


def build_prompt(scene: dict, episode: dict) -> str:
    role = scene["scene_role"]
    vtype = scene["visual_type"]
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "")
    badge = scene.get("badge_text", "")
    source_badge = scene.get("source_badge_text", "")
    has_mascot = scene.get("mascot_presence", False)

    prompt = f"{GLOBAL_STYLE}\n\n"

    if vtype == "poster_cover":
        prompt += (
            f"Create a stunning vertical poster card (9:16) for a health YouTube Short.\n"
            f"HEADLINE (large, bold, top area): 「{main_text}」\n"
            f"SUBHEADLINE (smaller, below headline): 「{sub_text}」\n"
            f"HERO VISUAL (center-bottom area): {hero}\n"
            f"BACKGROUND: {bg}\n"
        )
        if badge:
            prompt += f"TOP-RIGHT BADGE: sage green rounded rectangle with text「{badge}」\n"
        if has_mascot:
            expr = scene.get("mascot_expression", "default")
            pose = scene.get("mascot_pose", "hug_object_side")
            interaction = scene.get("mascot_interaction_mode", "")
            prompt += (
                f"\n3D MASCOT 小靜 (Taiwanese leopard cat, smooth matte plastic toy, Pop Mart style):\n"
                f"- Expression: {expr}, Pose: {pose}\n"
                f"- Interaction: {interaction}\n"
                f"- Must match the reference image EXACTLY (spots not stripes, white forehead lines, sage green apron)\n"
                f"- Small size relative to hero object (supporting role, not dominant)\n"
            )

    elif vtype == "comparison_card":
        prompt += (
            f"Create a clean comparison infographic card (9:16 vertical).\n"
            f"HEADLINE (large, bold, top): 「{main_text}」\n"
            f"SUBHEADLINE: 「{sub_text}」\n"
            f"VISUAL CONTENT: {hero}\n"
            f"BACKGROUND: {bg}\n"
        )
        if source_badge:
            prompt += f"BOTTOM SOURCE BADGE: sage green bar with text「{source_badge}」\n"

    elif vtype == "evidence_card":
        prompt += (
            f"Create an evidence/data card (9:16 vertical) with authoritative feel.\n"
            f"HEADLINE (large, bold): 「{main_text}」\n"
            f"SUBHEADLINE: 「{sub_text}」\n"
            f"DATA VISUAL: {hero}\n"
            f"BACKGROUND: {bg}\n"
        )
        if source_badge:
            prompt += f"SOURCE BADGE: 「{source_badge}」\n"

    elif vtype == "safety_reminder":
        prompt += (
            f"Create a warm, reassuring reminder card (9:16 vertical).\n"
            f"HEADLINE (large, friendly): 「{main_text}」\n"
            f"SUBHEADLINE: 「{sub_text}」\n"
            f"VISUAL: {hero}\n"
            f"BACKGROUND: {bg}\n"
            f"Mood: encouraging, not alarmist. Warm morning light.\n"
        )

    elif vtype == "brand_closing":
        prompt += (
            f"Create a warm brand closing card (9:16 vertical).\n"
            f"BRAND NAME (large, centered): 「{main_text}」\n"
            f"TAGLINE: 「{sub_text}」\n"
            f"BACKGROUND: {bg}\n"
        )
        if has_mascot:
            interaction = scene.get("mascot_interaction_mode", "")
            prompt += (
                f"\n3D MASCOT 小靜 (Taiwanese leopard cat, smooth matte plastic toy):\n"
                f"- Expression: goodbye (sweet smile, waving)\n"
                f"- {interaction}\n"
                f"- Must match reference EXACTLY\n"
            )

    # Universal prohibitions
    do_not = scene.get("do_not_include", [])
    if do_not:
        prompt += f"\nDO NOT INCLUDE: {', '.join(do_not)}\n"

    prompt += (
        "\nIMPORTANT RULES:\n"
        "- All text MUST be 繁體中文 (Traditional Chinese)\n"
        "- Text must be large enough for mobile viewing (elderly audience)\n"
        "- CRITICAL: ALL text (headlines, subheadlines, badges, labels) must be placed in the TOP 80% of the image. "
        "The BOTTOM 20% of the image must have NO text at all (it will be covered by YouTube Shorts title). "
        "Background visuals and objects in the bottom 20% are fine, just no text.\n"
        "- Maximum 1 mascot per image (if any)\n"
        "- Keep composition clean and not busy\n"
        "- No watermarks, no English text, no logos\n"
    )

    return prompt


def main():
    if not GEMINI_API_KEY:
        log("ERROR: No GEMINI_API_KEY found in .env or environment")
        sys.exit(1)

    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    scenes = episode["scenes"]

    log(f"Generating {len(scenes)} cards with Gemini ({IMAGE_MODEL})")
    log(f"Output: {OUTPUT_DIR}")

    results = []
    for scene in scenes:
        sid = scene["scene_id"]
        role = scene["scene_role"]
        vtype = scene["visual_type"]
        has_mascot = scene.get("mascot_presence", False)

        log(f"\nCard {sid} ({role}/{vtype}, mascot={has_mascot})...")

        prompt = build_prompt(scene, episode)
        ref_parts = build_ref_parts(need_mascot=has_mascot)

        img_bytes = call_gemini(prompt, ref_parts)
        if img_bytes:
            out_path = OUTPUT_DIR / f"card_{sid}_{role}.png"
            out_path.write_bytes(img_bytes)
            log(f"  OK: {out_path.name} ({len(img_bytes)/1024:.0f}KB)")
            results.append({"scene_id": sid, "path": str(out_path.name), "success": True})
        else:
            log(f"  FAILED: card {sid}")
            results.append({"scene_id": sid, "path": None, "success": False})

        # Rate limit spacing
        time.sleep(3)

    success_count = sum(1 for r in results if r["success"])
    log(f"\nDone: {success_count}/{len(scenes)} cards generated")

    manifest = {"episode": 13, "model": IMAGE_MODEL, "cards": results}
    (OUTPUT_DIR / "card_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
