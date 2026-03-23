"""Test: Generate Card 01 (hook) via Gemini API with mascot reference."""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "test_output" / "card01_gemini"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("GEMINI_IMAGE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set")
    sys.exit(1)

MODEL = "gemini-3.1-flash-image-preview"
REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference.jpg"

PROMPT = """A vertical 9:16 health education poster card (1080x1920).

Top half: Large bold Chinese headline "別再走一萬步了！" in dark olive color (#4E5538), poster-style typography, dominant and easy to read. Below it smaller subtitle "這個數字，根本不是科學建議" in brown (#3B2A1F).

Center: A large realistic digital pedometer/step counter showing "10,000" on its screen, with a bold red X crossing out the number. The pedometer sits on a wooden park bench.

Background: Soft morning park scene with walking path and trees, golden hour lighting, warm cream (#F6F1E7) and sage green (#A8B88A) color palette. 75% photorealistic, warm and inviting.

Bottom-right corner: A small cute 3D mascot exactly matching the attached reference image — smooth matte plastic leopard cat toy, wearing a bright sage green mini running vest with white trim edges and a tiny shoe icon badge on the chest, replacing the usual apron. A small sweatband on the head. Sporty and active look, but same matte plastic toy material as reference. Must match the reference image's head-to-body ratio, spotted pattern (not stripes), white forehead line, white ear patches exactly. Surprised expression, pointing upward. Pop Mart / Sonny Angel quality. Small relative to the pedometer (sidekick role).

Style: Clean, modern health infographic poster. One clear message. No human faces. Warm, trustworthy, mature tone. NOT cheap, NOT alarmist."""

def main():
    # Build parts with reference image
    parts = []

    if REFERENCE_3D.exists():
        ref_b64 = base64.b64encode(REFERENCE_3D.read_bytes()).decode()
        parts.append({"text": "CHARACTER REFERENCE — the 3D mascot must look EXACTLY like this (same face, markings, matte plastic material, proportions):"})
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": ref_b64}})
    else:
        print(f"WARNING: Reference image not found: {REFERENCE_3D}")

    parts.append({"text": PROMPT})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

    print(f"Calling Gemini ({MODEL})...")
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
                out_path = OUTPUT_DIR / "card01_gemini.png"
                out_path.write_bytes(img_bytes)
                print(f"OK — saved to {out_path} ({len(img_bytes)} bytes)")
                return
            elif "text" in part:
                print(f"Text response: {part['text'][:200]}")

        print("ERROR: No image in response")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        print(f"HTTP {e.code}: {body}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
