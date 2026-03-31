import base64, json, os, sys, time, urllib.request
from pathlib import Path

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-flash-image-preview"
OUT_DIR = Path(__file__).parent
MASCOT_REF = OUT_DIR / "mascot_turnaround.png"

def log(msg):
    print(f"[scene] {msg}", file=sys.stderr)

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

scenes = [
    ("live_bg01_opening", None,
     "A realistic modern Taiwanese apartment living room set up as a LIVESTREAM station. NO PEOPLE in the scene. "
     "On a wooden kitchen island table: a bottle of cheap yellow vegetable oil standing upright, "
     "next to a dark green bottle of extra virgin olive oil. A small bowl of mixed nuts, a wooden cutting board, "
     "and a smartphone on a small tripod pointing toward where the host would sit. "
     "Behind the table: a cozy lived-in living room with grey sofa, wooden bookshelf with books and plants, "
     "a warm floor lamp turned on, some green potted plants. "
     "A ring light is visible at the right edge, glowing warm. "
     "Warm mixed lighting: ring light glow + ceiling light + floor lamp. "
     "Slightly messy, authentic home feel. Evening atmosphere. "
     "9:16 portrait orientation. Photorealistic, iPhone-quality feel. "
     "ABSOLUTELY NO PEOPLE, NO HANDS, NO BODY PARTS visible. NO text, NO watermarks."),

    ("live_bg02_show_oil", None,
     "Close-up of a beautiful extra virgin olive oil bottle on a wooden table, golden oil visible through glass. "
     "Next to it: a colorful Mediterranean salad bowl (cherry tomatoes, cucumbers, olives, feta cheese, basil), "
     "some scattered walnuts, a small white plate of green olives. "
     "Background: blurred cozy apartment living room with ring light glow, smartphone on tripod visible but blurred. "
     "Warm ring light reflection on the oil bottle surface. "
     "Shallow depth of field, oil bottle sharp, background soft bokeh. "
     "9:16 portrait orientation. Photorealistic, food photography quality. "
     "ABSOLUTELY NO PEOPLE, NO HANDS, NO BODY PARTS visible. NO text, NO watermarks."),

    ("live_bg03_compare", None,
     "Two plates side by side on a wooden table, seen from above (flat lay / top-down view). "
     "LEFT plate: plain, pale, boring - steamed chicken breast and steamed broccoli on a white plate. Dull lighting. "
     "RIGHT plate: vibrant, colorful, appetizing - grilled salmon with avocado slices, cherry tomatoes, "
     "olive oil drizzle, fresh herbs on a decorative plate. Bright warm lighting. "
     "The contrast should be dramatic: left side looks sad/bland, right side looks delicious/inviting. "
     "Background: wooden table surface, ring light reflection visible as a circle highlight on the table. "
     "9:16 portrait orientation. Photorealistic, food photography. "
     "ABSOLUTELY NO PEOPLE, NO HANDS, NO BODY PARTS visible. NO text, NO watermarks."),

    ("live_bg04_data", None,
     "A bold livestream-style data overlay graphic. "
     "Giant red/coral number 31% in the center with a subtle glow effect. "
     "Below it: Chinese text 心血管风险降低 in bold white. "
     "A red heart icon, slightly tilted, above the number. "
     "Small citation banner at bottom: PREDIMED N Engl J Med 2018. "
     "The card has a glass-morphism drop shadow, like a floating livestream pop-up. "
     "Background: warm blurred bokeh of an apartment room with out of focus warm lights. "
     "Modern livestream graphics style, bold, high contrast, not clinical. "
     "9:16 portrait orientation. NO other text, NO watermarks, NO people."),

    ("live_bg05_eating", None,
     "A beautiful spread of Mediterranean food on a wooden dining table in a cozy apartment, evening setting. "
     "NO PEOPLE visible. "
     "On the table: a plate of grilled salmon with lemon wedges and fresh dill, "
     "a small bowl of mixed nuts (walnuts and almonds), a glass cruet of olive oil, "
     "some whole grain bread slices, a small plate of olives, a glass of water, wooden chopsticks resting on the plate. "
     "A smartphone on tripod visible at the edge of frame. Ring light glow from the side, dimmer now. "
     "Floor lamp warm glow in background. Edge of sofa visible. "
     "Evening intimate atmosphere, like someone just finished a livestream and is about to eat. "
     "9:16 portrait orientation. Photorealistic, warm tones. "
     "ABSOLUTELY NO PEOPLE, NO HANDS, NO BODY PARTS visible. NO text, NO watermarks."),

    ("live_bg06_mascot", MASCOT_REF,
     "Using the mascot reference image, generate a scene: "
     "The small 3D leopard cat mascot (smooth matte plastic toy, sage green apron) is sitting on a wooden dining table, "
     "hugging an olive oil bottle with both paws, looking up toward camera with a happy expression. "
     "Its spotted tail is curled around the base of the bottle. "
     "Around the mascot on the table: remnants of a Mediterranean meal (half-eaten salmon plate, "
     "olive bowl, scattered nuts), a smartphone on tripod in the background. "
     "Same apartment living room background: floor lamp warm glow, ring light dimmed, evening cozy atmosphere. "
     "The mascot looks like a real physical toy figurine placed on the table, about 20cm tall. "
     "9:16 portrait orientation. Photorealistic environment + 3D toy mascot. "
     "NO PEOPLE, NO HANDS visible. Only the mascot. NO text, NO watermarks.")
]

for name, ref, prompt in scenes:
    log(f"Generating {name}...")
    img_bytes = call_gemini(prompt, ref_path=ref)
    if img_bytes:
        out_path = OUT_DIR / f"{name}.png"
        out_path.write_bytes(img_bytes)
        log(f"  Saved: {name}.png ({len(img_bytes)} bytes)")
    else:
        log(f"  FAILED: {name}")
    time.sleep(2)

log("All background scenes done!")
