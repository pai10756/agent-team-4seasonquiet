"""Batch generate Card 02-05 via Gemini 3.1 Flash Image API."""

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "test_output" / "cards_10000steps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = "AIzaSyAaVV42BhssBY01VWqr6K7V2JLfGRDD00s"
MODEL = "gemini-3.1-flash-image-preview"

CARDS = {
    "card02": """A vertical 9:16 health comparison card (1080x1920).

Top: Large bold Chinese headline "一萬步＝60年前的廣告" in dark olive (#4E5538). Subtitle "1964年日本計步器的行銷口號" in brown (#3B2A1F).

Split layout with thin vertical dividing line:
- Left side: A vintage 1960s Japanese mechanical pedometer (manpo-kei) with retro design, sepia-toned, old-fashioned feel. Label: "廣告口號"
- Right side: A modern medical research journal/paper with clean design, bright and scientific feel. Label: "科學研究"

Top-right corner: A small sage green (#A8B88A) rounded badge with text "1964 東京奧運" in olive dark text.

Background: Clean cream (#F6F1E7) with subtle paper texture, warm lighting. No mascot, no human faces. Clean infographic style.

IMPORTANT: No watermark, no logo, no signature, no star symbol. The image must be completely clean.""",

    "card03": """A vertical 9:16 health data comparison card (1080x1920).

Top: Large bold Chinese headline "6000步 vs 10000步" in dark olive (#4E5538). Subtitle "死亡風險降幅幾乎一樣！" in brown (#3B2A1F).

Center: Simple clean infographic comparing two options:
- Left: A walking shoe icon with "6,000步" label and a large green checkmark, text "死亡風險 -50%"
- Right: A walking shoe icon with "10,000步" label and a yellow equals sign, text "風險沒有更低"
- Two horizontal bars below, nearly the same height, showing diminishing returns visually. The 6000 bar is green, the 10000 bar is only slightly taller in yellow-gray.

Bottom-right: Source badge "Lancet 2022 · 47,471人" in sage green rounded rectangle.

Background: Clean cream to white gradient (#F6F1E7), sage green accents. Minimal, modern infographic. No mascot, no human faces.

IMPORTANT: No watermark, no logo, no signature, no star symbol. The image must be completely clean.""",

    "card04": """A vertical 9:16 health evidence card (1080x1920).

Top: Large bold Chinese headline "3000→7000步，風險降50%" in dark olive (#4E5538). Subtitle "每週走1-2天也有效！" in brown (#3B2A1F).

Center: A clean dose-response curve infographic:
- X-axis: daily steps from 3,000 to 12,000
- Y-axis: mortality risk reduction
- The curve drops steeply from 3,000 to 7,000 steps, then flattens dramatically after 8,000
- A highlighted green zone between 6,000-8,000 steps labeled "最佳區間" in sage green
- The flat zone after 8,000 labeled "效益趨平"

Bottom-right: Source badge "Lancet 2025" in sage green rounded rectangle.

Background: Clean cream (#F6F1E7) with subtle grid lines, modern scientific infographic style. No mascot, no human faces.

IMPORTANT: No watermark, no logo, no signature, no star symbol. The image must be completely clean.""",

    "card05": """A vertical 9:16 health safety reminder card (1080x1920).

Top: Large bold Chinese headline "走對比走多更重要" in dark olive (#4E5538). Subtitle "膝蓋不好，量力而行" in brown (#3B2A1F).

Center: A pair of comfortable walking shoes on a gentle park path, soft morning sunlight. Warm, reassuring, healthy lifestyle photography. A subtle protective shield icon near a knee joint illustration, small and non-alarmist.

Overall mood: Peaceful, gentle, encouraging. NOT medical, NOT scary.

Background: Morning park path with gentle sunlight filtering through trees, warm cream and sage green color palette. 75% photorealistic. No mascot, no human faces, no running or intense exercise imagery.

IMPORTANT: No watermark, no logo, no signature, no star symbol. The image must be completely clean.""",
}


def call_gemini(prompt: str, card_name: str) -> bool:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

    parts = [{"text": prompt}]

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()

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
                out_path = OUTPUT_DIR / f"{card_name}.png"
                out_path.write_bytes(img_bytes)
                print(f"  OK — {out_path} ({len(img_bytes)} bytes)")
                return True

        print(f"  ERROR: No image in response")
        return False

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        print(f"  HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    for card_name, prompt in CARDS.items():
        print(f"\n[{card_name}] Generating...")
        success = call_gemini(prompt, card_name)
        if not success:
            print(f"  FAILED — skipping")
        # Rate limit: wait between calls
        time.sleep(5)

    print("\nDone!")


if __name__ == "__main__":
    main()
