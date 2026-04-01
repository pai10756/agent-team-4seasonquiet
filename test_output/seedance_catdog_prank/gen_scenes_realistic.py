#!/usr/bin/env python3
"""
Generate PHOTOREALISTIC scene reference images for cat & dog prank Shorts.
Style: Real animals in real home, shot on iPhone/DSLR. NOT 3D, NOT cartoon.
"""
import base64, json, os, sys, time, urllib.request
from pathlib import Path

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
CAT_REF = OUT_DIR / "cat_turnaround_real.png"
DOG_REF = OUT_DIR / "dog_turnaround_real.png"

def log(msg):
    print(f"[scene] {msg}", file=sys.stderr)

def call_gemini_with_refs(prompt, refs, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    parts = []
    for ref in refs:
        b64 = base64.b64encode(ref.read_bytes()).decode()
        mime = "image/jpeg" if str(ref).endswith(".jpg") else "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    parts.append({"text": prompt})
    payload = json.dumps({
        "contents": [{"parts": parts}],
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

REAL_STYLE = (
    "PHOTOREALISTIC, looks like real footage shot on iPhone 15 Pro or Sony A7IV. "
    "Real animals, real fur texture, real environment. Natural imperfections. "
    "NOT 3D render, NOT cartoon, NOT illustration, NOT Pixar, NOT anime. "
    "Slight natural grain, realistic depth of field, authentic home lighting."
)

scenes = [
    {
        "name": "scene01_sneaking_real",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            f"Using the EXACT same orange tabby cat from reference image 1 and the EXACT same golden Labrador from reference image 2.\n\n"
            f"Scene: A real cozy living room in a Taiwanese apartment, evening time. "
            f"The golden Labrador is lying on its side on a soft beige dog bed on the wooden floor, deeply asleep, belly rising and falling. "
            f"The orange tabby cat is tiptoeing toward the sleeping dog from the right side of frame, "
            f"holding a black Sharpie marker in its mouth, eyes squinting with a mischievous look.\n\n"
            f"Environment: Real lived-in apartment — beige fabric sofa with throw pillows, a warm floor lamp turned on casting golden light, "
            f"a bookshelf with some books and plants, wooden laminate floor, a few cat toys scattered.\n"
            f"Camera: Wide to medium shot, slightly low angle from floor level (as if phone placed on floor). Shallow depth of field on background.\n"
            f"Lighting: Warm evening — floor lamp as key light from left, ceiling light as soft fill, slight warm color cast.\n"
            f"{REAL_STYLE}\n"
            f"9:16 portrait orientation.\n"
            f"NO text, NO watermarks, NO UI overlays, NO cartoon elements."
        ),
    },
    {
        "name": "scene02_drawing_real",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            f"Using the EXACT same orange tabby cat from reference image 1 and the EXACT same golden Labrador from reference image 2.\n\n"
            f"Scene: EXTREME CLOSE-UP. The golden Labrador's face fills most of the frame, peacefully sleeping on a beige cushion. "
            f"The orange tabby cat's paw is visible from the right side, gripping a black marker pen, "
            f"carefully drawing a big circle around the dog's left eye. "
            f"The dog's right eye already has a big X drawn on it in black marker ink. "
            f"There is a small heart drawn on the dog's nose tip. "
            f"The marker lines look like real Sharpie ink on real fur — slightly uneven, absorbed into the fur.\n\n"
            f"Camera: Tight close-up on dog's face, cat's paw and marker entering from right edge of frame. Focus on the dog's face.\n"
            f"Lighting: Warm ambient lamp light from above-left, soft shadows under the fur.\n"
            f"{REAL_STYLE}\n"
            f"9:16 portrait orientation.\n"
            f"NO text, NO watermarks."
        ),
    },
    {
        "name": "scene03_mirror_real",
        "refs": [DOG_REF],
        "prompt": (
            f"Using the EXACT same golden Labrador from the reference image.\n\n"
            f"Scene: A hallway in a real apartment. The golden Labrador is standing in front of a full-length IKEA-style mirror leaning against the wall. "
            f"In the mirror reflection, we clearly see the dog's face with doodles drawn on it in black marker: "
            f"a big circle around the left eye, a big X over the right eye, a small heart on the nose tip, "
            f"and curly mustache lines near the mouth. The marker lines look like real ink on real fur.\n"
            f"The dog's expression is stunned — eyes wide, ears perked forward, mouth slightly open, frozen staring at its own reflection.\n\n"
            f"Camera: Medium shot from behind/side of the dog at about 45 degrees, capturing both the real dog and its mirror reflection clearly.\n"
            f"Lighting: Hallway ceiling light, slightly cooler tone than the living room, creating slight dramatic contrast.\n"
            f"{REAL_STYLE}\n"
            f"9:16 portrait orientation.\n"
            f"NO text, NO watermarks."
        ),
    },
    {
        "name": "scene04_staredown_real",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            f"Using the EXACT same orange tabby cat from reference image 1 and the EXACT same golden Labrador from reference image 2.\n\n"
            f"Scene: Back in the living room. The golden Labrador (with black marker doodles still visible on face — circle on left eye, X on right eye, "
            f"heart on nose, mustache lines) has turned around from the hallway and is now STARING down at the orange tabby cat with a look of disbelief.\n"
            f"The orange tabby cat is sitting on the wooden floor looking up at the dog with an exaggerated innocent face — "
            f"wide green eyes, head tilted to one side, one front paw slightly raised as if saying 'it wasn't me.'\n\n"
            f"Camera: Medium two-shot, eye level between the two animals. Dog on left facing right, cat on right facing left. Both in focus.\n"
            f"Lighting: Warm living room lamp light, golden warm tone.\n"
            f"{REAL_STYLE}\n"
            f"9:16 portrait orientation.\n"
            f"NO text, NO watermarks."
        ),
    },
    {
        "name": "scene05_laughing_real",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            f"Using the EXACT same orange tabby cat from reference image 1 and the EXACT same golden Labrador from reference image 2.\n\n"
            f"Scene: The golden Labrador (with marker doodles still faintly visible on face) and the orange tabby cat "
            f"are sitting side by side on the living room wooden floor, both looking extremely happy and content. "
            f"The dog has its mouth wide open in a big happy pant (tongue out, eyes soft and squinting with joy), looking like it's laughing. "
            f"The cat is leaning slightly against the dog, eyes half-closed in contentment, mouth slightly open showing teeth in a cat-smile. "
            f"The dog has one big paw gently resting over the cat's back in a buddy gesture.\n\n"
            f"Camera: Medium frontal shot, both animals centered and looking toward camera, slightly low angle.\n"
            f"Lighting: Warm golden living room light, feel-good cozy atmosphere, slight lens flare from floor lamp.\n"
            f"{REAL_STYLE}\n"
            f"9:16 portrait orientation.\n"
            f"NO text, NO watermarks."
        ),
    },
]

for scene in scenes:
    name = scene["name"]
    refs = [r for r in scene["refs"] if r.exists()]
    if not refs:
        log(f"SKIP {name}: no reference images found")
        continue
    log(f"Generating {name}...")
    img = call_gemini_with_refs(scene["prompt"], refs)
    if img:
        out = OUT_DIR / f"{name}.png"
        out.write_bytes(img)
        log(f"  OK {len(img):,} bytes -> {out}")
    else:
        log(f"  FAILED {name}")
    time.sleep(3)

log("Done!")
