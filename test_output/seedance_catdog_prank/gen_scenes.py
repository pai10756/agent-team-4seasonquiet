#!/usr/bin/env python3
"""
Generate scene reference images for cat & dog prank Shorts.
5 scenes, each uses character turnaround as reference for consistency.
"""
import base64, json, os, sys, time, urllib.request
from pathlib import Path

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
CAT_REF = OUT_DIR / "cat_turnaround.png"
DOG_REF = OUT_DIR / "dog_turnaround.png"

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

scenes = [
    {
        "name": "scene01_sneaking",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            "Using the orange tabby cat from reference image 1 and the golden Labrador from reference image 2.\n\n"
            "Scene: A cozy, warm-lit living room. The golden Labrador is lying on its side on a soft beige dog bed, "
            "deeply asleep with eyes closed, belly slowly rising and falling. "
            "The orange tabby cat is tiptoeing toward the sleeping dog from the right side, "
            "holding a black marker pen in its mouth, with a mischievous squinting grin.\n\n"
            "Environment: Warm apartment living room, wooden floor, a sofa in the background, "
            "soft evening lamp light, some throw pillows on the floor.\n"
            "Camera: Wide shot, slightly low angle, showing both characters.\n"
            "Style: Pixar-quality 3D animation, warm cinematic lighting, cozy atmosphere.\n"
            "9:16 portrait orientation.\n"
            "NO text, NO watermarks, NO UI overlays."
        ),
    },
    {
        "name": "scene02_drawing",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            "Using the orange tabby cat from reference image 1 and the golden Labrador from reference image 2.\n\n"
            "Scene: CLOSE-UP shot. The golden Labrador's face fills most of the frame, still sleeping peacefully. "
            "The orange tabby cat's paw is visible holding a black marker, carefully drawing a big circle "
            "around the dog's left eye. The dog's right eye already has a big X drawn on it in black marker. "
            "There is a small heart drawn on the dog's nose. The cat looks extremely focused and concentrated.\n\n"
            "Camera: Close-up on the dog's face, cat's paw and marker entering from right side of frame.\n"
            "Lighting: Warm ambient lamp light, soft shadows.\n"
            "Style: Pixar-quality 3D animation, expressive, comedic timing frozen moment.\n"
            "9:16 portrait orientation.\n"
            "NO text, NO watermarks."
        ),
    },
    {
        "name": "scene03_mirror",
        "refs": [DOG_REF],
        "prompt": (
            "Using the golden Labrador from the reference image.\n\n"
            "Scene: The golden Labrador is standing in front of a full-length mirror in a hallway. "
            "In the mirror reflection, we can clearly see the dog's face with doodles drawn on it: "
            "a big circle around the left eye, a big X on the right eye, a heart on the nose, "
            "and curly mustache lines near the mouth — all in black marker ink.\n"
            "The dog's expression is SHOCKED — eyes wide open, ears fully perked up, mouth slightly open, "
            "frozen in disbelief staring at its own reflection.\n\n"
            "Camera: Medium shot from behind/side of the dog, showing both the dog and its mirror reflection.\n"
            "Lighting: Hallway light, slightly dramatic.\n"
            "Style: Pixar-quality 3D animation, comedic, dramatic reaction moment.\n"
            "9:16 portrait orientation.\n"
            "NO text, NO watermarks."
        ),
    },
    {
        "name": "scene04_staredown",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            "Using the orange tabby cat from reference image 1 and the golden Labrador from reference image 2.\n\n"
            "Scene: The golden Labrador (with doodles still on its face — circle on left eye, X on right eye, "
            "heart on nose, mustache lines) has turned around from the mirror and is now STARING directly "
            "at the orange tabby cat. The dog's expression is a mix of disbelief and accusation.\n"
            "The orange tabby cat is sitting on the floor looking up at the dog with an exaggerated "
            "INNOCENT expression — wide eyes, head tilted to one side, one paw raised as if saying 'wasn't me'.\n\n"
            "Camera: Medium two-shot, eye-level, dog on the left facing right, cat on the right facing left.\n"
            "Lighting: Warm living room light.\n"
            "Style: Pixar-quality 3D animation, comedic standoff moment.\n"
            "9:16 portrait orientation.\n"
            "NO text, NO watermarks."
        ),
    },
    {
        "name": "scene05_laughing",
        "refs": [CAT_REF, DOG_REF],
        "prompt": (
            "Using the orange tabby cat from reference image 1 and the golden Labrador from reference image 2.\n\n"
            "Scene: The golden Labrador (still with doodles on face) and the orange tabby cat are sitting "
            "side by side on the living room floor, both LAUGHING HYSTERICALLY together. "
            "The dog has its mouth wide open in a big laugh, eyes squinting with joy. "
            "The cat is leaning back laughing, one paw on its belly. "
            "The dog has one big paw draped over the cat's shoulder in a buddy gesture.\n\n"
            "Camera: Medium frontal shot, both characters centered, slightly low angle looking up.\n"
            "Lighting: Warm golden living room light, feel-good atmosphere.\n"
            "Style: Pixar-quality 3D animation, heartwarming comedic finale, friendship moment.\n"
            "9:16 portrait orientation.\n"
            "NO text, NO watermarks."
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
