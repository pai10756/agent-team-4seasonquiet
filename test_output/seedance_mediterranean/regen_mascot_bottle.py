import base64, json, os, sys, time, urllib.request
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
MASCOT_REF = OUT_DIR / "mascot_turnaround.png"

def log(msg):
    print(f"[regen] {msg}", file=sys.stderr)

def call_gemini(prompt, ref_path=None, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    parts = []
    if ref_path:
        b64 = base64.b64encode(ref_path.read_bytes()).decode()
        mime = "image/png" if str(ref_path).endswith(".png") else "image/jpeg"
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

PROMPT = (
    "Using the mascot reference image, generate a scene: "
    "The small 3D leopard cat mascot (smooth matte plastic toy, sage green apron) is standing on a wooden dining table, "
    "hugging an olive oil bottle with BOTH PAWS wrapped around the bottle. "
    "Looking up toward camera with a happy smile expression. "
    "The mascot has EXACTLY ONE tail — the single spotted tail hangs naturally behind its body, "
    "NOT touching the bottle or any object. The tail is still and relaxed, not wagging. "
    "Around the mascot on the table: remnants of a Mediterranean meal (half-eaten salmon plate, "
    "olive bowl, scattered nuts), a smartphone on tripod in the background. "
    "Same apartment living room background: floor lamp warm glow, ring light dimmed, evening cozy atmosphere. "
    "The mascot looks like a real physical toy figurine placed on the table, about 20cm tall. "
    "9:16 portrait orientation. Photorealistic environment + 3D toy mascot. "
    "NO PEOPLE, NO HANDS visible. Only the mascot. NO text, NO watermarks."
)

log("Generating mascot + bottle reference (tail fix)...")
img_bytes = call_gemini(PROMPT, ref_path=MASCOT_REF)
if img_bytes:
    out_path = OUT_DIR / "live_bg06_mascot_v2.png"
    out_path.write_bytes(img_bytes)
    log(f"Saved: {out_path.name} ({len(img_bytes)} bytes)")
else:
    log("FAILED")
