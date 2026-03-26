"""
Card Evaluator — 多模態 LLM 視覺評審，對圖卡做結構化多維評分。

靈感來自 Karpathy/autoresearch：用量化指標驅動自主迭代。
autoresearch 用 val_bpb；我們用多模態 LLM 看圖打分。

Usage:
  python scripts/evaluate_card.py <image_path> --scene-json <episode.json> --scene-id 01
  python scripts/evaluate_card.py <image_path>                # 僅視覺評分，不比對劇本
  python scripts/evaluate_card.py test_output/cards_ep52/ --all  # 批次評所有 card*.png

Environment:
  GEMINI_API_KEY — Gemini API key (uses gemini-2.5-flash for evaluation)
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EVAL_MODEL = "gemini-2.5-flash"


def log(msg: str):
    print(f"[eval] {msg}", file=sys.stderr)


# ── Gemini text API ──────────────────────────────────────

def call_gemini_text(parts: list, max_retries: int = 3) -> dict | None:
    """Call Gemini for text/JSON response with image input."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{EVAL_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())

            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if text:
                return json.loads(text)
            log(f"  Empty response (attempt {attempt + 1})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            log(f"  HTTP {e.code} (attempt {attempt + 1}): {body}")
        except (json.JSONDecodeError, KeyError) as e:
            log(f"  Parse error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            import time
            time.sleep(2 ** attempt)

    return None


# ── Evaluation rubric ────────────────────────────────────

RUBRIC = """你是一位極度嚴格的 YouTube Shorts 圖卡視覺評審。你的評分標準非常高——只有真正專業級的圖卡才配得上 8 分以上。你必須像一位挑剔的設計總監一樣評分，不輕易給高分。

重要原則：
- 你必須嚴格比對「劇本資訊」（如有提供），圖卡內容必須與劇本一致，不一致就要大扣分
- 不要「看到什麼就評什麼」——要評「它該是什麼 vs 它實際是什麼」的落差
- 7 分 = 合格但普通，8 分 = 良好，9 分 = 優秀，10 分 = 完美無瑕（極少給出）

## 評分維度（每項 0-10 分）

### 1. headline_impact（標題衝擊力）— 權重 20%
標竿：標題文字要像 YouTube 縮圖一樣巨大搶眼。在手機上（5.5 吋螢幕）必須一眼就能讀完。
- 主標題應佔畫面寬度 60%+ 且高度 15%+，字體必須是粗體或超粗體
- 標題必須是圖卡上最大、最顯眼的元素，不能被背景或其他元素搶走
- 標題位置應在上方 1/3（視覺黃金區），不能藏在中間或底部
- 副標題要明顯比主標題小，形成清晰的視覺層次
- 10 分：標題像喊出來一樣大，佔據畫面主導地位，瞬間抓住注意力（極少）
- 8 分：標題大且醒目，能在 2 秒內讀完
- 6 分：標題可讀但不夠突出，容易被忽略
- 4 分：標題明顯太小，需要刻意去找才看得到
- 2 分：標題被背景吃掉或嚴重偏離黃金區
- 0 分：幾乎看不到標題

### 2. safe_zone（Shorts 安全區）— 權重 15%
Shorts 底部 20%（y=1536 以下）會被平台 UI（標題、按讚、留言按鈕）完全遮住。
- 底部 20% 絕對不能有任何文字、badge、來源標註
- 底部 20% 也不應有重要的視覺元素主體（如食物、小靜的臉）
- 來源標註（source badge）應放在中下偏上，離底部至少 25%
- 10 分：所有文字與重要元素都在上方 75% 內
- 8 分：所有文字在安全區內，僅有次要裝飾元素在底部
- 5 分：有來源標註或次要文字在底部 20%
- 2 分：有主標題或關鍵數據在底部 20%
- 0 分：主要內容被 Shorts UI 遮住

### 3. text_quality（文字品質與劇本一致性）— 權重 15%
這個維度同時評「文字呈現品質」和「與劇本內容的一致性」。
- 圖卡上的主標題必須與劇本的 on_screen_text_main 一致或高度相近
- 圖卡上的副標題必須與劇本的 on_screen_text_sub 一致或高度相近
- 如果圖卡出現劇本沒有的文字 → 扣分（幻覺）
- 如果圖卡缺少劇本要求的文字 → 扣分
- 所有文字必須是正確繁體中文，不可有英文（包括產品包裝、圖表標籤）
- 不可有亂碼、簡體字、錯字
- 10 分：文字與劇本完全一致，全部正確繁體中文，排版完美
- 7 分：文字大致正確但有 1-2 處與劇本不符或有小問題
- 4 分：主標題與劇本不同，或有明顯英文出現
- 2 分：內容嚴重偏離劇本
- 0 分：亂碼或文字完全錯誤

### 4. visual_realism（視覺真實感與美感）— 權重 15%
- 攝影風格卡：食物/場景是否像專業攝影？光影是否合理自然？有無 AI 偽影（多餘手指、融化邊緣、不自然紋理）？
- 插圖/資訊圖卡：向量圖形是否乾淨精緻？配色是否和諧？圖標是否專業？還是看起來很廉價？
- 3D 小靜：是否與 reference 完全一致？材質是否正確的磨砂塑膠？有無變形？
- 整體：畫面是否有雜訊或模糊？解析度是否足夠？
- 10 分：專業攝影師/設計師水準，看不出 AI 生成
- 7 分：整體不錯但能看出一些 AI 特徵
- 4 分：明顯 AI 生成感，有偽影或不自然處
- 2 分：嚴重偽影，視覺品質差
- 0 分：完全不可用

### 5. composition（構圖與資訊層次）— 權重 15%
- 視覺動線是否清晰？觀眾的眼睛應該走：標題→主視覺→輔助資訊→來源
- 元素間距是否舒適？不能太擠也不能太空
- 如果劇本要求特定佈局（如時間軸、左右對比），圖卡是否按要求執行？
- 主視覺（hero object）是否突出且與主題高度相關？
- 資訊圖表的數據是否直覺易懂？
- 有無不相關的裝飾元素干擾（與主題無關的食物、圖案等）？
- 10 分：構圖完美，完全按劇本佈局，一目瞭然
- 7 分：構圖合理但有 1-2 處可改進
- 4 分：佈局與劇本要求不同，或有明顯不相關元素
- 2 分：混亂難讀
- 0 分：完全無法理解圖卡在表達什麼

### 6. brand_consistency（品牌一致性）— 權重 10%
品牌「時時靜好」的視覺系統非常明確，任何偏離都要扣分。
- 色盤必須是：cream #F6F1E7（背景）/ sage #A8B88A（強調）/ olive #4E5538（標題）/ brown #3B2A1F（副文字）
- 如果背景不是 cream 色 → 扣分
- 如果標題不是 olive dark 色 → 扣分
- 整體風格必須是「溫暖、知性、成熟、乾淨」，不能是醫療感、廉價感、兒童感
- 不可出現非品牌的 logo、icon、圖標（如 UN logo、醫療符號等非品牌元素）
- 10 分：色盤完全正確，風格完美符合品牌
- 7 分：大致符合但有 1-2 處色彩偏差
- 4 分：明顯使用非品牌色或風格偏離
- 2 分：完全不像「時時靜好」品牌
- 0 分：與品牌毫無關聯

### 7. no_artifacts（無多餘元素）— 權重 10%
- 有無 AI 浮水印（右下角星星、鑽石、SynthID）？
- 有無不該出現的文字（如 "Badge"、像素座標 "y=1536"、英文標籤）？
- 有無重複或多餘的裝飾元素？
- 有無不該出現的 UI 按鈕、分享按鈕等？
- 有無劇本 do_not_include 清單裡的禁止元素？
- 10 分：完全乾淨，零瑕疵
- 7 分：有 1 個微小瑕疵但不影響觀看
- 4 分：有明顯不該出現的元素
- 0 分：多個嚴重的多餘元素

## 嚴格評分校準

你必須用以下標準校準自己的評分：
- 一張「普通合格」的 AI 生成圖卡大約是 60-70 分（Grade C-B）
- 一張「不錯但有瑕疵」的圖卡大約是 70-80 分（Grade B-A）
- 只有「接近專業設計師水準」的圖卡才配 85+ 分（Grade A+）
- 90+ 分（Grade S）意味著「可以直接上傳 YouTube，無需任何修改」
- 如果你對某個維度猶豫要給 8 還是 9，給 8
- 如果圖卡與劇本不一致，text_quality 和 composition 都要扣分

## 輸出格式

請用以下 JSON 格式回覆，scores 每項 0-10 整數，remarks 每項用一句話具體說明扣分原因（不要只說「不錯」或「良好」，要指出具體問題）：

{
  "scores": {
    "headline_impact": <int>,
    "safe_zone": <int>,
    "text_quality": <int>,
    "visual_realism": <int>,
    "composition": <int>,
    "brand_consistency": <int>,
    "no_artifacts": <int>
  },
  "weighted_score": <float 0-100>,
  "grade": "<S/A/B/C/D>",
  "remarks": {
    "headline_impact": "<具體說明標題大小、位置、可讀性的問題>",
    "safe_zone": "<具體指出哪些元素在危險區>",
    "text_quality": "<具體指出與劇本的差異、英文、錯字等>",
    "visual_realism": "<具體指出 AI 偽影、不自然處>",
    "composition": "<具體指出佈局問題、與劇本要求的差異>",
    "brand_consistency": "<具體指出哪些色彩/風格偏離品牌>",
    "no_artifacts": "<具體指出多餘元素>"
  },
  "top_issue": "<最需要改善的一件事，要具體>",
  "prompt_suggestion": "<對生成 prompt 的一個具體、可操作的修改建議>"
}

grade 標準：
- S: weighted_score >= 90（可直接上線，極少）
- A: 80-89（微調即可）
- B: 70-79（需要修正）
- C: 60-69（大幅修改）
- D: <60（重做）

weighted_score 計算：
headline_impact*0.20 + safe_zone*0.15 + text_quality*0.15 + visual_realism*0.15 + composition*0.15 + brand_consistency*0.10 + no_artifacts*0.10，再乘以 10 得到 0-100 分。
"""

WEIGHTS = {
    "headline_impact": 0.20,
    "safe_zone": 0.15,
    "text_quality": 0.15,
    "visual_realism": 0.15,
    "composition": 0.15,
    "brand_consistency": 0.10,
    "no_artifacts": 0.10,
}


def evaluate_card(image_path: Path, scene_context: str = "") -> dict | None:
    """Evaluate a single card image, return structured score dict."""
    img_bytes = image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()

    # Detect mime type
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    prompt = RUBRIC
    if scene_context:
        prompt += f"\n\n## 此圖卡的劇本資訊（供比對用）\n\n{scene_context}"

    parts = [
        {"inlineData": {"mimeType": mime, "data": img_b64}},
        {"text": prompt},
    ]

    result = call_gemini_text(parts)
    if not result:
        return None

    # Validate and recalculate weighted score
    scores = result.get("scores", {})
    ws = sum(scores.get(k, 0) * w for k, w in WEIGHTS.items()) * 10
    result["weighted_score"] = round(ws, 1)

    # Assign grade
    if ws >= 90:
        result["grade"] = "S"
    elif ws >= 80:
        result["grade"] = "A"
    elif ws >= 70:
        result["grade"] = "B"
    elif ws >= 60:
        result["grade"] = "C"
    else:
        result["grade"] = "D"

    return result


def get_scene_context(episode_path: Path, scene_id: str) -> str:
    """Extract scene info from episode JSON for evaluation context."""
    ep = json.loads(episode_path.read_text(encoding="utf-8"))
    for scene in ep.get("scenes", []):
        if scene.get("scene_id") == scene_id:
            return json.dumps(scene, ensure_ascii=False, indent=2)
    return ""


def print_report(image_name: str, result: dict):
    """Print a human-readable evaluation report."""
    scores = result.get("scores", {})
    remarks = result.get("remarks", {})

    print(f"\n{'='*60}")
    print(f"  {image_name}  —  Grade: {result['grade']}  ({result['weighted_score']}/100)")
    print(f"{'='*60}")

    dim_labels = {
        "headline_impact": "標題衝擊力",
        "safe_zone": "安全區合規",
        "text_quality": "文字品質  ",
        "visual_realism": "視覺真實感",
        "composition": "構圖層次  ",
        "brand_consistency": "品牌一致性",
        "no_artifacts": "無多餘元素",
    }

    for key, label in dim_labels.items():
        score = scores.get(key, 0)
        bar = "#" * score + "-" * (10 - score)
        weight_pct = int(WEIGHTS[key] * 100)
        remark = remarks.get(key, "")
        print(f"  {label} [{bar}] {score}/10 ({weight_pct}%)  {remark}")

    print(f"\n  最需改善: {result.get('top_issue', '-')}")
    print(f"  Prompt 建議: {result.get('prompt_suggestion', '-')}")
    print()


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Card visual evaluator")
    parser.add_argument("path", help="Image path or directory (with --all)")
    parser.add_argument("--all", action="store_true", help="Evaluate all card*.png in directory")
    parser.add_argument("--scene-json", help="Episode JSON for scene context")
    parser.add_argument("--scene-id", help="Scene ID (e.g. 01)")
    parser.add_argument("--output", help="Save JSON results to file")
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        log("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    target = Path(args.path)
    results = {}

    if args.all:
        if not target.is_dir():
            log(f"ERROR: {target} is not a directory")
            sys.exit(1)
        cards = sorted(target.glob("card*.png"))
        if not cards:
            log(f"No card*.png found in {target}")
            sys.exit(1)

        for card_path in cards:
            scene_id = card_path.stem.replace("card", "")
            scene_ctx = ""
            if args.scene_json:
                scene_ctx = get_scene_context(Path(args.scene_json), scene_id)

            log(f"Evaluating {card_path.name}...")
            result = evaluate_card(card_path, scene_ctx)
            if result:
                results[card_path.name] = result
                print_report(card_path.name, result)
            else:
                log(f"  FAILED to evaluate {card_path.name}")

        # Summary
        if results:
            avg = sum(r["weighted_score"] for r in results.values()) / len(results)
            print(f"\n{'='*60}")
            print(f"  Overall Average: {avg:.1f}/100")
            grades = [r["grade"] for r in results.values()]
            print(f"  Grades: {' | '.join(f'{k}: {v}' for k, v in zip(sorted(results.keys()), grades))}")
            print(f"{'='*60}\n")

    else:
        if not target.is_file():
            log(f"ERROR: {target} not found")
            sys.exit(1)

        scene_ctx = ""
        if args.scene_json and args.scene_id:
            scene_ctx = get_scene_context(Path(args.scene_json), args.scene_id)

        log(f"Evaluating {target.name}...")
        result = evaluate_card(target, scene_ctx)
        if result:
            results[target.name] = result
            print_report(target.name, result)
        else:
            log("FAILED to evaluate")
            sys.exit(1)

    # Save JSON
    if args.output and results:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
