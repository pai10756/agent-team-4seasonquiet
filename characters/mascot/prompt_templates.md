# 小靜 Prompt 模板

asset_gen 根據 episode JSON 的 `mascot` 欄位，選用對應模板生成吉祥物圖片。

## 共用角色描述塊（每個 prompt 都必須包含）

```
CHARACTER_BLOCK = """
A cute Taiwanese leopard cat mascot named 小靜,
character-driven illustration style, very simple geometric construction,
big expressive and endearing eyes, unique rounded silhouette,
detached simple paws, warm yellow-brown fur, cream face and cheeks,
two iconic white vertical stripes on the forehead,
black ears with small white spots on the back,
simplified round dark spots on the body and tail instead of tabby stripes,
brick-pink nose, clever and friendly personality,
vector cartoon style, highly recognizable on mobile,
minimal but memorable, clean outlines,
{outfit_prompt_fragment}
premium but approachable,
species-accurate Taiwanese leopard cat markings simplified into a clean mascot language.
Not a domestic tabby cat, no tiger stripes, no m-shaped house-cat forehead marking,
no realistic fur, no complex texture, no busy background,
no ringed tabby tail, no decorative clutter.
"""

# outfit_prompt_fragment 變數：
# 從 character.json → outfit.options[mascot.outfit].prompt_fragment 或
#                    → outfit.seasonal[mascot.outfit].prompt_fragment 讀取
# 預設（apron）→ "wearing a simple cream apron with a small bowl icon on the front"
# none → "no clothing or accessories, just the natural leopard cat character"
# sport_vest → "wearing a simple light blue sport vest"
# sleep_cap → "wearing a small cozy beige nightcap with a tiny star on the tip"
# scarf → "wearing a simple warm orange-brown knit scarf"
# doctor_coat → "wearing a tiny simplified white doctor coat, icon-level simplicity"
# lunar_new_year → "wearing a red apron with a small tangerine icon, festive but simple"
# mid_autumn → "wearing a deep orange apron with a small mooncake icon"
# dragon_boat → "wearing a green apron with a small rice dumpling icon"
```

---

## 模板 1：縮圖吉祥物（Thumbnail Overlay）

用途：生成透明背景的小靜，疊加到縮圖上。

```
{CHARACTER_BLOCK}

Expression: {expression_prompt_fragment}
{%- if prop %}
Holding in one paw: {prop} (simplified icon-level, matching the vector style)
{%- endif %}

Full body standing pose, character occupies 90% of frame.
Pure white background (for transparent PNG extraction).
Mobile-readable at small sizes.
```

### 變數來源

```
expression_prompt_fragment = character.json → expressions[mascot.thumbnail.expression].prompt_fragment
prop = episode_json → mascot.prop（可選）
outfit_prompt_fragment = character.json → outfit.options[mascot.outfit].prompt_fragment 或 outfit.seasonal[mascot.outfit].prompt_fragment（預設 apron）
```

### 填入範例

| episode 主題 | expression | prop | 組合效果 |
|-------------|------------|------|---------|
| 白粥升糖 | `surprised` → "wide open eyes, small O-shaped mouth, startled surprised expression" | "tiny bowl of porridge" | 驚訝的小靜拿著一碗粥 |
| 補鈣排行 | `happy` → "crescent squinting eyes, joyful open smile" | "tiny glass of milk with X mark" | 開心的小靜拿著打叉的牛奶杯 |
| 雞蛋膽固醇 | `thinking` → "one paw touching chin, curious eyes looking up" | "tiny egg" | 思考的小靜旁邊一顆蛋 |
| 烹調方式 | `reminder` → "one paw raised with index finger pointing up" | "tiny frying pan" | 提醒的小靜拿著小鍋 |
| 端午特集 | `happy` → "crescent squinting eyes, joyful open smile" | "tiny rice dumpling" | 穿綠圍裙的小靜拿粽子 |

---

## 模板 2：片頭標題卡（Title Card with Mascot）

用途：3 秒片頭，吉祥物 + 頻道名 + 主題。

```
A YouTube Shorts title card, 9:16 vertical (720x1280).

Background: dark gradient with warm tone.
Center-top: large bold text "{title_line1}" in golden yellow with dark outline.
Below: "{title_line2}" in white bold with dark outline.
Small source badge at bottom-center: "{source_text}" in gray.

Bottom-right corner (20% of frame):
{CHARACTER_BLOCK}
Expression: {expression_description}

Clean editorial layout, warm color palette, cinematic feel.
```

---

## 模板 3：片尾落款（End Card）

用途：固定片尾，每集相同。

```
A YouTube Shorts end card, 9:16 vertical (720x1280).

Background: warm cream/beige gradient, soft and inviting.
Center: {CHARACTER_BLOCK}
Expression: right hand raised high waving, warm smile.
Size: 40% of frame.

Below character: "時時靜好" in warm brown handwritten-style font, large.
Below that: "我們下次見" in smaller gray text.

Clean, minimal, warm, brand-consistent.
No other elements, no food, no data.
```

---

## 模板 4：知識提醒卡（Knowledge Card with Mascot）

用途：ranking 型態的圖卡中插入小靜。

```
A health education info card, 9:16 vertical (720x1280).

Background: {bg_color} with subtle warm gradient.
Main content area (top 65%): {info_content}

Bottom-left (25% of frame):
{CHARACTER_BLOCK}
Expression: one hand holding small signboard, other hand pointing at it,
lightbulb symbol above head, friendly but serious expression.

The signboard text area is blank (text will be overlaid in post-production).

Clean vector style matching the mascot, editorial science-video feel.
```

---

## 生成流程

```
asset_gen 收到 episode_json
  │
  ├─ 1. 讀取 character.json
  │     ├─ prompt_base → CHARACTER_BLOCK
  │     ├─ negative_prompt → 附加到每個 prompt 尾端
  │     └─ reference_image → Duolingo_Real_leopard_cat_v2.jpg
  │
  ├─ 2. 解析 episode_json.mascot 欄位
  │     ├─ thumbnail.expression → 查 expressions[].prompt_fragment
  │     ├─ prop → 如有指定，加入 "Holding in one paw: {prop}"
  │     ├─ outfit_variant → 查 outfit.seasonal_variants，決定 apron_color
  │     └─ end_card.expression → 固定 "goodbye"
  │
  ├─ 3. 組合 prompt
  │     ├─ CHARACTER_BLOCK（apron_color 已替換）
  │     ├─ + expression prompt_fragment
  │     ├─ + prop（如有）
  │     ├─ + negative_prompt
  │     └─ + 場景模板（縮圖 / 片頭 / 片尾 / 知識卡）
  │
  ├─ 4. 呼叫 Gemini API（附 reference image）
  │
  └─ 5. 輸出
        ├─ asset_paths.mascot_thumbnail → 透明背景 PNG
        ├─ asset_paths.mascot_endcard → 片尾落款圖
        └─ asset_paths.mascot_knowledge_card → 知識卡（如有 in_video）
```

## 什麼會變、什麼不變

```
永遠不變（鎖死）           每集可變（scriptwriter 決定）
─────────────────────    ──────────────────────────
角色造型（頭身比、斑點）     表情（6 種中選）
額頭白線、耳後白斑           手持道具（主題食材 icon）
眼睛大小、鼻子顏色           圍裙顏色（節慶限定款）
圍裙形狀和剪裁              出現位置（左下/右下）
vector 風格、線條粗細         影片中出現時機
negative prompt             縮圖構圖
```

## 一致性保障

1. **CHARACTER_BLOCK 永遠不改** — 這是角色的 DNA，每次生成都包含
2. **prompt_base 直接從 character.json 讀取** — 不手寫，防止人為偏離
3. **negative prompt 永遠帶上** — 防止 Gemini 漂移回虎斑貓
4. **reference image** — 每次生成都附上 `Duolingo_Real_leopard_cat_v2.jpg` 作為 style reference
5. **expression 用 prompt_fragment** — 不讓 agent 自由描述表情，只能從 6 個預定義中選
6. **生成後人工抽檢前 3 集** — 確認穩定後才全自動
