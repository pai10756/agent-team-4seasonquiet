#!/usr/bin/env python3
"""Generate EP53 Tea Host (茶姐姐) character turnaround card — same format as EP09.

Produces:
  1. character_turnaround.png — 4-angle turnaround (front, 3/4 left, side profile, 3/4 back) + 4 face close-ups
  2. face_reference.jpg — single hero portrait for Seedance face-lock

Uses 0331 card_main as face reference to maintain character consistency.
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

# Load .env
env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
IMAGE_MODEL = "gemini-3.1-flash-image-preview"

# Reference images (face source)
REF_0331 = BASE / "card_main_0331.jpg"
REF_0401 = BASE / "0401_card_main_hanfu.jpg"
# EP09 turnaround as format reference
EP09_TURNAROUND = BASE / "test_output" / "seedance_mediterranean" / "character_turnaround_v4.png"

OUTPUT_DIR = BASE / "characters" / "ep53_tea_host"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(f"[ep53_char] {msg}", file=sys.stderr, flush=True)


def call_gemini(parts, max_retries=5):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
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
                    log(f"  Image too small ({len(img_bytes)} bytes), retrying...")

            log(f"  No image in response (attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} (attempt {attempt + 1}): {body}")
            if e.code == 503:
                wait = 10 * (attempt + 1)
                log(f"  503 — waiting {wait}s...")
                time.sleep(wait)
                continue
        except Exception as e:
            log(f"  Error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    return None


def load_ref(path, label):
    if path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode()
        mime = "image/png" if str(path).endswith(".png") else "image/jpeg"
        log(f"  Loaded reference: {path.name}")
        return [
            {"text": label},
            {"inlineData": {"mimeType": mime, "data": b64}},
        ]
    else:
        log(f"  WARNING: {path.name} not found")
        return []


# ── Card 1: Character Turnaround (same layout as EP09 v4) ──

TURNAROUND_PROMPT = """Create a character turnaround reference sheet for video production. Use the EXACT same layout as the FORMAT REFERENCE image.

LAYOUT (single 3:2 HORIZONTAL composite image, clean white/light gray studio background):
Left side (~40% width): TWO full-body shots stacked vertically (head to bare feet, standing on white floor):
  TOP: Front View — standing straight, relaxed posture, arms at sides, gentle smile, looking at camera
  BOTTOM: 3/4 Left View — body turned 45 degrees left, face still partly visible, same relaxed posture

Right side (~60% width): SIX head/shoulder close-up portraits in a 2x3 grid (2 columns × 3 rows):
  Row 1 LEFT: Front face — gentle smile, direct eye contact
  Row 1 RIGHT: 3/4 Left View — head turned 45 degrees left
  Row 2 LEFT: Warm genuine smile — eyes slightly crinkled, friendly, happy
  Row 2 RIGHT: Side Profile (Left) — full 90-degree left profile, showing nose bridge and jawline
  Row 3 LEFT: Surprised expression — slightly raised brows, mouth slightly open
  Row 3 RIGHT: Thinking expression — eyes looking slightly up, contemplative

CHARACTER IDENTITY (must match the FACE REFERENCE images EXACTLY — same person):
- Beautiful East Asian female, age 23-26
- Gentle square jaw, soft contour, delicate bone structure
- Gentle downturned almond eyes, soft double eyelids, dark brown iris
- Fluffy natural textured brows, slightly arched
- Higher nose bridge, refined, petite tip
- Subtle pout, soft gradient glossy lips, natural pink-peach tone
- Porcelain-clear dewy glass skin, warm undertone
- Long dark chocolate brown hair in loose natural waves, center-parted
- Korean editorial natural makeup: dewy glass skin, soft peach blush, gradient glossy lips

OUTFIT:
- Cream / off-white oversized chunky knit sweater (#F5F0E8), V-neck or slightly off-shoulder, relaxed fit
- Light khaki / beige casual trousers, relaxed straight fit
- Bare feet (for full body shots)
- Small gold stud earrings only, no other accessories

CRITICAL RULES:
- ALL views must be the SAME person with IDENTICAL face, hair, makeup, and outfit
- Clean white/very light gray studio background, no props, no furniture
- Even soft studio lighting, no harsh shadows
- Photorealistic quality, NOT illustration, NOT cartoon
- No text labels on the image (unlike the format reference which has labels — omit them)
- No watermarks, no logos, no AI marks
"""


# ── Card 2: Face Reference (single hero portrait) ────────

FACE_REFERENCE_PROMPT = """Create a single portrait photograph for use as a face-lock reference in AI video generation.

COMPOSITION: Upper body portrait (head, shoulders, upper chest), centered, vertical 9:16 ratio (1080x1920).

CHARACTER (must match FACE REFERENCE images EXACTLY — same person):
- Beautiful East Asian female, age 23-26
- Gentle square jaw, soft contour, delicate bone structure
- Gentle downturned almond eyes, soft double eyelids, dark brown iris
- Fluffy natural textured brows, slightly arched
- Higher nose bridge, refined, petite tip
- Subtle pout lips, natural pink-peach tone
- Porcelain-clear dewy glass skin, warm undertone
- Long dark chocolate brown hair in loose natural waves, center-parted, tucked behind one ear
- Korean editorial natural makeup

OUTFIT: Cream off-white oversized knit sweater (#F5F0E8)

EXPRESSION: Serene, contemplative, quiet confidence — chin resting lightly on interlaced fingers, gazing softly at camera

LIGHTING: Warm golden-hour soft light from left, gentle fill from right, slight backlight rim glow on hair edges
BACKGROUND: Clean warm cream tone, very soft, no distracting elements, slight warm bokeh
COLOR GRADE: Warm cream/amber, low saturation, slight film grain

STYLE: Photorealistic editorial portrait, Sony A7IV, 85mm f/1.4, f/2.0, shallow DOF

FORBIDDEN: No watermarks, no logos, no text, no AI marks, no extra people, no cartoon style
"""


def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY or GOOGLE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    cards = [
        {
            "name": "Character Turnaround",
            "prompt": TURNAROUND_PROMPT,
            "output": "character_turnaround.png",
            "refs": [
                (REF_0331, "FACE REFERENCE — the character must have THIS exact face, hair, and skin:"),
                (REF_0401, "SAME PERSON different styling — note the consistent facial features:"),
                (EP09_TURNAROUND, "FORMAT REFERENCE — use this EXACT layout (2 full-body on top row, 4 face close-ups on bottom rows). Copy this grid arrangement but with the tea host character in cream knit sweater instead:"),
            ],
        },
        {
            "name": "Face Reference Portrait",
            "prompt": FACE_REFERENCE_PROMPT,
            "output": "face_reference.jpg",
            "refs": [
                (REF_0331, "FACE REFERENCE — the character must look EXACTLY like this woman:"),
                (REF_0401, "SAME PERSON — consistent facial features across different styles:"),
            ],
        },
    ]

    results = []
    for card in cards:
        log(f"\n{'='*50}")
        log(f"Generating: {card['name']}")
        log(f"{'='*50}")

        parts = []
        for ref_path, label in card["refs"]:
            parts.extend(load_ref(ref_path, label))
        parts.append({"text": card["prompt"]})

        img_bytes = call_gemini(parts)
        if img_bytes:
            out_path = OUTPUT_DIR / card["output"]
            out_path.write_bytes(img_bytes)
            log(f"OK: {out_path} ({len(img_bytes):,} bytes)")
            results.append((card["name"], out_path))
        else:
            log(f"FAILED: {card['name']}")
            results.append((card["name"], None))

        time.sleep(5)

    log("\n" + "=" * 50)
    log("RESULTS:")
    for name, path in results:
        status = f"OK -> {path}" if path else "FAILED"
        log(f"  {name}: {status}")


if __name__ == "__main__":
    main()
