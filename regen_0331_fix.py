#!/usr/bin/env python3
"""Regenerate card_main and card_action for 2026-03-31 with corrected weekday."""
import os, json, base64, urllib.request, time, sys
from pathlib import Path

BASE = Path("/home/shany/.openclaw/data-radix/almanac_factory")

# Load API key
for line in (BASE / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

GOOGLE_KEY = os.environ["GOOGLE_API_KEY"]

def gen(card_key, out_name):
    prompt = (BASE / f"outputs/prompts/2026-03-31_{card_key}.txt").read_text()
    full = (
        "Generate a high-quality vertical portrait image (9:16 ratio, 1080x1920) "
        "for a YouTube Shorts video about Chinese almanac. " + prompt
    )
    models = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
    for model in models:
        for attempt in range(2):
            print(f"[{out_name}] {model} attempt {attempt+1}", flush=True)
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={GOOGLE_KEY}"
            )
            payload = json.dumps({
                "contents": [{"parts": [{"text": full}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST"
            )
            try:
                print("  Calling API...", flush=True)
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read())
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        raw = base64.b64decode(part["inlineData"]["data"])
                        if part["inlineData"].get("mimeType") == "image/png":
                            try:
                                from PIL import Image
                                import io
                                buf = io.BytesIO()
                                Image.open(io.BytesIO(raw)).convert("RGB").save(buf, format="JPEG", quality=95)
                                raw = buf.getvalue()
                            except Exception:
                                pass
                        out = BASE / f"outputs/assets/2026-03-31/{out_name}"
                        out.write_bytes(raw)
                        print(f"  OK {len(raw):,} bytes -> {out}", flush=True)
                        return True
                print("  No image in response", flush=True)
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "text" in part:
                        print(f"  Text: {part['text'][:200]}", flush=True)
            except Exception as e:
                print(f"  Error: {e}", flush=True)
                time.sleep(8)
    print(f"  FAILED all attempts for {out_name}", flush=True)
    return False

print("=== Regenerating card_main (card1) ===", flush=True)
ok1 = gen("card1", "card_main.jpg")
time.sleep(3)
print("=== Regenerating card_action (card3) ===", flush=True)
ok3 = gen("card3", "card_action.jpg")

if ok1 and ok3:
    print("\nBoth cards regenerated successfully!", flush=True)
elif ok1:
    print("\nOnly card_main succeeded, card_action failed", flush=True)
elif ok3:
    print("\nOnly card_action succeeded, card_main failed", flush=True)
else:
    print("\nBoth cards failed!", flush=True)
