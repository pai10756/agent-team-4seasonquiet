#!/usr/bin/env python3
"""Regenerate card_main for 2026-04-01 with hanfu cinematic style."""
import os, json, base64, urllib.request, time, sys
from pathlib import Path

BASE = Path("/home/shany/.openclaw/data-radix/almanac_factory")
for line in (BASE / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

GOOGLE_KEY = os.environ["GOOGLE_API_KEY"]

prompt = (BASE / "outputs/prompts/2026-04-01_card1.txt").read_text()
full = (
    "Generate a high-quality vertical portrait image (9:16 ratio, 1080x1920) "
    "for a YouTube Shorts video about Chinese almanac. " + prompt
)

model = "gemini-3.1-flash-image-preview"
for attempt in range(3):
    print(f"[card_main.jpg] {model} attempt {attempt+1}", flush=True)
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
                out = BASE / "outputs/assets/2026-04-01/card_main.jpg"
                out.write_bytes(raw)
                print(f"  OK {len(raw):,} bytes", flush=True)
                sys.exit(0)
        print("  No image in response", flush=True)
    except Exception as e:
        print(f"  Error: {e}", flush=True)
        time.sleep(8)

print("FAILED", flush=True)
sys.exit(1)
