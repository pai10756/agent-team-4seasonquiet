"""Test: Generate Card 06 (closing) via Gemini API with mascot reference."""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "test_output" / "card06_gemini"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAaVV42BhssBY01VWqr6K7V2JLfGRDD00s")
MODEL = "gemini-3.1-flash-image-preview"
REFERENCE_3D = BASE / "characters" / "mascot" / "3d_reference.jpg"

PROMPT = """A vertical 9:16 brand closing card (1080x1920).

Top-left: Large bold Chinese text "時時靜好" in dark olive (#4E5538), prominent and elegant.
Below it: Subtitle "陪你安心懂健康" in brown (#3B2A1F), warm and reassuring.

Center-bottom: A cute 3D mascot exactly matching the attached reference image — smooth matte plastic leopard cat toy with big round head, small body, spotted pattern (not stripes), white forehead line, white ear patches behind black-tipped ears, pink nose. Same matte plastic toy material as reference. Pop Mart / Sonny Angel quality.

Outfit for this card: wearing a bright sage green mini running vest with white trim edges and a tiny shoe icon badge on the chest (replacing the usual apron). A small white sporty sweatband/headband on the head. Wearing tiny cute running shoes on the feet. Sporty and active look.

Pose: Waving goodbye to the viewer with one hand raised and a warm gentle smile. The mascot is prominent (40-50% of frame), standing on a natural park path surface.

Speech bubble: A soft white rounded speech bubble coming from the mascot, containing the Chinese text "我是小靜，我們下次見！" in brown (#3B2A1F). The bubble has a gentle tail pointing toward the mascot's mouth. Simple, clean, cute style — not comic-style, more like a gentle chat bubble.

Background: A soft-focus realistic morning park scene with a gentle walking path, green trees, and warm golden sunlight filtering through leaves. In the blurred background, one or two elderly people are walking leisurely on the path (seen from behind, soft bokeh, not in focus). Dreamy depth of field effect to keep focus on the mascot. Warm cream and sage green color tones overall.

Style: Warm, inviting, trustworthy. Like saying goodbye to a friend after a morning walk in the park. One mascot only.

IMPORTANT: No watermark, no logo, no signature, no star symbol, no badge in corners. The image must be completely clean with no marks or stamps."""


def main():
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
                out_path = OUTPUT_DIR / "card06_gemini.png"
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
