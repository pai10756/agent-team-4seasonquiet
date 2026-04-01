#!/usr/bin/env python3
"""Generate character turnaround + face reference from character.json.

Reads appearance/wardrobe/styling from character.json, auto-discovers face
reference images from the same directory, and outputs:
  1. character_turnaround.png — horizontal 3:2 (left 2 full-body, right 6 face close-ups)
  2. face_reference.jpg — single hero portrait for Seedance face-lock

用法:
  python scripts/gen_character_card.py characters/ep53_tea_host/character.json
  python scripts/gen_character_card.py characters/ep53_tea_host/character.json --output-dir test_output/seedance_tea_longevity
  python scripts/gen_character_card.py characters/ep53_tea_host/character.json --format-ref test_output/seedance_mediterranean/character_turnaround_v4.png

環境變數:
  GEMINI_API_KEY — Gemini API key
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

# Load .env
_env_file = BASE / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")


def log(msg):
    print(f"[gen_char] {msg}", file=sys.stderr, flush=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Gemini API call ──────────────────────────────────────

def call_gemini(parts, max_retries=5):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())

            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    if len(img_bytes) > 10 * 1024:
                        return img_bytes
                    log(f"  Image too small ({len(img_bytes)} bytes), retrying...")

            log(f"  No image in response (attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} (attempt {attempt + 1}): {body}")
            if e.code == 503:
                wait = 10 * (attempt + 1)
                log(f"  503 — waiting {wait}s...")
                time.sleep(wait)
                continue
        except Exception as e:
            log(f"  Error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    return None


def load_ref(path: Path, label: str):
    if path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode()
        mime = "image/png" if str(path).endswith(".png") else "image/jpeg"
        log(f"  Loaded reference: {path.name}")
        return [
            {"text": label},
            {"inlineData": {"mimeType": mime, "data": b64}},
        ]
    else:
        log(f"  WARNING: {path.name} not found, skipping")
        return []


# ── Build prompts from character.json ────────────────────

def build_identity_block(char: dict) -> str:
    """Build CHARACTER IDENTITY text from appearance fields."""
    app = char.get("appearance", {})
    face = app.get("face", {})
    hair = app.get("hair", {})
    makeup = app.get("makeup", {})

    lines = []
    ethnicity = app.get("ethnicity", "East Asian female")
    age = app.get("age_range", "23-26")
    lines.append(f"- {ethnicity}, age {age}")

    for key in ("shape", "skin", "eyes", "brows", "nose", "lips"):
        val = face.get(key)
        if val:
            lines.append(f"- {val.rstrip('.')}")

    if hair:
        parts = [v for k, v in hair.items() if k != "texture" and v]
        if parts:
            lines.append(f"- Hair: {', '.join(parts)}")

    overall_makeup = makeup.get("overall")
    if overall_makeup:
        lines.append(f"- Makeup: {overall_makeup}")
    else:
        makeup_parts = [v for k, v in makeup.items() if k != "_doc" and v]
        if makeup_parts:
            lines.append(f"- Makeup: {'; '.join(makeup_parts)}")

    return "\n".join(lines)


def build_outfit_block(char: dict) -> str:
    """Build OUTFIT text from wardrobe.primary or first wardrobe entry."""
    wardrobe = char.get("wardrobe", {})
    # Try keys in priority order
    for key_suffix in ("primary", "ep_primary"):
        for wk, wv in wardrobe.items():
            if key_suffix in wk and isinstance(wv, dict):
                return _format_outfit(wv)
    # Fallback: first entry
    for wk, wv in wardrobe.items():
        if isinstance(wv, dict) and "alternate" not in wk:
            return _format_outfit(wv)
    # Last resort
    for wk, wv in wardrobe.items():
        if isinstance(wv, dict):
            return _format_outfit(wv)
    return "- Casual, clean outfit matching brand palette"


def _format_outfit(outfit: dict) -> str:
    lines = []
    desc = outfit.get("description", "")
    color = outfit.get("color", "")
    material = outfit.get("material", "")
    fit = outfit.get("fit", "")
    accessories = outfit.get("accessories", "")

    main = desc
    if color and color not in desc:
        main += f" ({color})"
    if material:
        main += f", {material}"
    if fit:
        main += f", {fit}"
    lines.append(f"- {main}")

    if accessories:
        lines.append(f"- {accessories}")
    lines.append("- Bare feet (for full body shots)")
    return "\n".join(lines)


def build_turnaround_prompt(char: dict) -> str:
    identity = build_identity_block(char)
    outfit = build_outfit_block(char)

    return f"""Create a character turnaround reference sheet for video production.

LAYOUT (single 3:2 HORIZONTAL composite image, clean white/light gray studio background):
Left side (~40% width): TWO full-body shots stacked vertically (head to bare feet, standing on white floor):
  TOP: Front View — standing straight, relaxed posture, arms at sides, gentle smile, looking at camera
  BOTTOM: 3/4 Left View — body turned 45 degrees left, face still partly visible, same relaxed posture

Right side (~60% width): SIX head/shoulder close-up portraits in a 2x3 grid (2 columns × 3 rows):
  Row 1 LEFT: Front face — gentle smile, direct eye contact
  Row 1 RIGHT: 3/4 Left View — head turned 45 degrees left
  Row 2 LEFT: Warm genuine smile — eyes slightly crinkled, friendly, happy
  Row 2 RIGHT: Side Profile (Left) — full 90-degree left profile, showing nose bridge and jawline
  Row 3 LEFT: Surprised expression — slightly raised brows, mouth slightly open
  Row 3 RIGHT: Thinking expression — eyes looking slightly up, contemplative

CHARACTER IDENTITY (must match the FACE REFERENCE images EXACTLY — same person):
{identity}

OUTFIT:
{outfit}

CRITICAL RULES:
- ALL views must be the SAME person with IDENTICAL face, hair, makeup, and outfit
- Clean white/very light gray studio background, no props, no furniture
- Even soft studio lighting, no harsh shadows
- Photorealistic quality, NOT illustration, NOT cartoon
- No text labels on the image
- No watermarks, no logos, no AI marks
"""


def build_face_reference_prompt(char: dict) -> str:
    identity = build_identity_block(char)
    styling = char.get("scene_styling_notes", {})
    lighting = styling.get("lighting", "Warm golden-hour soft light from left, gentle fill from right, slight backlight rim glow on hair edges")
    bg = styling.get("background_mood", "Clean warm cream tone, very soft, no distracting elements, slight warm bokeh")
    color_grade = styling.get("color_grading", "Warm cream/amber, low saturation, slight film grain")

    # Get primary outfit description (short form)
    wardrobe = char.get("wardrobe", {})
    outfit_short = "Casual outfit"
    for wk, wv in wardrobe.items():
        if isinstance(wv, dict) and "alternate" not in wk:
            outfit_short = wv.get("description", outfit_short)
            break

    default_expr = char.get("appearance", {}).get("face", {}).get(
        "expression_default", "serene, contemplative, quiet confidence")

    return f"""Create a single portrait photograph for use as a face-lock reference in AI video generation.

COMPOSITION: Upper body portrait (head, shoulders, upper chest), centered, vertical 9:16 ratio (1080x1920).

CHARACTER (must match FACE REFERENCE images EXACTLY — same person):
{identity}

OUTFIT: {outfit_short}

EXPRESSION: {default_expr}

LIGHTING: {lighting}
BACKGROUND: {bg}
COLOR GRADE: {color_grade}

STYLE: Photorealistic editorial portrait, Sony A7IV, 85mm f/1.4, f/2.0, shallow DOF

FORBIDDEN: No watermarks, no logos, no text, no AI marks, no extra people, no cartoon style
"""


# ── Auto-discover reference images ───────────────────────

def find_face_refs(char_dir: Path) -> list:
    """Find existing face reference images in character directory and project root."""
    refs = []

    # Look for portrait/reference images in character dir
    for pattern in ("*portrait*.jpg", "*portrait*.png", "*reference*.jpg", "*reference*.png"):
        for p in sorted(char_dir.glob(pattern)):
            if p.name != "face_reference.jpg":  # skip our own output
                refs.append((p, f"FACE REFERENCE — the character must look like this person:"))
                break
        if refs:
            break

    # Look for common project-root reference images (農民曆工廠 output)
    for name in ("card_main_0331.jpg", "card_main.jpg"):
        p = BASE / name
        if p.exists():
            label = "FACE REFERENCE — the character must have THIS exact face:" if not refs else \
                    "SAME PERSON different styling — note the consistent facial features:"
            refs.append((p, label))

    # Check for hanfu/alternate styling refs
    for name in ("0401_card_main_hanfu.jpg",):
        p = BASE / name
        if p.exists() and len(refs) < 3:
            refs.append((p, "SAME PERSON different styling — note the consistent facial features:"))

    return refs


def find_format_ref() -> Path | None:
    """Find an existing turnaround to use as format reference."""
    candidates = [
        BASE / "test_output" / "seedance_mediterranean" / "character_turnaround_v4.png",
        BASE / "characters" / "ep53_tea_host" / "character_turnaround_v6.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ── Main ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate character turnaround + face reference from character.json")
    parser.add_argument("character_json", help="Path to character.json")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Output directory (default: same as character.json)")
    parser.add_argument("--format-ref", default=None,
                        help="Path to existing turnaround as layout reference")
    parser.add_argument("--skip-face-ref", action="store_true",
                        help="Skip face reference portrait generation")
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY or GOOGLE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    char_path = Path(args.character_json).resolve()
    char = load_json(char_path)
    char_dir = char_path.parent
    output_dir = Path(args.output_dir).resolve() if args.output_dir else char_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    char_name = char.get("character_name", "角色")
    char_name_en = char.get("character_name_en", "Character")
    log(f"Character: {char_name} ({char_name_en})")
    log(f"Source: {char_path}")
    log(f"Output: {output_dir}")

    # Discover references
    face_refs = find_face_refs(char_dir)
    format_ref_path = Path(args.format_ref) if args.format_ref else find_format_ref()

    # Build cards
    cards = [
        {
            "name": f"Character Turnaround ({char_name})",
            "prompt": build_turnaround_prompt(char),
            "output": "character_turnaround.png",
            "refs": face_refs[:],
        },
    ]
    if format_ref_path and format_ref_path.exists():
        cards[0]["refs"].append((
            format_ref_path,
            "FORMAT REFERENCE — use this EXACT layout (2 full-body on left, 6 face close-ups on right). "
            "Copy this grid arrangement but with the new character:"
        ))

    if not args.skip_face_ref:
        cards.append({
            "name": f"Face Reference ({char_name})",
            "prompt": build_face_reference_prompt(char),
            "output": "face_reference.jpg",
            "refs": face_refs[:2],  # only face refs, no format ref
        })

    results = []
    for card in cards:
        log(f"\n{'=' * 50}")
        log(f"Generating: {card['name']}")
        log(f"{'=' * 50}")

        parts = []
        for ref_path, label in card["refs"]:
            parts.extend(load_ref(ref_path, label))
        parts.append({"text": card["prompt"]})

        img_bytes = call_gemini(parts)
        if img_bytes:
            out_path = output_dir / card["output"]
            out_path.write_bytes(img_bytes)
            log(f"OK: {out_path} ({len(img_bytes):,} bytes)")
            results.append({"name": card["name"], "path": str(out_path), "success": True})
        else:
            log(f"FAILED: {card['name']}")
            results.append({"name": card["name"], "success": False})

        time.sleep(5)

    log(f"\n{'=' * 50}")
    log("RESULTS:")
    for r in results:
        status = f"OK -> {r['path']}" if r["success"] else "FAILED"
        log(f"  {r['name']}: {status}")

    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_ok = all(r["success"] for r in results)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
