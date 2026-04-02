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

## 兩條管線（v3.1）

radix 收到指令後，前三步（研究→劇本→審查）共用，asset_gen + assembler 依管線分流。

### 共用流程：研究 → 劇本 → 審查

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
      └─ 依管線類型產出對應 prompt（圖卡 prompt 或 Seedance prompt）
  → reviewer（v3 三層審查）：
      ├─ 鎖死層：schema + 語言 + 醫療宣稱 + 品牌
      ├─ 視覺品牌層：小靜一致性 + hero object + 標題主導
      └─ 護欄層：LLM 判斷 hook 力度 + 節奏
  → 🧑 人工確認審查結果 + 用詞審查
```

### 管線 A：靜態圖卡（EP13 實證版）

適用：數據密度高、排行榜、倒數揭曉、圖文快剪

```
  → asset_gen（Gemini 直出）：
      ├─ Gemini 單次生成完整卡片（gemini-3.1-flash-image-preview）
      ├─ 小靜卡（card_01/06）注入 3d_reference_clean.jpg 作為 exact reference
      ├─ 所有 prompt 標注底部 20% 禁放文字
      ├─ Pillow 移除 SynthID 浮水印（像素 clone）
      └─ 🧑 逐張人工品質確認，不合格重新生成
  → assembler（TTS 驅動時長）：
      ├─ ElevenLabs TTS:
      │     model=eleven_v3, voice=yC4SQtHeGxfvfsrKVdz9
      │     speed=1.2, stability=0.35, similarity_boost=0.85
      │     style=0.15, speaker_boost=true
      ├─ ffmpeg probe 各段 TTS 實際時長
      ├─ 卡片時長 = max(原始節奏, TTS + 0.3s)
      ├─ 卡片影片化：靜態圖→mp4，僅 fade in/out（禁止動畫/zoompan）
      ├─ TTS 音訊 normalize → pad → concat（禁用 amix，會降音量）
      ├─ 合併：-map 0:v:0 -map 1:a:0，單一音軌，AAC 128k
      ├─ 字幕：ASS 白字黑框（FontSize 68, 描邊寬 5, MarginV 280）
      │     時間根據 TTS probe 動態對齊（不用固定時間）
      ├─ 輸出：1080×1920, 30fps, H.264 CRF 18, AAC 128k
      └─ 🧑 成品審片
  → radix 記憶更新
```

### 管線 B：Seedance 影片（EP09 成熟版）

適用：需要人物情緒/動作、敘事型、混合型

```
  → 角色設計：
      ├─ 年輕女性（20-26）：農民曆工廠 build_random_appearance() 隨機外觀
      └─ 中年/年長者：Agent 自行設計外觀描述
  → asset_gen（Gemini 素材生成）：
      ├─ character_turnaround.png — 角色定裝照（3:2 白底，多角度+多表情）
      ├─ face_reference.jpg — 臉部特寫備用
      ├─ mascot_turnaround.png — 每集必生成，以 3d_reference_clean.jpg 為 ref
      ├─ live_scene01~05.png — 人物場景圖（9:16，含人物，無小靜）
      ├─ live_scene06_mascot.jpg — 結尾場景（人物+小靜同框，互動僅限輕撫頭頂）
      └─ 🧑 逐張確認，不合格 regen
  → Seedance Prompt 撰寫（songguoxs 格式）：
      ├─ 2 Parts × 15-18 秒
      ├─ [00:00-00:05] 時間軸 + 場景參考 图片N + 對白直寫
      ├─ 動作逐句拆解（說"X"時——動作Y）
      ├─ 小靜固定在 Part2 最後一段蹦跳出場
      ├─ 尾部 Sound: / Music: / 禁止:
      └─ Seedance 自動配音（不用 TTS）
  → 🧑 即夢平台手動提交（每段 3-5 次，挑最佳 take）
  → assembler（Agent 自動）：
      ├─ ffmpeg concat Part1.mp4 + Part2.mp4
      └─ ASS 字幕燒入（白字黑描邊，畫面下半部中間）
  → radix 記憶更新
  （Seedance API 不可用時自動降級為管線 A）
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
- 參考圖：`characters/mascot/3d_reference_clean.jpg`
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

## Asset 生成管線

### 管線 A：Gemini 直出（靜態圖卡）

```
Gemini 單次直出完整卡片（含文字、排版、配色）
  → model: gemini-3.1-flash-image-preview
  → 小靜卡注入 3d_reference_clean.jpg
  → Pillow 移除 SynthID 浮水印
  → 🧑 逐張確認 → 不合格重新生成
```

### 管線 B：Seedance 素材生成

```
Step 1: 角色設計
  年輕女性 → 農民曆工廠 build_random_appearance()（日期 seed 隨機外觀）
  中年/年長者 → Agent 自行設計外觀描述

Step 2: Gemini 生成定裝照
  character_turnaround.png — 角色多角度+多表情（3:2 白底）
  face_reference.jpg — 臉部特寫備用

Step 3: 小靜定裝照（每集必生成）
  以 characters/mascot/3d_reference_clean.jpg 為 ref
  → mascot_turnaround.png — 當集服裝/多角度+多表情

Step 4: 場景參考圖
  Gemini 以 character_turnaround 為 ref 生成 live_scene01~05（9:16，含人物）
  Gemini 以 character_turnaround + mascot_turnaround 為 ref 生成 live_scene06_mascot
  → 結尾場景互動僅限輕撫頭頂（禁止比愛心等複雜手勢，Seedance 會變形）

Step 5: Seedance Prompt 撰寫
  格式基底：songguoxs/seedance-prompt-skill 客製化版
  → 全中文、2 Parts × 15-18 秒、[00:00-00:05] 時間軸
  → 對白直寫進 prompt（Seedance 內建配音，不用 TTS）
  → 動作逐句拆解微表情/手勢
  → 小靜固定 Part2 最後一段蹦跳出場
  → 尾部 Sound: / Music: / 禁止: 區塊
```

## 工具分工

| 工具 | 管線 A（靜態圖卡） | 管線 B（Seedance） |
|------|-------------------|-------------------|
| **Gemini** | 直出完整卡片（gemini-3.1-flash-image-preview） | 定裝照 + 場景參考圖 + 小靜 turnaround |
| **Seedance** | — | 影片生成（含內建配音） |
| **ElevenLabs** | TTS（eleven_v3, voice yC4SQtHeGxfvfsrKVdz9, speed 1.2） | — |
| **Pillow** | 僅 SynthID 浮水印移除 | — |
| **ffmpeg** | 組裝 + TTS 驅動時長 + ASS 字幕 | concat Part1+Part2 + ASS 字幕（白字黑描邊） |

## 自我改進迴圈

```
YouTube Studio（手動或 API）
  → 每集上傳 7 天後回收數據（完播率、點擊率、分享數）
  → 回饋給 radix 的 Markdown 記憶系統
  → 下一集 scriptwriter 自動參考績效記憶
  → hook 越來越準
```
