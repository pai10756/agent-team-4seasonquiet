"""
劇本生成腳本 — scriptwriter agent 使用。

v3: 輸出 episode.schema.json v3 格式，含 core_claim, single_takeaway,
    mascot_strategy, scenes[] (scene_card with visual_type/scene_role),
    visual_style_token 等新欄位。

讀取 research_report，呼叫 LLM 產出符合 episode.schema.json v3 的完整劇本 JSON。
支援 review 修正迴圈：傳入 review_result 時修正 auto_fixable violations
（包含 lock_layer 和 visual_brand_layer）。

用法:
  # 首次生成
  python scripts/write_episode.py research_report.json --output ep.json

  # 根據 review 修正
  python scripts/write_episode.py research_report.json --output ep.json \
    --episode ep.json --review review_result.json

環境變數:
  GEMINI_API_KEY — Gemini API key（scriptwriter 用 Gemini 生成劇本）
  SCRIPTWRITER_MODEL — 模型名（預設 gemini-2.5-flash）
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from validate_schema import validate_episode

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SCRIPTWRITER_MODEL = os.environ.get("SCRIPTWRITER_MODEL", "gemini-2.5-flash")

SCHEMA_PATH = BASE / "schemas" / "episode.schema.json"
CHARACTER_PATH = BASE / "characters" / "mascot" / "character.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def call_gemini(prompt: str, model: str = None, temperature: float = 0.7) -> str:
    """呼叫 Gemini API，回傳文字回應。"""
    model = model or SCRIPTWRITER_MODEL
    if not GEMINI_API_KEY:
        print("錯誤: 請設定 GEMINI_API_KEY 環境變數", file=sys.stderr)
        sys.exit(1)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
        }
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        print(f"Gemini API 錯誤 HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "text" in part:
            return part["text"]
    return ""


def extract_json(text: str) -> dict:
    """從 LLM 回應中提取 JSON。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].strip().startswith("```") else 0
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])
    return json.loads(text)


def build_first_draft_prompt(research: dict, schema: dict, character: dict) -> str:
    """構建首次生成劇本的 prompt（v3 episode schema）。"""
    expressions = list(character.get("expressions", {}).keys())
    expressions = [e for e in expressions if not e.startswith("_")]
    outfits = list((character.get("outfit", {}).get("options", {})).keys())

    # Load brand visual tokens for card_types and palette
    brand_tokens_path = BASE / "configs" / "brand_visual_tokens.json"
    brand_tokens = load_json(brand_tokens_path) if brand_tokens_path.exists() else {}
    card_types = list(brand_tokens.get("card_types", {}).keys())

    # Expression-headline mapping from character
    expr_map = character.get("expression_headline_map", {})
    expr_map_str = json.dumps(expr_map, ensure_ascii=False, indent=2)

    # Research visual fields
    good_cover_objects = research.get("good_cover_objects", [])
    mascot_rec_pose = research.get("mascot_recommended_pose", "hug_object_side")
    visual_risks = research.get("visual_risk_notes", [])

    return f"""你是「時時靜好」YouTube Shorts 頻道的劇本編劇兼視覺導演。
請根據以下研究報告，撰寫一集完整的 v3 劇本 JSON。

## 研究報告
{json.dumps(research, ensure_ascii=False, indent=2)}

## 品牌風格
Style Token: STYLE_SHIZHI_3D_POSTER_V1
- 75% 寫實底圖 + 25% 3D 元素（小靜吉祥物）
- 大標題海報風格，每張卡只有一個主訊息
- 色盤：cream #F6F1E7（背景）、sage #A8B88A（品牌條）、olive dark #4E5538（標題字）、brown #3B2A1F（副標字）
- 畫布 1080x1920 (9:16)

## 輸出要求（v3 episode.schema.json）

### 必填欄位
- series: 系列名稱（如「長輩廚房｜吃對了嗎？」）
- episode: 集數（整數）
- type: 影片型態（standard / ranking / hybrid / quick_cut）
- type_rationale: 選擇此型態的理由（≥10 字，包含數據密度、情緒轉折、成本考量的判斷）
- topic_title: 主題標題
- core_claim: 這支片真正要講的唯一核心（≥10 字）。例：「真正更該注意的是整體搭配中的飽和脂肪，不是只把雞蛋當成罪魁禍首。」
- single_takeaway: 觀眾離開前只要記住這一句（≥5 字）。例：「吃對搭配，比怕蛋更重要。」
- visual_style_token: 固定填 "STYLE_SHIZHI_3D_POSTER_V1"
- hook_text: 主 hook（繁體中文，6-10 字為佳）
- hook_variants: 3-5 個 hook 變體，每個含 level/text/rationale
  - level: unaware / problem_aware / solution_aware / audience
- research_sources: 研究來源（≥1 個，含 citation 和 key_finding）
- subtitles: 字幕列表（繁體中文，每句 6-12 字，最多 15 字）
  - 最後幾句必須包含品牌告別語（含「時時靜好」）
- sound: 環境音描述
- music: 配樂描述
- youtube_metadata: title（含「時時靜好」≤100 字）、description（含來源）、hashtags（≥5 個，含 #時時靜好）

### mascot_strategy（3D 吉祥物「小靜」使用策略）
小靜是 3D 光滑磨砂塑膠玩具風格的台灣石虎吉祥物，品牌主持人角色。
- presence: "both"（開場+結尾）/ "opening_only" / "closing_only" / "none"
- opening_expression: 從 {expressions} 中選，配合 hook 情緒
- opening_pose: 從 ["hug_object_side", "lean_on_object", "think_with_object", "hold_badge", "point_up"] 中選
- outfit: 從 {outfits} 中選（預設 "apron"）
- prop: 主題相關手持小道具（icon 級別），如 "tiny egg"，可不填
- render_mode: 固定 "3d_exact_reference"
- scale_vs_object: "small"（小靜是配角）/ "equal" / "large"
- allow_extra_mascot: false（禁止重複）
- allow_logo_mascot: false（不當 logo 用）

表情與標題情緒對應規則（reviewer 會檢查）：
{expr_map_str}

研究報告建議的封面姿勢: {mascot_rec_pose}
研究報告建議的封面物件: {json.dumps(good_cover_objects, ensure_ascii=False)}

### scenes[]（導演稿場景卡，≥2 張）
每張卡是一個 scene_card，這取代了舊版 scene_images[]。
每張卡必須有明確的敘事角色和視覺規格。

場景卡欄位：
- scene_id: 兩位數編號 "01", "02", ...
- scene_role: 敘事角色 — "hook" / "flip" / "compare" / "evidence" / "reminder" / "closing"
- scene_goal: 這張卡要讓觀眾產生什麼反應（一句話）
- visual_type: 視覺版型 — 從 {card_types} 中選
- on_screen_text_main: 主標題文字（繁體中文，會在合成階段疊加）
- on_screen_text_sub: 副標題文字（可選）
- hero_object: 主視覺物件（英文描述），如 "one large realistic white egg on wooden table"
- background_scene: 背景場景（英文描述），如 "warm kitchen interior, soft natural light"
- mascot_presence: true/false（只有開場卡和結尾卡允許 true）
- mascot_expression: 對應 mascot_strategy 的表情（有小靜時才填）
- mascot_pose: 對應 mascot_strategy 的姿勢（有小靜時才填）
- badge_text: 右上角 badge 文字（可選），如 "2025\\n研究更新"
- source_badge_text: 資料來源 badge（evidence 卡建議填寫）
- do_not_include: 禁止的視覺元素 array，如 ["正面人臉", "文字浮水印"]
- time_range: 在影片中的時間範圍，如 "0-3s"
- animation: 動畫效果 — "slow_push_in" / "slight_drift" / "simple_cut" / "slide_in" / "badge_fade_in" / "mascot_wave" / "none"

### 建議的 6 卡結構（~33 秒 Shorts）
| # | scene_role | visual_type | time | 說明 |
|---|-----------|------------|------|------|
| 01 | hook | poster_cover | 0-3s | 大標題 + hero object + 小靜 |
| 02 | flip | comparison_card | 3-8s | 認知反轉，顛覆常識 |
| 03 | compare | comparison_card | 8-15s | 數據比較 |
| 04 | evidence | evidence_card | 15-23s | 研究佐證 |
| 05 | reminder | safety_reminder | 23-29s | 安全提醒 |
| 06 | closing | brand_closing | 29-33s | 小靜告別 + 品牌 |

你可以增減或調整卡片，但開場和結尾卡是必要的。

### 影片型態判斷
- 比較 ≥3 個東西 → ranking 或 hybrid
- 有情緒轉折 → standard
- 純數據無人物 → ranking 或 quick_cut
- standard 用 Seedance（有成本），ranking/quick_cut 用圖卡（免費）

### standard/hybrid 型態額外要求
- character: 角色描述（string）
- seedance_prompts: seedance_part1 / seedance_part2（簡體中文 prompt，<2000 字）

### ranking/hybrid 型態額外要求
- ranking_data: 排行榜數據（≥3 項，含 rank, food, value, unit, comparison）
- comparison_note: 比較基準說明

### 三層規範
- 鎖死：不說「超級食物」、不做療效宣稱、字幕繁體中文、每張卡只有一個主訊息
- 護欄：hook 優先用「顛覆認知」框架、數字反差 ≥3 倍、正面框架優於恐嚇
- 自由：切入角度、遣詞用字、情緒弧線、揭曉順序由你決定

### 視覺設計禁忌
- 小靜只出現在開場和結尾卡（中間卡禁止）
- 每張圖最多一隻小靜
- 不要把小靜當 badge/貼紙/浮水印
- hero object 必須是畫面主角（小靜是配角）
- 字要夠大（中高齡友善）
- 避免畫面過滿
- **禁止在食物上打叉(X)、劃線、紅圈禁止符號等否定視覺標記**。觀眾會誤解為「這個不能吃」，與正面框架矛盾。如需表達比較，請用並排對比、數據差異、箭頭指向等正面方式
- hero_object 描述中不可包含 "X", "cross", "slash", "ban", "prohibited", "red mark" 等否定標記詞
{f"- 視覺風險：{json.dumps(visual_risks, ensure_ascii=False)}" if visual_risks else ""}

### JSON 結構範例（最小骨架）
```json
{{
  "series": "長輩廚房｜吃對了嗎？",
  "episode": 10,
  "type": "ranking",
  "type_rationale": "本主題有多種早餐搭配的飽和脂肪數據比較...",
  "topic_title": "雞蛋與膽固醇：被冤枉的好食物",
  "core_claim": "真正更該注意的是整體搭配中的飽和脂肪...",
  "single_takeaway": "吃對搭配，比怕蛋更重要。",
  "visual_style_token": "STYLE_SHIZHI_3D_POSTER_V1",
  "hook_text": "一天只能吃一顆蛋？",
  "hook_variants": [
    {{"level": "unaware", "text": "雞蛋吃太多會怎樣？", "rationale": "..."}},
    {{"level": "problem_aware", "text": "蛋黃膽固醇很高？", "rationale": "..."}},
    {{"level": "solution_aware", "text": "一天到底能吃幾顆蛋？", "rationale": "..."}}
  ],
  "research_sources": [
    {{"citation": "Zhong et al., JAMA, 2019", "key_finding": "..."}}
  ],
  "mascot_strategy": {{
    "presence": "both",
    "opening_expression": "thinking",
    "opening_pose": "hug_object_side",
    "outfit": "apron",
    "prop": "tiny egg",
    "render_mode": "3d_exact_reference",
    "scale_vs_object": "small",
    "allow_extra_mascot": false,
    "allow_logo_mascot": false
  }},
  "scenes": [
    {{
      "scene_id": "01",
      "scene_role": "hook",
      "scene_goal": "觀眾好奇：真的只能吃一顆嗎？",
      "visual_type": "poster_cover",
      "on_screen_text_main": "一天只能吃一顆蛋？",
      "hero_object": "one large realistic white egg on warm wooden table",
      "background_scene": "warm kitchen interior, soft natural light from window",
      "mascot_presence": true,
      "mascot_expression": "thinking",
      "mascot_pose": "hug_object_side",
      "do_not_include": ["正面人臉", "多顆蛋"],
      "time_range": "0-3s",
      "animation": "slow_push_in"
    }},
    {{
      "scene_id": "06",
      "scene_role": "closing",
      "scene_goal": "品牌印象，溫暖告別",
      "visual_type": "brand_closing",
      "on_screen_text_main": "時時靜好",
      "on_screen_text_sub": "我們下次見",
      "hero_object": "",
      "background_scene": "clean warm gradient background",
      "mascot_presence": true,
      "mascot_expression": "goodbye",
      "mascot_pose": "greet_viewer",
      "time_range": "29-33s",
      "animation": "mascot_wave"
    }}
  ],
  "subtitles": [
    {{"text": "繁體中文字幕", "start": 0.0, "end": 2.5}},
    {{"text": "每句6-12字", "start": 2.5, "end": 5.0}},
    {{"text": "時時靜好祝您健康", "start": 30.0, "end": 33.0}}
  ],
  "ranking_data": [
    {{"rank": 1, "food": "食材名", "value": 85, "unit": "mg", "comparison": "..."}},
    {{"rank": 2, "food": "食材名", "value": 73, "unit": "mg", "comparison": "..."}},
    {{"rank": 3, "food": "食材名", "value": 46, "unit": "mg", "comparison": "..."}}
  ],
  "comparison_note": "數值來源: ...",
  "sound": "廚房環境音，雞蛋輕敲碗沿聲",
  "music": "輕快溫暖烏克麗麗",
  "youtube_metadata": {{
    "title": "一天只能吃一顆蛋？醫生沒告訴你的真相｜時時靜好",
    "description": "描述含來源...",
    "hashtags": ["#時時靜好", "#雞蛋", "#膽固醇", "#健康飲食", "#Shorts"]
  }}
}}
```

嚴格按照以上結構輸出。特別注意：
- hook_variants 是 array of objects（不是 dict）
- subtitles 是 array of objects with text/start/end（不是 string array）
- scenes 是 array of scene_card objects（不是舊版 scene_images）
- scene_id 是兩位數字串 "01" "02"（不是整數）
- mascot_strategy 是 object（不是舊版 mascot）
- visual_style_token 固定為 "STYLE_SHIZHI_3D_POSTER_V1"
- core_claim 和 single_takeaway 是必填 string

只輸出 JSON，不要其他文字。"""


def build_revision_prompt(episode: dict, review: dict, research: dict) -> str:
    """構建修正劇本的 prompt（v3: 含 lock_layer + visual_brand_layer violations）。"""
    # Collect auto_fixable violations from both layers
    lock_violations = review.get("lock_layer", {}).get("violations", [])
    visual_violations = review.get("visual_brand_layer", {}).get("violations", [])
    all_violations = lock_violations + visual_violations
    auto_fixable = [v for v in all_violations if v.get("auto_fixable")]

    # Include guardrail notes as suggestions (not mandatory)
    guardrail_notes = review.get("guardrail_layer", {}).get("notes", [])

    return f"""你是「時時靜好」YouTube Shorts 頻道的劇本編劇兼視覺導演。
以下是你之前產出的劇本，reviewer 審查後發現 {len(auto_fixable)} 個需修正的問題。

## 審查結果（第 {review.get('attempt', 1)} 輪）

### 必須修正的 violations（auto_fixable）
{json.dumps(auto_fixable, ensure_ascii=False, indent=2)}

{f"### 護欄建議（不阻擋但建議改善）{chr(10)}{json.dumps(guardrail_notes, ensure_ascii=False, indent=2)}" if guardrail_notes else ""}

## 原始劇本
{json.dumps(episode, ensure_ascii=False, indent=2)}

## 研究報告（供參考）
{json.dumps(research, ensure_ascii=False, indent=2)}

## 修正要求
- 只修正上面列出的 auto_fixable 問題
- 每個 violation 都有 fix_hint，照做即可
- 不要改動沒有問題的部分
- 護欄建議如果容易順手改就一起改，但不是必須
- 輸出完整的修正後 JSON（不是 diff）
- 確保 mascot_strategy, scenes[], core_claim, single_takeaway 等 v3 欄位都保留

只輸出 JSON，不要其他文字。"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成 episode JSON")
    parser.add_argument("research", help="research_report JSON 檔案路徑")
    parser.add_argument("--output", "-o", required=True, help="輸出 episode JSON 路徑")
    parser.add_argument("--episode", help="現有 episode JSON（修正模式）")
    parser.add_argument("--review", help="review_result JSON（修正模式）")
    args = parser.parse_args()

    research_path = Path(args.research)
    if not research_path.is_absolute():
        research_path = Path.cwd() / research_path
    research = load_json(research_path)

    schema = load_json(SCHEMA_PATH)
    character = load_json(CHARACTER_PATH) if CHARACTER_PATH.exists() else {}

    is_revision = args.episode and args.review
    if is_revision:
        episode = load_json(Path(args.episode))
        review = load_json(Path(args.review))
        prompt = build_revision_prompt(episode, review, research)
        print(f"[scriptwriter] 修正模式（第 {review.get('attempt', 1)} 輪）", file=sys.stderr)
    else:
        prompt = build_first_draft_prompt(research, schema, character)
        print("[scriptwriter] 首次生成模式", file=sys.stderr)

    print(f"[scriptwriter] 呼叫 {SCRIPTWRITER_MODEL}...", file=sys.stderr)
    response = call_gemini(prompt)

    try:
        episode = extract_json(response)
    except json.JSONDecodeError as e:
        print(f"[scriptwriter] JSON 解析失敗: {e}", file=sys.stderr)
        print(f"[scriptwriter] 原始回應前 500 字:\n{response[:500]}", file=sys.stderr)
        sys.exit(1)

    # 驗證
    errors = validate_episode(episode)
    if errors:
        print(f"[scriptwriter] 警告: 產出有 {len(errors)} 個 schema 錯誤（將由 reviewer 處理）", file=sys.stderr)
        for e in errors[:5]:
            print(f"  {e}", file=sys.stderr)

    # 輸出
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scriptwriter] 已存: {output_path}", file=sys.stderr)

    # 也輸出到 stdout
    sys.stdout.buffer.write(json.dumps(episode, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
