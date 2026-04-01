"""EP53 喝茶與長壽 — 場景圖生成（含人物 + 背景）

Uses character_turnaround_v6.png as character reference.
Generates 6 live scenes with the tea host character.
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

CHAR_REF = BASE / "characters" / "ep53_tea_host" / "character_turnaround_v6.png"
MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
if not MASCOT_REF.exists():
    MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference.jpg"


def log(msg):
    print(f"[ep53_scene] {msg}", file=sys.stderr, flush=True)


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


# Character description block (matches turnaround_v6)
CHAR_DESC = (
    "The young woman from the reference image: East Asian female, 23-26, "
    "gentle square jaw, downturned almond eyes, porcelain dewy skin. "
    "Hair pulled back in a low bun with soft face-framing strands. "
    "Wearing a cream off-white V-neck chunky knit sweater and khaki trousers. "
    "Korean natural makeup: dewy glass skin, soft peach blush, gradient glossy lips."
)

scenes = [
    {
        "name": "scene01_hook",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: A warm, naturally-lit traditional tea room / tea corner in a modern Taiwanese home. "
            "The young woman is sitting behind a beautiful wooden tea tray (功夫茶盤), seen from 3/4 FRONT angle. "
            "She is holding up a small ceramic tea cup with both hands near her chin, "
            "looking at the camera with a curious, slightly mysterious expression — "
            "as if she's about to reveal a secret.\n\n"
            "Environment:\n"
            "- A complete gongfu tea set on the wooden tea tray: clay teapot (紫砂壺), fairness pitcher, small cups\n"
            "- Loose leaf tea visible in an open ceramic tea caddy\n"
            "- Warm morning golden light streaming from a window on the left\n"
            "- Behind her: natural wood shelving with tea canisters, a small bamboo plant, warm earth tones\n"
            "- Steam rising gently from the teapot\n"
            "- Cozy, authentic, lived-in tea space feel\n"
            "- 9:16 portrait orientation\n"
            "- Photorealistic, cinematic quality, shallow DOF\n"
            "- Warm cream/amber color grading\n"
            "- NO text, NO watermarks, NO UI overlays"
        )
    },
    {
        "name": "scene02_flip_data",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: Same tea room. The woman is seen from 3/4 angle, "
            "leaning forward slightly with an earnest, informative expression. "
            "One hand is gesturing toward the camera (palm up, explaining), "
            "the other hand rests on the wooden tea tray near the teapot. "
            "She looks like she's sharing an important fact with genuine excitement.\n\n"
            "Environment:\n"
            "- Same wooden tea tray with gongfu tea set\n"
            "- A small notebook or phone showing data visible on the table (subtle, not dominant)\n"
            "- Morning golden light from left window\n"
            "- Tea room shelving and plants in warm bokeh background\n"
            "- A freshly poured cup of green tea in front of her, golden-green color visible\n"
            "- 9:16 portrait, photorealistic, cinematic\n"
            "- Warm tones, shallow DOF\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene03_compare_cups",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: Same tea room, slightly different angle. The woman is looking at the camera with "
            "a surprised, 'did you know?' expression. In front of her on the wooden tea tray: "
            "THREE small ceramic tea cups arranged in a row, each with different amounts of green tea. "
            "She is pointing at the MIDDLE cup (the 2-3 cups sweet spot) with one finger, "
            "indicating this is the right amount. Her expression says 'this one — not too little, not too much.'\n\n"
            "Environment:\n"
            "- Same tea room, morning light\n"
            "- The three cups are clearly visible: first cup nearly empty, middle cup nicely filled, third cup overflowing\n"
            "- Tea tray with teapot in background\n"
            "- Warm cozy atmosphere\n"
            "- 9:16 portrait, photorealistic\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene04_evidence_exercise",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: The woman has stood up from the tea table. She is now standing in the tea room, "
            "seen from medium shot (full upper body). One hand holds a tea cup, the other hand "
            "makes a fist-pump / arm-flexing gesture — playfully showing 'exercise'. "
            "Her expression is emphatic and engaging, like she's delivering the most surprising finding. "
            "Slight head tilt, eyebrows raised, mouth open mid-sentence.\n\n"
            "Environment:\n"
            "- Tea table visible behind her with tea set\n"
            "- She's half-turned toward camera, dynamic pose\n"
            "- Morning light wrapping around her from the side\n"
            "- Natural, warm, energetic atmosphere\n"
            "- 9:16 portrait, photorealistic\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene05_reminder",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: The woman is back at the tea table, pouring tea from a clay teapot into a cup "
            "with careful, graceful movements. She is looking at the tea stream with a gentle, "
            "caring expression — like a reminder to be mindful. The tea is at a comfortable temperature "
            "(gentle steam, not intense). She's pouring slowly and deliberately.\n\n"
            "Environment:\n"
            "- Close-up angle showing her hands, the teapot, and the cup prominently\n"
            "- The golden-green tea stream is clearly visible\n"
            "- A small bamboo tea strainer and a light snack plate nearby\n"
            "- Same warm tea room, morning light, shallow DOF\n"
            "- Intimate, calming, reassuring mood\n"
            "- 9:16 portrait, photorealistic, food/tea photography quality\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene06_closing",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: Final farewell shot. The woman is holding a warm cup of tea with both hands "
            "at chest level, raising it slightly toward the camera in a gentle toast/cheers gesture. "
            "She has a warm, genuine smile with slightly crinkled eyes — the 'see you next time' smile. "
            "Soft golden backlight creating a warm halo/rim light on her hair.\n\n"
            "Environment:\n"
            "- Same tea room but now slightly tighter framing — medium close-up\n"
            "- Background beautifully blurred: warm golden bokeh with tea set and green plant shapes\n"
            "- The warmest, most inviting lighting of all scenes\n"
            "- Dreamy, gentle, goodbye atmosphere\n"
            "- 9:16 portrait, photorealistic, cinematic portrait\n"
            "- NO text, NO watermarks"
        )
    },
]

if __name__ == "__main__":
    if not API_KEY:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    results = []
    for scene in scenes:
        log(f"\nGenerating {scene['name']}...")
        parts = []
        for ref in scene["refs"]:
            parts.extend(load_ref(ref,
                "CHARACTER REFERENCE — the woman must look EXACTLY like this person (same face, same hair in low bun, same outfit):"))
        parts.append({"text": scene["prompt"]})

        img = call_gemini(parts)
        if img:
            out = OUT_DIR / f"{scene['name']}.png"
            out.write_bytes(img)
            log(f"  OK: {out.name} ({len(img):,} bytes)")
            results.append((scene['name'], True))
        else:
            log(f"  FAILED: {scene['name']}")
            results.append((scene['name'], False))
        time.sleep(5)

    log("\n" + "=" * 50)
    log("RESULTS:")
    for name, ok in results:
        log(f"  {name}: {'OK' if ok else 'FAILED'}")
