"""EP54 園藝也是運動 — 角色定裝照 + 小靜定裝照生成

Generates:
1. character_turnaround.png — 花姐姐多角度定裝照（3:2 白底）
2. face_reference.jpg — 臉部特寫
3. mascot_turnaround.png — 小靜當集定裝照（含園藝圍裙）
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).parent

env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
MODEL = "gemini-3.1-flash-image-preview"

MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
if not MASCOT_REF.exists():
    MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference.jpg"


def log(msg):
    print(f"[ep54_char] {msg}", file=sys.stderr, flush=True)


def call_gemini(parts, max_retries=5):
    """Use curl subprocess with stdin pipe to avoid Python urllib 429 issue."""
    import subprocess
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    })
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", "Content-Type: application/json",
                 "-d", "@-",
                 "--max-time", "180"],
                input=payload, capture_output=True, text=True, timeout=200
            )
            if result.returncode != 0:
                log(f"  curl error (attempt {attempt+1}): {result.stderr[:200]}")
            else:
                data = json.loads(result.stdout)
                if "error" in data:
                    log(f"  API error (attempt {attempt+1}): {data['error'].get('message', '')[:200]}")
                else:
                    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            img_bytes = base64.b64decode(part["inlineData"]["data"])
                            if len(img_bytes) > 10 * 1024:
                                return img_bytes
                    log(f"  No image (attempt {attempt+1})")
        except Exception as e:
            log(f"  Error (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))
    return None


def load_ref(path, label):
    if not path.exists():
        log(f"  WARNING: {path} not found")
        return []
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "image/png" if str(path).endswith(".png") else "image/jpeg"
    log(f"  Loaded: {path.name}")
    return [{"text": label}, {"inlineData": {"mimeType": mime, "data": b64}}]


CHARACTER_DESC = (
    "Beautiful East Asian female, age 25-28. "
    "Face: oval face, bright round almond eyes with soft double eyelids, warm brown iris, "
    "natural full brows slightly straight, straight nose bridge with soft rounded tip, "
    "naturally pink slightly full lower lip. "
    "Signature: healthy sun-kissed glow with light freckles on nose bridge. "
    "Hair: medium-long natural dark brown, loose low ponytail with face-framing wispy strands. "
    "Makeup: barely-there, natural healthy glow, tinted lip balm only. "
    "Outfit: cream linen button-up shirt with sleeves rolled to elbows, "
    "sage green cotton tank top underneath visible at V-neck, khaki wide-leg cropped pants. "
    "No logos, no loud prints, no jewelry except simple leather wristwatch."
)

TURNAROUND_PROMPT = (
    "3:2 horizontal character turnaround sheet / model sheet, pure clean white background.\n"
    f"Character: {CHARACTER_DESC}\n\n"
    "Face shape, eye shape, brow shape, nose bridge, lip thickness, freckle pattern, "
    "and age must be strictly consistent across all views. "
    "Hairline and hairstyle must remain consistent. Only ONE character, no face swapping.\n\n"
    "Layout (single composite image, clean grid, unified lighting and color):\n"
    "Left side (~60% width): two large images stacked vertically:\n"
    "1) Full-body front view standing pose (relaxed stance, hands at sides)\n"
    "2) Full-body 90-degree side view standing pose\n\n"
    "Right side (~40% width): 2x3 grid of six head close-ups:\n"
    "1) Head front view (neutral expression)\n"
    "2) Head back view (showing ponytail and head shape)\n"
    "3) Head left 45-degree view (neutral)\n"
    "4) Head right 45-degree view (neutral)\n"
    "5) Expression: warm happy smile (eyes crinkled, genuine joy)\n"
    "6) Expression: surprised/excited (eyes wide, mouth slightly open, discovering something)\n\n"
    "Quality: high-end realistic studio photography, sharp eyes, real skin micro-texture "
    "(pores, freckles visible, no airbrushing), consistent exposure, 8K detail, light film grain, "
    "ultra-clean white background.\n\n"
    "Hard constraints: NO readable text, no labels, no subtitles, no logos, no UI overlays, "
    "no cartoon or anime style, no extra people, no deformed fingers."
)

FACE_PROMPT = (
    f"Single portrait close-up of: {CHARACTER_DESC}\n\n"
    "Tight crop: face and upper shoulders only. Front-facing, slight 10-degree turn to left. "
    "Warm natural outdoor golden-hour light from upper-right. "
    "Expression: warm approachable smile, eyes looking directly at camera. "
    "Freckles on nose bridge clearly visible. Hair wisps catching light. "
    "Clean cream/white background. 3:4 portrait ratio. "
    "Photorealistic, 8K detail, real skin texture visible. "
    "NO text, NO watermarks."
)

MASCOT_PROMPT = (
    "3:2 horizontal character turnaround sheet, pure clean white background.\n"
    "Character: The EXACT 3D smooth matte plastic leopard cat toy figure from the reference image. "
    "Same head shape, same round dark brown eyes, same forehead white stripes, same dark spots (not stripes), "
    "same sage green apron with white bowl-leaf icon. Smooth matte plastic material, Pop Mart quality.\n\n"
    "For this episode, the mascot is in a GARDEN setting mood — same apron, but holding a tiny watering can "
    "as a prop in one paw. Expression is happy and curious.\n\n"
    "Layout (single composite image):\n"
    "Left side (~60%): two views stacked:\n"
    "1) Full-body front view (standing, holding tiny watering can)\n"
    "2) Full-body 45-degree view (same pose)\n\n"
    "Right side (~40%): 2x3 grid of six head/expression close-ups:\n"
    "1) Front face (default gentle smile)\n"
    "2) 45-degree left\n"
    "3) 45-degree right\n"
    "4) Happy excited (crescent eyes, big smile)\n"
    "5) Curious (head tilt, one paw on chin)\n"
    "6) Waving goodbye (one paw raised)\n\n"
    "Quality: clean 3D render quality, consistent lighting, white background. "
    "NO text, NO labels, NO watermarks."
)

tasks = [
    ("character_turnaround", TURNAROUND_PROMPT, []),
    ("face_reference", FACE_PROMPT, []),
    ("mascot_turnaround", MASCOT_PROMPT, [MASCOT_REF]),
]

if __name__ == "__main__":
    if not API_KEY:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    for name, prompt, refs in tasks:
        log(f"\nGenerating {name}...")
        parts = []
        for ref in refs:
            parts.extend(load_ref(ref,
                "EXACT REFERENCE — the character must look identical to this:"))
        parts.append({"text": prompt})

        img = call_gemini(parts)
        ext = "png" if "turnaround" in name else "jpg"
        if img:
            out = OUT_DIR / f"{name}.{ext}"
            out.write_bytes(img)
            log(f"  OK: {out.name} ({len(img):,} bytes)")
        else:
            log(f"  FAILED: {name}")
        time.sleep(5)
