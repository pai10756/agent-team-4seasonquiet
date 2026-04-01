"""EP54 園藝也是運動 — 場景圖生成（含人物 + 背景）

Uses character_turnaround.png as character reference.
Generates 5 live scenes + 1 mascot closing scene.
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

CHAR_REF = OUT_DIR / "character_turnaround.png"
if not CHAR_REF.exists():
    CHAR_REF = OUT_DIR / "character_turnaround.jpg"
MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference_clean.jpg"
if not MASCOT_REF.exists():
    MASCOT_REF = BASE / "characters" / "mascot" / "3d_reference.jpg"


def log(msg):
    print(f"[ep54_scene] {msg}", file=sys.stderr, flush=True)


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


CHAR_DESC = (
    "The young woman from the reference image: East Asian female, 25-28, "
    "oval face, bright round almond eyes, natural full brows, straight nose, naturally pink full lips. "
    "Healthy sun-kissed skin with light freckles on nose bridge. "
    "Hair in a loose low ponytail with face-framing wispy strands. "
    "Wearing a cream linen button-up shirt with sleeves rolled to elbows "
    "over a sage green cotton tank top, khaki wide-leg cropped pants. "
    "Minimal no-makeup look, natural healthy glow."
)

scenes = [
    {
        "name": "scene01_hook",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: A beautiful community garden / rooftop garden in golden morning light. "
            "The young woman is kneeling on soft dark soil beside a raised wooden garden bed, "
            "both hands gently pressing soil around a small green seedling she just planted. "
            "She looks up at the camera with a warm, satisfied, slightly mischievous smile — "
            "as if saying 'bet you didn't know this counts as exercise.'\n\n"
            "Environment:\n"
            "- Lush green vegetable rows and herb patches in wooden raised beds\n"
            "- A galvanized metal watering can beside her\n"
            "- Warm golden morning sunlight creating long shadows and dappled light through nearby trees\n"
            "- Small garden tools (trowel, pruning shears) on the soil beside her\n"
            "- Background: more garden beds, potted plants, greenery in soft bokeh\n"
            "- 9:16 portrait orientation\n"
            "- Photorealistic, outdoor documentary quality, shallow DOF\n"
            "- Warm earthy golden-green color grading\n"
            "- NO text, NO watermarks, NO UI overlays"
        )
    },
    {
        "name": "scene02_flip_data",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: Same community garden. The woman is now standing next to a raised bed "
            "full of mature vegetables, one hand resting on the wooden edge, the other hand "
            "gesturing with palm up in an explaining motion. She's leaning slightly forward "
            "with an earnest, informative expression — sharing surprising data with the viewer.\n\n"
            "Environment:\n"
            "- Lush garden vegetables visible: leafy greens, tomato vines, herbs\n"
            "- Morning golden light from the side, creating warm rim light on her hair\n"
            "- Garden path visible, other raised beds in soft bokeh background\n"
            "- She's slightly sweaty from garden work — realistic, natural\n"
            "- 9:16 portrait, photorealistic, outdoor documentary quality\n"
            "- Warm golden-green tones, shallow DOF\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene03_exercise_compare",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: The woman is in the garden, demonstrating a proper gardening squat — "
            "knees bent, back straight, feet flat on ground, reaching down to tend low plants. "
            "She's looking at the camera from this squat position with a knowing smile and "
            "one finger raised, as if saying 'THIS is the correct posture.'\n\n"
            "Environment:\n"
            "- She's between two rows of vegetable beds\n"
            "- Fresh herbs and small vegetables at ground level around her\n"
            "- Garden gloves on her hands, a bit of soil on her fingers\n"
            "- Warm morning light, natural outdoor setting\n"
            "- 9:16 portrait, photorealistic\n"
            "- Warm earthy tones\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene04_mental_health",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: The woman is standing up from garden work, stretching her arms overhead "
            "with a deeply satisfied, relieved expression. Eyes slightly closed, genuine happy smile, "
            "head tilted back slightly. Behind her, a beautiful garden in full bloom. "
            "The stretch feels earned — she's been working and now feeling great.\n\n"
            "Environment:\n"
            "- Colorful flowers and green vegetables in background\n"
            "- Golden light filtering through tree canopy overhead\n"
            "- Dappled shadow patterns on her shirt and the ground\n"
            "- Straw hat hanging on a nearby garden post\n"
            "- Sense of accomplishment and peace\n"
            "- 9:16 portrait, photorealistic, lifestyle photography\n"
            "- Warm golden tones\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "scene05_reminder",
        "refs": [CHAR_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n\n"
            "Scene: The woman is sitting on a low wooden garden bench, putting on her straw sun hat "
            "with one hand while holding a water bottle with the other. She's looking at the camera "
            "with a caring, reminder expression — like a friend reminding you to take care of yourself. "
            "Slight head tilt, warm smile.\n\n"
            "Environment:\n"
            "- Garden tools neatly placed beside the bench\n"
            "- A small basket of freshly harvested herbs/vegetables on the bench\n"
            "- Sunscreen bottle visible nearby (subtle, not dominant)\n"
            "- Bright outdoor sunlight, some shade from a garden pergola\n"
            "- 9:16 portrait, photorealistic\n"
            "- Warm protective mood\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "live_scene06_mascot",
        "refs": [CHAR_REF, MASCOT_REF],
        "prompt": (
            f"Using the character from the reference. {CHAR_DESC}\n"
            "Also include the 3D mascot from the mascot reference: a cute 3D smooth matte plastic "
            "leopard cat toy figure wearing a sage green apron with a white bowl-leaf icon.\n\n"
            "Scene: The woman is sitting on the garden bench holding a small basket of fresh herbs. "
            "The 3D mascot (小靜) is sitting on top of a large terracotta flower pot next to her, "
            "dangling its little legs. She is reaching over to gently pat the mascot on its head "
            "with one hand, looking at it with a delighted surprised smile. "
            "The mascot is looking up at her happily.\n\n"
            "Environment:\n"
            "- Garden setting, warm golden light\n"
            "- Flowers and herbs around them\n"
            "- Cozy, warm, farewell atmosphere\n"
            "- 9:16 portrait, photorealistic with 3D character element\n"
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
        for i, ref in enumerate(scene["refs"]):
            label = ("CHARACTER REFERENCE — the woman must look EXACTLY like this person "
                     "(same face, same hair, same outfit):" if i == 0
                     else "MASCOT REFERENCE — the 3D leopard cat must look EXACTLY like this:")
            parts.extend(load_ref(ref, label))
        parts.append({"text": scene["prompt"]})

        img = call_gemini(parts)
        if img:
            out = OUT_DIR / f"{scene['name']}.jpg"
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
