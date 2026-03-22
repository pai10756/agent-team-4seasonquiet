# Agent Team 架構設計（v3）

## 整體架構

```
你（LINE / Telegram）
  │
  ▼
radix（Coordinator / 主 Agent）
  ├── researcher      — 選題研究 + 視覺物件建議
  ├── scriptwriter    — 劇本 + 視覺導演稿
  ├── asset_gen       — 4 階段素材生成
  ├── assembler       — 影片組裝
  └── reviewer        — 三層品質審查
```

## 為什麼 radix 當 Coordinator

- radix 是既有的 OpenClaw 主 agent（`~/.openclaw/data-radix/`）
- 不需另創 coordinator，避免多一層調度延遲
- Worker agents 作為 radix 透過 `agentToAgent` 調度的子 agent

## v3 任務流

```
radix 收到指令（如「做一集雞蛋膽固醇」）
  → researcher：
      ├─ 查 USDA/PubMed 數據、找認知反差點
      ├─ 提供 good_cover_objects, comparison_objects
      ├─ 建議 mascot_recommended_pose
      └─ 標注 visual_risk_notes, unsafe_claims_to_avoid
  → scriptwriter（v3 視覺導演稿）：
      ├─ 產出 core_claim + single_takeaway
      ├─ 產出 3-5 個 hook 變體（分認知層級）
      ├─ 產出 scenes[]（scene_card with visual_type/scene_role）
      ├─ 產出 mascot_strategy（presence/expression/pose）
      └─ standard 型態含 Seedance prompt
  → reviewer（v3 三層審查）：
      ├─ 鎖死層：schema + 語言 + 醫療宣稱 + 品牌
      ├─ 視覺品牌層：小靜一致性 + hero object + 標題主導
      └─ 護欄層：LLM 判斷 hook 力度 + 節奏
  → asset_gen（v3 四階段）：
      ├─ Stage 1: plan_layout — 讀取 brand_visual_tokens 分配版面
      ├─ Stage 2: generate_hero_background — Gemini 生成底圖 + hero object（無小靜）
      ├─ Stage 3: generate_mascot — 3D 小靜透明背景 PNG（exact reference）
      └─ Stage 4: compose_card — Pillow 合成底圖 + 小靜 + 文字疊加
  → assembler（v3 卡片節奏）：
      ├─ scenes[] 模式：按固定節奏模板分配時長
      ├─ standard 模式：片頭 + Seedance + 片尾
      └─ 輸出最終 MP4 + ASS 字幕
  → radix 記憶更新：上傳後回收績效 → 存入記憶
```

## v3 卡片節奏模板（~33s Shorts）

| # | scene_role | visual_type | 時間 | 時長 |
|---|-----------|------------|------|------|
| 01 | hook | poster_cover | 0-3s | 3s |
| 02 | flip | comparison_card | 3-8s | 5s |
| 03 | compare | comparison_card | 8-15s | 7s |
| 04 | evidence | evidence_card | 15-23s | 8s |
| 05 | reminder | safety_reminder | 23-29s | 6s |
| 06 | closing | brand_closing | 29-33s | 4s |

## 品牌視覺系統（v3）

Style Token: `STYLE_SHIZHI_3D_POSTER_V1`

- 75% 寫實底圖 + 25% 3D 元素
- 色盤：cream #F6F1E7 / sage #A8B88A / olive dark #4E5538 / brown #3B2A1F
- 畫布 1080x1920 (9:16)
- 定義檔：`configs/brand_visual_tokens.json`

### 3D 吉祥物「小靜」

Smooth matte plastic toy 風格（Pop Mart / Sonny Angel 品質），每次生成必須附 reference image。

- 角色規格：`characters/mascot/character.json`
- 3D 規格：`configs/mascot_3d_spec.json`
- 參考圖：`characters/mascot/3d_reference.jpg`
- 只出現在開場卡和結尾卡，每張圖最多一隻
- 禁止當 badge/貼紙/浮水印使用

## 影片型態選擇（由 agent 判斷）

```
                    數據密度低                數據密度高
                ┌─────────────────┬─────────────────┐
  需要人物      │   Seedance      │   混合型          │
  情緒/動作     │   人物敘事       │   Seedance 開場   │
                │   一個轉折       │   + 圖卡中段      │
                │                 │   + 人物收尾      │
                ├─────────────────┼─────────────────┤
  不需要人物    │   圖文快剪       │   圖卡排行榜       │
                │   靜態圖+旁白    │   倒數揭曉        │
                └─────────────────┴─────────────────┘
```

## Asset 生成四階段管線

```
Stage 1: Layout Planner
  讀取 brand_visual_tokens.json + cover/closing card templates
  → 決定每張卡的 zone 配置

Stage 2: Background + Hero Object
  Gemini 生成底圖（寫實風格，無小靜）
  → hero object + background scene
  → 不同 visual_type 有不同 prompt 策略

Stage 3: 3D Mascot（透明背景）
  只對 mascot_presence=true 的場景生成
  → 必須附 3d_reference.jpg 作為 exact reference
  → 輸出透明背景 PNG

Stage 4: Composer
  Pillow 合成：底圖 + 小靜（去白底）+ 文字疊加
  → 按 brand_visual_tokens 的色盤和排版規則
  → 輸出 card_XX_composed.png
```

## 工具分工

| 工具 | 用途 | 備註 |
|------|------|------|
| **Gemini** | 底圖、hero object、3D 小靜 | 免費，所有圖片統一用 Gemini |
| **Seedance（即夢）** | 影片生成 | standard 型態使用 |
| **ElevenLabs** | TTS 語音 | 排行榜型使用 |
| **Pillow** | 圖卡合成、文字疊加 | v3 Stage 4 composer |
| **ffmpeg** | 影片組裝、字幕燒入 | assembler 使用 |

## 自我改進迴圈

```
YouTube Studio（手動或 API）
  → 每集上傳 7 天後回收數據（完播率、點擊率、分享數）
  → 回饋給 radix 的 Markdown 記憶系統
  → 下一集 scriptwriter 自動參考績效記憶
  → hook 越來越準
```
