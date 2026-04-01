#!/usr/bin/env python3
"""
Generate character turnaround sheets for cat & dog prank Shorts.
Characters:
  1. Orange tabby cat (橘貓) — the prankster
  2. Golden Labrador Retriever — the sleeping victim
"""
import base64, json, os, sys, time, urllib.request
from pathlib import Path

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent

def log(msg):
    print(f"[turnaround] {msg}", file=sys.stderr)

def call_gemini(prompt, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            candidates = data.get("candidates", [])
            if candidates:
                for part in candidates[0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        return base64.b64decode(part["inlineData"]["data"])
            log(f"No image (attempt {attempt+1})")
        except Exception as e:
            log(f"Error attempt {attempt+1}: {e}")
            time.sleep(5)
    return None

# ── Character 1: Orange Tabby Cat ──
cat_prompt = """Generate a CHARACTER TURNAROUND SHEET for animation/video production.
Subject: A cute, chubby orange tabby cat with bright green eyes, round face, thick striped fur pattern, pink nose, and a mischievous expression. The cat has a slightly chubby belly and short legs. Animated/Pixar-quality 3D rendering style, expressive and adorable.

Layout: 3:2 horizontal, pure white background (#FFFFFF).
Left side: Two full-body views side by side:
  1. Front view (sitting upright, tail curled around feet, looking directly at camera)
  2. Side view (90 degrees, same sitting pose, showing full profile)

Right side: 2x3 grid of HEAD CLOSE-UPS:
  1. Front neutral expression
  2. Back view (showing ear pattern and stripe pattern on back of head)
  3. Left 45-degree angle, neutral
  4. Right 45-degree angle, neutral
  5. Mischievous grin (squinting eyes, sly smile)
  6. Innocent/surprised expression (wide eyes, slightly open mouth)

CRITICAL: Face shape, eye shape, ear shape, stripe pattern must be IDENTICAL across all views.
High-quality 3D render, soft studio lighting, 8K detail.
NO text, NO labels, NO watermarks."""

# ── Character 2: Golden Labrador ──
dog_prompt = """Generate a CHARACTER TURNAROUND SHEET for animation/video production.
Subject: A friendly, large golden Labrador Retriever with warm brown eyes, soft golden fur, floppy ears, big black nose, and a gentle expression. Medium-large build, muscular but soft-looking. Animated/Pixar-quality 3D rendering style, lovable and expressive.

Layout: 3:2 horizontal, pure white background (#FFFFFF).
Left side: Two full-body views side by side:
  1. Front view (sitting upright, tongue slightly out, looking at camera)
  2. Side view (90 degrees, same sitting pose, showing full profile)

Right side: 2x3 grid of HEAD CLOSE-UPS:
  1. Front neutral expression
  2. Back view (showing ear shape and fur pattern on back of head)
  3. Left 45-degree angle, neutral
  4. Right 45-degree angle, neutral
  5. Shocked/surprised expression (wide eyes, ears perked up, mouth open)
  6. Laughing expression (mouth wide open, eyes squinting, happy)

CRITICAL: Face shape, eye color, ear shape, nose shape must be IDENTICAL across all views.
High-quality 3D render, soft studio lighting, 8K detail.
NO text, NO labels, NO watermarks."""

turnarounds = [
    ("cat_turnaround.png", cat_prompt),
    ("dog_turnaround.png", dog_prompt),
]

for filename, prompt in turnarounds:
    log(f"Generating {filename}...")
    img = call_gemini(prompt)
    if img:
        out = OUT_DIR / filename
        out.write_bytes(img)
        log(f"  OK {len(img):,} bytes -> {out}")
    else:
        log(f"  FAILED {filename}")
    time.sleep(3)

log("Done!")
