"""EP54 園藝也是運動 — 全素材重新生成
修正：
1. 主角臉孔改用農民曆工廠 card_main_0331 精確描述
2. 小靜定裝照用 3d_reference_clean.jpg 精確文字描述
3. 場景圖全部無人臉（純環境），結尾只有小靜
"""
import json, subprocess, base64, sys, time, os
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent

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


def log(msg):
    print(f"[regen] {msg}", file=sys.stderr, flush=True)


def gen(name, prompt, ext="jpg"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    })
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", "Content-Type: application/json",
                 "-d", "@-", "--max-time", "180"],
                input=payload, capture_output=True, text=True, timeout=200
            )
            if not result.stdout.strip():
                log(f"  {name} attempt {attempt+1}: empty response")
                time.sleep(15)
                continue
            data = json.loads(result.stdout)
            if "error" in data:
                log(f"  {name} attempt {attempt+1} ERROR: {data['error'].get('message', '')[:120]}")
                time.sleep(15)
                continue
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img = base64.b64decode(part["inlineData"]["data"])
                    if len(img) > 10000:
                        out_path = OUT / f"{name}.{ext}"
                        out_path.write_bytes(img)
                        log(f"  OK: {name}.{ext} ({len(img):,} bytes)")
                        return True
            log(f"  {name} attempt {attempt+1}: no image in response")
        except Exception as e:
            log(f"  {name} attempt {attempt+1} exception: {e}")
        time.sleep(15)
    log(f"  FAILED: {name}")
    return False


# ══════════════════════════════════════════
# 農民曆工廠 card_main_0331 精確臉部描述
# ══════════════════════════════════════════
FACE_0331 = (
    "Beautiful Korean-style East Asian female, age 23-25. "
    "Face: gentle square jaw with soft V-line contour, high cheekbones, small delicate chin. "
    "Eyes: gentle downturned monolid-to-subtle-double-eyelid eyes, dark brown iris, soft feminine gaze. "
    "Brows: straight fluffy textured brows, natural and groomed. "
    "Nose: high straight bridge, refined small tip, delicate nostrils. "
    "Lips: subtle natural pout, soft gradient pink lips (inner pink fading outward), petite mouth. "
    "Skin: flawless porcelain-clear complexion, dewy luminous glass skin, no blemishes, no freckles. "
    "Hair: long straight dark black-brown hair, center-parted, silky smooth, tucked behind ears. "
    "Makeup: Korean glass-skin base, barely-there soft peach blush, gradient glossy lips, "
    "clean bare eyelids with zero eyeshadow, no false lashes, natural brows. "
    "Aura: serene, elegant, quietly confident, editorial clean beauty."
)

# ══════════════════════════════════════════
# 小靜 3d_reference_clean.jpg 精確描述
# ══════════════════════════════════════════
MASCOT_DESC = (
    "A 3D smooth matte plastic toy figure of a Taiwanese leopard cat, Pop Mart / Sonny Angel quality. "
    "EXACT DESIGN: Very large round head (head-to-body ratio approximately 1:1), super-deformed cute proportion. "
    "FACE: warm golden-yellow-brown matte plastic. "
    "Two PROMINENT thick white vertical stripes running from forehead down between the eyes. "
    "Dark brown curved eyebrow-like markings above each eye. "
    "Two dark brown tear-line markings running from inner eye corners down cheeks. "
    "Big round dark brown eyes with large white circular highlight dots (eyes about 35% of face width). "
    "Small pink triangular nose. Simple curved smile line mouth. "
    "Cream/off-white cheek and chin area with smooth gradient transition. "
    "EARS: black with small white spots on back of each ear, slightly rounded shape. "
    "BODY: warm golden-yellow-brown with scattered round dark brown SPOTS "
    "(NOT stripes, NOT tabby pattern) on arms, sides, and legs. "
    "Cream/off-white belly area. Short stubby limbs. "
    "Short tail with dark ring markings. "
    "APRON: mint/sage green (#A8B88A) apron covering front torso, "
    "with a white bowl-with-leaf-sprout icon centered on chest. "
    "MATERIAL: smooth matte plastic surface, low gloss, very soft diffused shadows, "
    "no fur texture, no pores, no realistic animal features. "
    "LIGHTING: soft studio lighting from front-top, muted pastel sage green background."
)


# ══════════════════════════════════════════
# 生成任務清單
# ══════════════════════════════════════════
all_tasks = [
    # ── 1. 角色定裝照（有臉）──
    (
        "character_turnaround",
        (
            "3:2 horizontal character turnaround sheet, pure clean white background. "
            f"Character: {FACE_0331} "
            "Outfit for this episode: cream linen button-up shirt with sleeves rolled to elbows, "
            "over a sage green cotton tank top visible at the V-neck opening. "
            "Khaki wide-leg cropped pants. Canvas garden shoes. "
            "Hair styled in a low ponytail with soft face-framing strands for practical outdoor look. "
            "Layout: Left side (60% width) two large images stacked vertically: "
            "1) Full-body front view standing pose (relaxed stance, arms at sides). "
            "2) Full-body 90-degree side view standing pose. "
            "Right side (40% width) 2x3 grid of six head close-ups: "
            "1) Head front view neutral 2) Head back view showing ponytail "
            "3) Left 45-degree 4) Right 45-degree "
            "5) Expression: happy warm smile with crinkled eyes "
            "6) Expression: surprised excited with wide eyes and slightly open mouth. "
            "High-end realistic studio photography, sharp eyes in focus, "
            "real skin micro-texture, consistent exposure, 8K detail, light film grain, "
            "ultra-clean white background. "
            "NO readable text, NO labels, NO watermarks, NO cartoon, NO anime."
        ),
        "png"
    ),

    # ── 2. 臉部特寫（有臉）──
    (
        "face_reference",
        (
            "Single portrait close-up, 3:4 ratio. "
            f"{FACE_0331} "
            "Hair in a low ponytail with wispy face-framing strands. "
            "Wearing cream linen shirt collar visible at shoulders. "
            "Tight crop: face and upper shoulders only. "
            "Front-facing with slight 10-degree turn to the left. "
            "Warm natural golden-hour outdoor light from upper-right. "
            "Expression: warm approachable smile, eyes looking directly at camera. "
            "Clean soft-focus garden background with green bokeh. "
            "Photorealistic, 8K detail, real skin texture visible. "
            "NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 3. 小靜定裝照 ──
    (
        "mascot_turnaround",
        (
            "3:2 horizontal character turnaround sheet, muted pastel sage green background. "
            f"{MASCOT_DESC} "
            "For this garden episode: holding a tiny mint-green watering can in one paw as a prop. "
            "Layout: Left side (60% width) two views stacked vertically: "
            "1) Full-body front view standing, holding tiny watering can in left paw, "
            "right paw raised in a friendly wave. "
            "2) Full-body 45-degree three-quarter view, same pose. "
            "Right side (40% width) 2x3 grid of six head/expression close-ups: "
            "1) Front face default gentle smile "
            "2) Left 45-degree view "
            "3) Right 45-degree view "
            "4) Happy excited expression (crescent squinting eyes, big joyful smile) "
            "5) Curious expression (head tilted, one paw on chin) "
            "6) Waving goodbye (one paw raised, sweet smile). "
            "Clean consistent 3D render quality throughout all panels. "
            "NO text labels on any panel, NO watermarks, NO realistic fur texture."
        ),
        "png"
    ),

    # ── 4. scene01 hook（無人臉）──
    (
        "scene01_hook",
        (
            "9:16 vertical portrait (1080x1920). A beautiful community garden in golden morning light. "
            "Close-up of two hands wearing cotton garden gloves pressing dark rich soil "
            "around a small green seedling in a wooden raised bed. "
            "ONLY hands and forearms visible, NO face, NO full person visible. "
            "A galvanized metal watering can and small garden trowel beside the hands on the soil. "
            "Lush green vegetable rows stretching into the background. "
            "Warm golden morning sunlight creating long shadows and dappled light through nearby trees. "
            "Photorealistic outdoor documentary quality, shallow depth of field, "
            "warm earthy golden-green color grading. "
            "NO human face, NO full person, NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 5. scene02 flip data（無人臉）──
    (
        "scene02_flip_data",
        (
            "9:16 vertical portrait (1080x1920). A lush community garden scene, NO PEOPLE at all. "
            "A wooden raised bed overflowing with mature vegetables: "
            "leafy greens, ripe red tomatoes on vines, fresh basil and rosemary herbs. "
            "A pair of garden gloves and a hand trowel resting on the wooden bed edge. "
            "Morning golden light from the left side, garden path visible leading to more beds. "
            "Dew drops glistening on leaves. Warm, inviting, productive garden atmosphere. "
            "Photorealistic outdoor documentary, shallow DOF, warm golden-green tones. "
            "NO people, NO face, NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 6. scene03 exercise compare（無人臉）──
    (
        "scene03_exercise_compare",
        (
            "9:16 vertical portrait (1080x1920). Garden tools arranged artistically on dark rich soil, "
            "NO PEOPLE at all. "
            "Center: a sturdy garden spade stuck upright in loose soil. "
            "Around it: pruning shears, a hand rake, garden gloves, a foam kneeling pad. "
            "A pair of running shoes placed next to the garden tools "
            "(visual metaphor: gardening equals exercise). "
            "Background: vegetable garden rows with herbs and leafy greens in soft bokeh. "
            "Warm morning light, earthy tones. "
            "Photorealistic, warm earthy color grading, shallow DOF. "
            "NO people, NO face, NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 7. scene04 mental health（無人臉）──
    (
        "scene04_mental_health",
        (
            "9:16 vertical portrait (1080x1920). A beautiful blooming garden in golden light, "
            "NO PEOPLE at all. "
            "Colorful flowers in full bloom: hydrangeas, roses, lavender, marigolds, "
            "alongside neat green vegetable beds. "
            "A wooden garden bench with a straw hat and a small harvest basket "
            "overflowing with fresh herbs and cherry tomatoes. "
            "Golden light filtering through tree canopy above, "
            "creating beautiful dappled shadow patterns on the ground and bench. "
            "Peaceful, therapeutic, accomplished garden atmosphere. "
            "Photorealistic lifestyle photography, shallow DOF, warm golden tones. "
            "NO people, NO face, NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 8. scene05 reminder（無人臉）──
    (
        "scene05_reminder",
        (
            "9:16 vertical portrait (1080x1920). A garden rest station, NO PEOPLE at all. "
            "A low wooden garden bench under a pergola with climbing green vines providing dappled shade. "
            "On the bench: a woven straw sun hat, a clear water bottle half-full, "
            "a tube of sunscreen, and folded garden gloves. "
            "Beside the bench on the ground: a small wicker basket overflowing "
            "with freshly harvested herbs and vegetables. "
            "Bright outdoor sunlight beyond the pergola shade, warm contrast between light and shadow. "
            "Warm, caring, protective atmosphere. "
            "Photorealistic, warm tones, shallow DOF. "
            "NO people, NO face, NO text, NO watermarks."
        ),
        "jpg"
    ),

    # ── 9. 結尾場景（只有小靜，無人臉）──
    (
        "live_scene06_mascot",
        (
            "9:16 vertical portrait (1080x1920). "
            "A garden bench scene with ONLY a 3D toy mascot character, "
            "absolutely NO human, NO human face anywhere in the image. "
            f"{MASCOT_DESC} "
            "The 3D leopard cat toy figure is sitting on top of a large terracotta flower pot "
            "next to a wooden garden bench. "
            "It holds a tiny watering can in one paw and waves with the other paw. "
            "Happy expression with crescent squinting eyes and big smile. "
            "On the bench beside the pot: a small basket of fresh herbs. "
            "Around: colorful flowers, green plants, warm golden afternoon light. "
            "The mascot is the ONLY character in the entire image. "
            "Warm garden atmosphere, soft golden-hour lighting, shallow DOF. "
            "Photorealistic garden background with 3D toy character element. "
            "NO human, NO human face, NO text, NO watermarks."
        ),
        "jpg"
    ),
]


if __name__ == "__main__":
    if not API_KEY:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    results = []
    for name, prompt, ext in all_tasks:
        log(f"\nGenerating {name}...")
        ok = gen(name, prompt, ext)
        results.append((name, ok))
        time.sleep(12)  # Gemini free tier: ~15 RPM, 10-12s between image gen requests

    log("\n" + "=" * 50)
    log("RESULTS:")
    for name, ok in results:
        log(f"  {name}: {'OK' if ok else 'FAILED'}")
