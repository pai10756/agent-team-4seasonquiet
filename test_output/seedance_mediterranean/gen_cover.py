import base64, json, os, sys, time, urllib.request
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
CHAR_REF = OUT_DIR / "character_turnaround_v4.png"

def log(msg):
    print(f"[cover] {msg}", file=sys.stderr)

def call_gemini(prompt, refs, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    parts = []
    for ref in refs:
        b64 = base64.b64encode(ref.read_bytes()).decode()
        mime = "image/png" if str(ref).endswith(".png") else "image/jpeg"
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

COVER_PROMPT = (
    "Using the character from the reference image (young Taiwanese woman, sage green linen blouse, "
    "long dark brown wavy hair).\n\n"
    "Create a 9:16 portrait (1080x1920) YouTube Shorts cover thumbnail.\n\n"

    "SCENE:\n"
    "The woman is in her apartment livestream setup, sitting behind a wooden table. "
    "She is holding up a bottle of extra virgin olive oil toward the camera with one hand, "
    "the other hand pointing at it with a confident excited expression — eyes bright, mouth open in a smile, "
    "like she just discovered something amazing she must share.\n"
    "On the table: a colorful Mediterranean salad bowl, scattered nuts, phone on tripod.\n"
    "Behind her: cozy apartment living room with sofa, bookshelf, plants, warm floor lamp.\n"
    "Ring light visible, creating warm glow. Evening warm lighting.\n"
    "3/4 front angle, upper body and table visible.\n"
    "Photorealistic, iPhone livestream quality.\n\n"

    "TEXT OVERLAY (must be rendered clearly and correctly in Traditional Chinese):\n"
    "- MAIN HEADLINE — the LARGEST and most dominant element on the entire image:\n"
    "  Line 1: 吃油\n"
    "  Line 2: 反而瘦？\n"
    "  Position: upper-left area, overlapping slightly on the scene.\n"
    "  Style: BOLD white text (#FFFFFF) with thick black outline/stroke and strong drop shadow "
    "for maximum readability against the photo background. The text must POP and be instantly readable.\n"
    "- SUB-HEADLINE:\n"
    "  地中海飲食的秘密\n"
    "  Position: below main headline.\n"
    "  Style: White text with black outline, smaller than headline but still clearly readable.\n"
    "- BADGE (top-right corner):\n"
    "  A sage green (#A8B88A) circle with white text: 研究實證\n\n"

    "CRITICAL RULES:\n"
    "- Text MUST have strong contrast against the photo — use white with thick dark outline/stroke\n"
    "- Headline must be the most eye-catching element — bigger than anything else\n"
    "- The woman and the olive oil bottle must both be clearly visible\n"
    "- Render Chinese characters 吃油反而瘦？ correctly, no garbled text\n"
    "- No watermarks, no extra logos\n"
)

log("Generating livestream-style cover...")
img_bytes = call_gemini(COVER_PROMPT, [CHAR_REF])
if img_bytes:
    out_path = OUT_DIR / "cover_live.png"
    out_path.write_bytes(img_bytes)
    log(f"Saved: {out_path.name} ({len(img_bytes)} bytes)")
else:
    log("FAILED")
    sys.exit(1)

log("Done!")
