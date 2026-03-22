# Agent Team｜時時靜好 (4seasonquiet)

OpenClaw 多 Agent 團隊，自動化生產「時時靜好」YouTube Shorts 頻道內容。

## 關聯專案

| 專案 | 角色 | 路徑 |
|------|------|------|
| **night-thinking** | 研究素材庫（50 主題、爆量研究、格式目錄） | `../night-thinking/` |
| **elder_kitchen** | 「長輩廚房」系列生產（劇本 JSON、腳本、角色資產） | `../elder_kitchen/` |
| **health-digest-factory** | 通用組裝管線（Seedance workflow、assemble 腳本） | `../health-digest-factory/` |

## 核心架構（v3）

radix（主 Agent / Coordinator）調度 5 個 worker agents，透過 OpenClaw 的 agentToAgent 機制協作。

詳見：
- `docs/architecture.md` — 完整架構設計（含 v3 四階段管線、卡片節奏模板）
- `docs/agent_specs.md` — 各 Agent 規格與三層規範（含視覺品牌層）
- `docs/seedance_api_options.md` — Seedance API 自動化方案
- `docs/vibe_advertising_insights.md` — Jacob @jacobgrowth 的 AI UGC 管線啟發
- `configs/` — OpenClaw 配置範本 + 品牌視覺系統

## Agent 交接契約（Source of Truth）

`schemas/` 目錄下的 JSON Schema 是所有 agent 之間交接格式的唯一標準：

| Schema | 產出者 → 消費者 | v3 重點變更 |
|--------|----------------|-------------|
| `schemas/episode.schema.json` | scriptwriter → reviewer, asset_gen, assembler | 新增 core_claim, single_takeaway, mascot_strategy, scenes[], visual_style_token |
| `schemas/review_result.schema.json` | reviewer → scriptwriter, radix | 新增 visual_brand_layer + 20 個視覺 violation codes + visual_checklist |
| `schemas/research_report.schema.json` | researcher → scriptwriter | 新增 good_cover_objects, mascot_recommended_pose, visual_risk_notes 等視覺欄位 |

文件描述和 schema 衝突時，以 schema 為準。

## 品牌視覺系統（v3）

Style Token: `STYLE_SHIZHI_3D_POSTER_V1`

| 配置檔 | 用途 |
|--------|------|
| `configs/brand_visual_tokens.json` | 色盤、排版、畫布、卡片類型定義 |
| `configs/mascot_3d_spec.json` | 3D 小靜 identity/material/lighting lock、pose family |
| `configs/negative_design_tokens.json` | 視覺設計禁忌清單 |
| `configs/cover_card_template_3d.json` | 開場卡固定版面 zone 座標 |
| `configs/closing_card_template_3d.json` | 結尾卡固定版面 zone 座標 |

- 畫布 1080x1920 (9:16)
- 色盤：cream #F6F1E7 / sage #A8B88A / olive dark #4E5538 / brown #3B2A1F
- 75% 寫實底圖 + 25% 3D 元素

## Asset 生成四階段管線（v3）

| 階段 | 功能 | 腳本 |
|------|------|------|
| Stage 1 | Layout Planner — 讀取 brand tokens 分配版面 | `scripts/generate_assets.py` |
| Stage 2 | Background + Hero Object — Gemini 生成底圖（無小靜） | `scripts/generate_assets.py` |
| Stage 3 | 3D Mascot — 透明背景 PNG（exact reference） | `scripts/generate_mascot.py` |
| Stage 4 | Composer — Pillow 合成底圖 + 小靜 + 文字疊加 | `scripts/generate_assets.py` |

## 審查三層機制（v3）

reviewer 迴圈最多 3 輪，詳見 `configs/workflow_produce_episode.yaml`：
- **鎖死層**：schema 完整性、語言、醫療宣稱、品牌結尾、core_claim、single_takeaway
- **視覺品牌層（v3 新增）**：小靜一致性（不重複、不濫用、表情匹配）、hero object 主導、標題可讀
- **護欄層**：LLM 判斷 hook 力度、節奏、框架（偏離記錄但不阻擋）
- 第 1-2 輪：auto_fixable violations → scriptwriter 自動修正
- 第 3 輪：仍有 auto_fixable 未修 → 終止；全部 needs_human → pass_with_notes，通知人工
- Seedance API 不可用時自動降級為 quick_cut 模式

## 卡片節奏模板（v3）

| # | scene_role | visual_type | 時間 | 時長 |
|---|-----------|------------|------|------|
| 01 | hook | poster_cover | 0-3s | 3s |
| 02 | flip | comparison_card | 3-8s | 5s |
| 03 | compare | comparison_card | 8-15s | 7s |
| 04 | evidence | evidence_card | 15-23s | 8s |
| 05 | reminder | safety_reminder | 23-29s | 6s |
| 06 | closing | brand_closing | 29-33s | 4s |

## 吉祥物系統（小靜 v3 — 3D）

台灣石虎吉祥物「小靜」，3D smooth matte plastic toy 風格（Pop Mart / Sonny Angel 品質），品牌主持人角色。

### 核心檔案

| 檔案 | 用途 |
|------|------|
| `characters/mascot/character.json` | 角色規格 source of truth（v3: xiaojing_3d_v1） |
| `characters/mascot/3d_reference.jpg` | 3D exact reference（每次生成必須附上） |
| `characters/mascot/3d_main_card_reference.jpg` | 封面卡範例參考 |
| `configs/mascot_3d_spec.json` | 3D 規格：identity/material/lighting lock、pose family |
| `docs/mascot_design_plan.md` | 設計決策紀錄與標竿案例 |

### 設計原則

- **3D identity lock 永遠不改**：頭身比、斑點（非條紋）、額頭白線、耳後白斑、磨砂塑膠材質、sage green apron
- **每次生成必須附 3d_reference.jpg 作為 exact reference**，防止 Gemini 漂移
- **小靜與底圖分開生成**（Stage 2 底圖無小靜 → Stage 3 透明背景小靜 → Stage 4 合成）
- **出場限制**：只在開場卡和結尾卡出現，每張圖最多一隻，禁止當 badge/貼紙/浮水印
- **可變元素由 scriptwriter 在 `mascot_strategy` 欄位指定**：
  - `presence`：both / opening_only / closing_only / none
  - `opening_expression`：8 種（default/surprised/thinking/happy/reminder/goodbye/worried/proud）
  - `opening_pose`：6 種（hug_object_side/lean_on_object/think_with_object/hold_badge/point_up/greet_viewer）
  - `outfit`：5 種（apron/none/sport_vest/sleep_cap/doctor_coat），預設 apron
  - `prop`：主題相關手持小道具（icon 級別），可選
  - `scale_vs_object`：small（配角）/ equal / large
