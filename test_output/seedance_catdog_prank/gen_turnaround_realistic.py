#!/usr/bin/env python3
"""
Generate PHOTOREALISTIC character turnaround sheets for cat & dog prank Shorts.
Style: Real animals, as if photographed with iPhone/DSLR camera.
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

cat_prompt = """Generate a PHOTOREALISTIC CHARACTER REFERENCE SHEET for video production.
Subject: A real, chubby orange tabby cat. NOT cartoon, NOT 3D render, NOT illustration. Must look like a REAL CAT photographed in a studio.
Real fur texture with visible individual hairs, natural eye reflections, wet nose, whiskers catching light. The cat has bright green eyes, round chubby face, classic orange tabby stripe pattern, pink nose, and a slightly mischievous expression.

Layout: 3:2 horizontal, pure white studio background with soft shadows.
Left side: Two full-body photos side by side:
  1. Front view (sitting upright, looking at camera)
  2. Side view (90 degrees profile, same sitting pose)

Right side: 2x3 grid of HEAD CLOSE-UP photos:
  1. Front face, neutral expression
  2. Back of head (showing ear backs and stripe pattern)
  3. Left 45-degree angle, neutral
  4. Right 45-degree angle, neutral
  5. Squinting mischievous expression (half-closed eyes, like plotting something)
  6. Wide-eyed surprised expression (ears forward, pupils dilated)

CRITICAL: This must look like REAL PHOTOGRAPHY of a real cat. Studio lighting, shallow depth of field on close-ups, visible fur texture, natural eye catchlights.
Shot on Canon EOS R5, 85mm f/1.4 lens, professional studio lighting.
NO illustration, NO 3D, NO cartoon, NO anime, NO text, NO labels, NO watermarks."""

dog_prompt = """Generate a PHOTOREALISTIC CHARACTER REFERENCE SHEET for video production.
Subject: A real, adult golden Labrador Retriever. NOT cartoon, NOT 3D render, NOT illustration. Must look like a REAL DOG photographed in a studio.
Real golden fur with visible texture and natural sheen, warm brown eyes with natural reflections, big black wet nose, floppy soft ears. Friendly, gentle expression. Medium-large healthy build.

Layout: 3:2 horizontal, pure white studio background with soft shadows.
Left side: Two full-body photos side by side:
  1. Front view (sitting upright, tongue slightly out, looking at camera)
  2. Side view (90 degrees profile, same sitting pose)

Right side: 2x3 grid of HEAD CLOSE-UP photos:
  1. Front face, neutral calm expression
  2. Back of head (showing ear shape and fur pattern)
  3. Left 45-degree angle, neutral
  4. Right 45-degree angle, neutral
  5. Shocked/confused expression (eyebrows raised, head slightly tilted, mouth slightly open)
  6. Happy laughing expression (mouth wide open, tongue out, eyes squinting with joy)

CRITICAL: This must look like REAL PHOTOGRAPHY of a real dog. Studio lighting, shallow depth of field on close-ups, visible fur texture, natural eye catchlights.
Shot on Canon EOS R5, 85mm f/1.4 lens, professional studio lighting.
NO illustration, NO 3D, NO cartoon, NO anime, NO text, NO labels, NO watermarks."""

turnarounds = [
    ("cat_turnaround_real.png", cat_prompt),
    ("dog_turnaround_real.png", dog_prompt),
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
