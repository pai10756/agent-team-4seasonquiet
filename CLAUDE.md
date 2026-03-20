# Agent Team｜時時靜好 (4seasonquiet)

OpenClaw 多 Agent 團隊，自動化生產「時時靜好」YouTube Shorts 頻道內容。

## 關聯專案

| 專案 | 角色 | 路徑 |
|------|------|------|
| **night-thinking** | 研究素材庫（50 主題、爆量研究、格式目錄） | `../night-thinking/` |
| **elder_kitchen** | 「長輩廚房」系列生產（劇本 JSON、腳本、角色資產） | `../elder_kitchen/` |
| **health-digest-factory** | 通用組裝管線（Seedance workflow、assemble 腳本） | `../health-digest-factory/` |

## 核心架構

radix（主 Agent / Coordinator）調度 5 個 worker agents，透過 OpenClaw 的 agentToAgent 機制協作。

詳見：
- `docs/architecture.md` — 完整架構設計
- `docs/agent_specs.md` — 各 Agent 規格與三層規範
- `docs/seedance_api_options.md` — Seedance API 自動化方案
- `docs/vibe_advertising_insights.md` — Jacob @jacobgrowth 的 AI UGC 管線啟發
- `configs/` — OpenClaw 配置範本

## Agent 交接契約（Source of Truth）

`schemas/` 目錄下的 JSON Schema 是所有 agent 之間交接格式的唯一標準：

| Schema | 產出者 → 消費者 |
|--------|----------------|
| `schemas/episode.schema.json` | scriptwriter → reviewer, asset_gen, assembler |
| `schemas/review_result.schema.json` | reviewer → scriptwriter, radix |
| `schemas/research_report.schema.json` | researcher → scriptwriter |

文件描述和 schema 衝突時，以 schema 為準。

## 審查收斂機制

reviewer 迴圈最多 3 輪，詳見 `configs/workflow_produce_episode.yaml`：
- 第 1-2 輪：auto_fixable violations → scriptwriter 自動修正
- 第 3 輪：仍有 auto_fixable 未修 → 終止；全部 needs_human → pass_with_notes，通知人工
- Seedance API 不可用時自動降級為 quick_cut 模式（Gemini 靜態圖 + ffmpeg 字幕疊加）

## 吉祥物系統（小靜）

台灣石虎吉祥物「小靜」，Duolingo 風格角色驅動插畫，用於片頭、片尾、縮圖、知識卡。

### 核心檔案

| 檔案 | 用途 |
|------|------|
| `characters/mascot/character.json` | 角色規格 source of truth（locked_identity + 可變 outfit/expression/prop） |
| `characters/mascot/prompt_templates.md` | Gemini prompt 模板（縮圖、片頭、片尾、知識卡） |
| `characters/mascot/Duolingo_Real_leopard_cat_v2.jpg` | style reference（每次生成必須附上） |
| `docs/mascot_design_plan.md` | 設計決策紀錄與標竿案例 |

### 設計原則

- **locked_identity 永遠不改**：頭身比、斑點（非條紋）、額頭白線、耳後白斑、眼睛大小、negative prompt
- **可變元素由 scriptwriter 在 episode JSON 的 `mascot` 欄位指定**：
  - `outfit`：9 種選項（apron/none/sport_vest/sleep_cap/scarf/doctor_coat + 3 節慶款），預設 apron
  - `expression`：12 種（base 6 + extended 6），從 character.json 查 prompt_fragment
  - `prop`：主題相關手持小道具（icon 級別），可選
- **CHARACTER_BLOCK + negative prompt 每次生成都必須包含**，防止 Gemini 漂移回虎斑貓
- 服裝不能遮蓋身體超過 30%，必須保留斑點和體色可見性
