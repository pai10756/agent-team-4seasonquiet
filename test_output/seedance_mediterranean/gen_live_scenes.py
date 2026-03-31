import base64, json, os, sys, time, urllib.request
from pathlib import Path

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
CHAR_REF = OUT_DIR / "character_turnaround_v4.png"
MASCOT_REF = OUT_DIR / "mascot_turnaround.png"

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
        "name": "live_scene01_opening",
        "refs": [CHAR_REF],
        "prompt": (
            "Using the character from the reference (sage green linen blouse, rolled sleeves, long dark brown wavy hair).\n\n"
            "Scene: A realistic LIVESTREAM ROOM setup in a modern Taiwanese apartment living room. "
            "The young woman is seen from 3/4 FRONT angle (slightly to the side, not fully frontal), "
            "sitting behind a kitchen island / tall table. In front of her: a bottle of cheap vegetable oil "
            "she is holding up with a disapproving expression, shaking her head.\n\n"
            "Environment details that make it feel REAL and LIVED-IN:\n"
            "- A ring light visible at the edge of frame (slightly overexposed glow)\n"
            "- A smartphone on a small tripod visible on the table, recording her\n"
            "- Behind her: a real apartment living room with sofa, bookshelf, some plants, a warm floor lamp turned on\n"
            "- Table has scattered ingredients: olive oil bottle, some nuts in a bowl, a cutting board\n"
            "- Slightly messy, authentic home feel, not a studio\n"
            "- Warm mixed lighting: ring light + apartment ceiling light + floor lamp\n"
            "- 9:16 portrait orientation\n"
            "- Photorealistic, iPhone-quality video feel, slight grain\n"
            "- NO text, NO watermarks, NO UI overlays"
        )
    },
    {
        "name": "live_scene02_show_oil",
        "refs": [CHAR_REF],
        "prompt": (
            "Using the character from the reference.\n\n"
            "Scene: Same livestream room setup in apartment. The young woman is seen from SIDE/3/4 angle, "
            "enthusiastically holding up a bottle of extra virgin olive oil close to camera, tilting it so "
            "the golden oil catches the ring light. Her other hand points at the bottle label. "
            "Expression: proud, confident, like showing her favorite product.\n\n"
            "Environment:\n"
            "- Same apartment living room background (sofa, bookshelf, plants, floor lamp)\n"
            "- Ring light glow visible, smartphone tripod on table\n"
            "- Table now has a beautiful Mediterranean salad bowl, some walnuts scattered, a small plate of olives\n"
            "- Close-up angle, the olive oil bottle is large in frame, woman slightly behind\n"
            "- Warm ring light + ambient apartment light\n"
            "- 9:16 portrait, photorealistic, authentic livestream feel\n"
            "- Slight depth of field, bottle sharp, background soft\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "live_scene03_compare",
        "refs": [CHAR_REF],
        "prompt": (
            "Using the character from the reference.\n\n"
            "Scene: Same apartment livestream setup. The woman is seen from 3/4 angle, "
            "holding TWO PLATES. Left hand holds a plain, pale plate with steamed chicken and broccoli "
            "(held lower, she looks at it with a bored unimpressed face). Right hand holds a vibrant "
            "Mediterranean plate with grilled salmon, avocado, cherry tomatoes, olive oil drizzle "
            "(held higher, she looks at it with an excited smile).\n\n"
            "Environment:\n"
            "- Same living room behind her (sofa, bookshelf, floor lamp, plants)\n"
            "- Ring light glow, phone tripod visible\n"
            "- She is leaning forward slightly, engaging with camera\n"
            "- Dynamic pose, body language clearly favoring the Mediterranean plate\n"
            "- 9:16 portrait, photorealistic\n"
            "- Warm apartment lighting, authentic feel\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "live_scene04_data",
        "refs": [CHAR_REF],
        "prompt": (
            "Generate a data card that looks like a LIVESTREAM OVERLAY / pop-up graphic.\n\n"
            "Design: A bold, eye-catching card floating on a slightly blurred warm apartment background.\n"
            "- Giant red/coral number 31% in the center, with a subtle glow effect\n"
            "- Below it: the Chinese text 心血管风险降低 in bold white text\n"
            "- A simple heart icon in red, slightly tilted\n"
            "- Small citation banner at bottom: PREDIMED N Engl J Med 2018\n"
            "- The card has a slight drop shadow, like a livestream pop-up overlay\n"
            "- Background: warm blurred bokeh of an apartment room (out of focus warm lights)\n"
            "- Style: modern livestream graphics, bold, high contrast, not clinical\n"
            "- 9:16 portrait\n"
            "- NO other text, NO watermarks"
        )
    },
    {
        "name": "live_scene05_eating",
        "refs": [CHAR_REF],
        "prompt": (
            "Using the character from the reference.\n\n"
            "Scene: Same apartment. The woman is sitting at her kitchen table (ring light now slightly to the side), "
            "eating from a beautiful plate of Mediterranean food. She is using chopsticks to pick up a piece of "
            "grilled salmon, bringing it toward the camera to show it, her expression is satisfied and happy, "
            "eyes slightly closed in enjoyment. 3/4 SIDE angle.\n\n"
            "Environment:\n"
            "- Real apartment feeling: edge of sofa visible, some shoes near the door, a jacket hung on a chair\n"
            "- Table has the full spread: salmon plate, olive oil, nuts bowl, a glass of water, phone still on tripod\n"
            "- Evening warm lighting: floor lamp on, overhead light dimmed\n"
            "- Intimate, cozy, eating at home after a livestream feeling\n"
            "- 9:16 portrait, photorealistic, warm tones\n"
            "- NO text, NO watermarks"
        )
    },
    {
        "name": "live_scene06_mascot_finale",
        "refs": [CHAR_REF, MASCOT_REF],
        "prompt": (
            "Using both references:\n"
            "Image 1: The young woman character\n"
            "Image 2: The 3D mascot XiaoJing (leopard cat toy in sage green apron)\n\n"
            "Scene: Same apartment living room. The woman is sitting at the table, seen from 3/4 SIDE angle, "
            "smiling down at the small 3D mascot who has appeared on the table next to the olive oil bottle. "
            "The mascot is hugging the bottle with both paws, looking up at her with a happy face. "
            "The woman has one hand reaching toward the mascot, about to pet its head, "
            "her expression is surprised and delighted.\n\n"
            "Environment:\n"
            "- Same lived-in apartment (ring light still on but dimmer, floor lamp warm glow)\n"
            "- Phone tripod still visible, like the livestream just ended\n"
            "- Table still has food remnants, but tidier\n"
            "- Warm evening glow, intimate cozy atmosphere\n"
            "- The mascot looks like a real physical toy figurine on the table, about 20cm tall\n"
            "- 9:16 portrait, photorealistic woman + 3D toy mascot\n"
            "- NO text, NO watermarks"
        )
    }
]

for scene in scenes:
    log(f"Generating {scene['name']}...")
    img_bytes = call_gemini_with_refs(scene["prompt"], scene["refs"])
    if img_bytes:
        out_path = OUT_DIR / f"{scene['name']}.png"
        out_path.write_bytes(img_bytes)
        log(f"  Saved: {out_path.name} ({len(img_bytes)} bytes)")
    else:
        log(f"  FAILED: {scene['name']}")
    time.sleep(2)

log("All live scenes done!")
