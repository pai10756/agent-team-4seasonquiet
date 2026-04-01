"""EP53 喝茶與長壽 — 背景場景圖生成（無人物，供 Seedance 合成用）

Generates 6 background scenes without any people.
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).parent

# Load .env
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
    print(f"[ep53_bg] {msg}", file=sys.stderr, flush=True)


def call_gemini(parts, max_retries=5):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    if len(img_bytes) > 10 * 1024:
                        return img_bytes
            log(f"  No image (attempt {attempt+1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} (attempt {attempt+1}): {body}")
            if e.code == 503:
                time.sleep(10 * (attempt + 1)); continue
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


scenes = [
    ("bg01_tea_room", None,
     "A warm, naturally-lit traditional tea corner in a modern Taiwanese home. NO PEOPLE in the scene. "
     "On a beautiful wooden tea tray (功夫茶盤): a clay teapot (紫砂壺), a fairness pitcher, "
     "several small ceramic tea cups arranged neatly, an open ceramic tea caddy with loose leaf tea visible. "
     "Behind the table: natural wood shelving with various tea canisters, a small bamboo plant, "
     "warm earth-tone ceramics. A linen tea cloth draped on the tray edge. "
     "Warm morning golden light streaming from a window on the left side. "
     "Steam rising gently from the teapot spout. "
     "9:16 portrait. Photorealistic, cinematic tea photography. Warm cream/amber color grading. "
     "ABSOLUTELY NO PEOPLE, NO HANDS, NO BODY PARTS. NO text, NO watermarks."),

    ("bg02_tea_data", None,
     "Same tea room setting but closer angle. A freshly poured cup of green tea in the foreground, "
     "golden-green color clearly visible through the ceramic cup. Steam curling upward. "
     "Behind it: the clay teapot, a small notebook open showing some handwritten notes (blurred), "
     "scattered dried tea leaves on the wooden tray. "
     "Warm morning light, shallow depth of field — tea cup sharp, background dreamy bokeh. "
     "9:16 portrait. Photorealistic, food photography quality. "
     "ABSOLUTELY NO PEOPLE, NO HANDS. NO text, NO watermarks."),

    ("bg03_three_cups", None,
     "Top-down / slightly angled overhead view of a wooden tea tray. "
     "THREE small ceramic tea cups arranged in a neat row from left to right: "
     "LEFT cup: nearly empty, just a thin layer of tea at the bottom. "
     "MIDDLE cup: perfectly filled to about 70% with golden-green tea, looks ideal and inviting. "
     "RIGHT cup: overflowing slightly, tea pooling around the base, too much. "
     "The contrast should be clear: too little — just right — too much. "
     "Around the cups: the tea tray with teapot, some scattered dried tea leaves, wooden surface. "
     "Warm natural light from above-left. "
     "9:16 portrait. Photorealistic, clean composition. "
     "ABSOLUTELY NO PEOPLE, NO HANDS. NO text, NO watermarks."),

    ("bg04_tea_and_shoes", None,
     "A creative split composition on a wooden floor / entry area of a cozy home. "
     "LEFT side: a small wooden side table with a cup of warm tea, steam rising, "
     "a tea caddy, cozy warm atmosphere. "
     "RIGHT side: a pair of clean running shoes / sneakers placed neatly on the floor, "
     "a yoga mat rolled up leaning against the wall, suggesting exercise. "
     "The composition implies tea + exercise = the winning combination. "
     "Warm natural light from a nearby window. Cream and wood tones throughout. "
     "9:16 portrait. Photorealistic, lifestyle photography. "
     "ABSOLUTELY NO PEOPLE, NO HANDS. NO text, NO watermarks."),

    ("bg05_pouring_tea", None,
     "Extreme close-up of tea being poured from a clay teapot into a small ceramic cup. "
     "The golden-green tea stream is the hero — sharp, glistening, caught mid-pour. "
     "The tea temperature is comfortable (gentle steam, NOT intense boiling steam). "
     "A small bamboo tea strainer beside the cup. A light snack plate with dried fruit nearby. "
     "Background: blurred warm tea room with wooden surfaces and earth tones. "
     "Shot from slightly above, shallow DOF. "
     "9:16 portrait. Photorealistic, tea ceremony photography, Sony A7IV quality. "
     "ABSOLUTELY NO PEOPLE, NO HANDS holding the teapot — the pour should look like "
     "a gravity/still-life shot or use an elevated teapot stand. NO text, NO watermarks."),

    ("bg06_closing_mascot", "mascot",
     "Using the mascot reference: the small 3D leopard cat mascot (smooth matte plastic toy, "
     "sage green apron, round spotted face) is sitting on a wooden tea tray. "
     "The mascot is hugging a small ceramic tea cup with both paws, looking up at camera with "
     "a happy, warm expression. Its spotted tail curls around the base of the cup. "
     "Around the mascot: a clay teapot, some small tea cups, scattered dried tea leaves. "
     "Background: warm blurred tea room with golden bokeh, morning light, dreamy atmosphere. "
     "The mascot looks like a real physical toy figurine placed on the tray, about 15cm tall. "
     "9:16 portrait. Photorealistic environment + 3D matte plastic toy mascot. "
     "NO PEOPLE, NO HANDS. Only the mascot. NO text, NO watermarks.")
]


if __name__ == "__main__":
    if not API_KEY:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    results = []
    for name, ref_type, prompt in scenes:
        log(f"\nGenerating {name}...")
        parts = []
        if ref_type == "mascot":
            parts.extend(load_ref(MASCOT_REF,
                "MASCOT REFERENCE — the 3D mascot must look EXACTLY like this (same face, markings, material, apron):"))
        parts.append({"text": prompt})

        img = call_gemini(parts)
        if img:
            out = OUT_DIR / f"{name}.png"
            out.write_bytes(img)
            log(f"  OK: {name}.png ({len(img):,} bytes)")
            results.append((name, True))
        else:
            log(f"  FAILED: {name}")
            results.append((name, False))
        time.sleep(5)

    log("\n" + "=" * 50)
    log("RESULTS:")
    for name, ok in results:
        log(f"  {name}: {'OK' if ok else 'FAILED'}")
