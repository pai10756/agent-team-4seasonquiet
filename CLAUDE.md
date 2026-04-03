# Agent Team｜時時靜好 (4seasonquiet)

OpenClaw 多 Agent 團隊，自動化生產「時時靜好」YouTube Shorts 頻道內容。

## 關聯專案

| 專案 | 角色 | 路徑 |
|------|------|------|
| **night-thinking** | 研究素材庫（50 主題、爆量研究、格式目錄） | `../night-thinking/` |
| **elder_kitchen** | 「長輩廚房」系列生產（劇本 JSON、腳本、角色資產） | `../elder_kitchen/` |
| **health-digest-factory** | 通用組裝管線（Seedance workflow、assemble 腳本） | `../health-digest-factory/` |

## 核心架構（v3.1 — 雙管線）

radix（主 Agent / Coordinator）調度 5 個 worker agents，透過 OpenClaw 的 agentToAgent 機制協作。
前三步（研究→劇本→審查）共用，asset_gen + assembler 依管線分流：

| 管線 | 適用場景 | asset_gen | assembler |
|------|---------|-----------|-----------|
| **A 靜態圖卡** | 數據密度高、排行榜、圖文快剪 | Gemini 直出完整卡片 | TTS 驅動時長 + concat 音訊 |
| **B Seedance 影片** | 人物情緒/動作、敘事型 | Gemini 場景圖 + turnaround | Seedance 配音影片 + ffmpeg 字幕 |

Seedance API 不可用時自動降級為管線 A。

詳見：
- `docs/architecture.md` — 完整架構設計（含雙管線、卡片節奏模板）
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

## Asset 生成管線（v3.1）

### 管線 A：Gemini 直出（靜態圖卡）

| 步驟 | 說明 |
|------|------|
| Gemini 直出 | `gemini-3.1-flash-image-preview` 一次生成完整卡片（含文字排版） |
| 小靜注入 | card_01/06 附 `characters/mascot/3d_reference_clean.jpg` 壓縮至 ~20KB 作為 exact reference |
| 浮水印移除 | Pillow 像素 clone 移除 SynthID（Gemini 強制嵌入，無法 prompt 禁用） |
| Prompt 語言 | **英文撰寫打 API**（中文 prompt 易觸發 429 配額限制），但圖卡上文字指定繁體中文：`All text Traditional Chinese. No English on card. No phone UI.` |

#### 管線 A — 圖卡設計規範

| 規則 | 說明 |
|------|------|
| 圖卡一（hook） | **年輕女生 + 3D 小靜同框**。女生外觀每集隨機（`build_random_appearance()`）。小靜帶 `3d_reference_clean.jpg` 壓縮參考生成，佔畫面 ~15%，女生佔 ~40%。**小靜服裝根據主題自動切換**（`scripts/mascot_outfit.py`）：睡眠→睡帽、運動/肌力→運動背心、飲食→圍裙、醫學→白袍 |
| 背景 | **儘量使用真實攝影照片**當背景，填滿整張圖卡，搭配適度的圖表或插圖 |
| 長輩主題背景 | 目標受眾為長輩時，**使用真實長輩照片當背景**（如長輩園藝、散步、煮飯），比純物件圖更有共鳴 |
| 底部 20% | 安全區，**所有文字（含來源標註 source badge）都不放**（Shorts 標題遮擋），但可以有圖片/背景延伸，**不要刻意留白底色** |
| 文字可讀性 | 在照片背景上的文字加白色半透明陰影或深色底條，確保清晰可讀 |
| 攝影風格 | 用相機參數 prompt（Sony A7IV, 50mm f/1.8）效果好 |
| 來源標註 | 研究來源用**中文期刊名稱**（如「QJM 國際醫學期刊」而非 "QJM"、「英國運動醫學期刊」而非 "Br J Sports Med"） |
| 避免技術數值 | 圖卡上不放專業術語數值（如 MET 3.5-5.0），改用觀眾能懂的描述（如「中等強度」「跟快走差不多」） |
| 敏感詞 | 中國平台敏感詞避免（如「推翻」改用「不成立」「打破」） |
| 資訊卡 | 數據/建議類卡片直接在圖卡上排版文字（如三個建議用編號列出），不要只放裝飾照片 |

#### 管線 A — TTS 語音（assembler）

| 參數 | 值 |
|------|-----|
| API | ElevenLabs Text-to-Speech |
| Model | `eleven_v3` |
| Voice ID | `yC4SQtHeGxfvfsrKVdz9`（Little Ching / 小靜） |
| Speed | `1.2` |
| Stability | `0.35` |
| Similarity Boost | `0.85` |
| Style | `0.15` |
| Speaker Boost | `true` |
| 後製加速 | ffmpeg `atempo=1.1`（TTS 生成後再加速 10%） |
| 旁白原則 | 精簡，每 5 秒段落 20-25 字內，控制 Shorts 總長 ≤ 60 秒。避免專業術語數值（如 MET），用白話描述 |
| 多音字檢查 | 旁白完成後掃描破音字/多音字，用同音異體字替代（如「數杯數」→「算杯數」） |

#### 管線 A — 影片組裝（assembler）

| 步驟 | 說明 |
|------|------|
| Probe TTS 時長 | ffmpeg 測量每段 MP3 實際秒數 |
| 卡片影片化 | 靜態圖→mp4，時長 = `max(原始節奏, TTS+0.3s)`，**禁止任何動畫/zoompan/fade，直接切換** |
| TTS 音訊串接 | normalize 44100Hz/stereo → pad 到卡片時長 → **concat（禁用 amix，會降音量）** |
| 合併影音 | `-map 0:v:0 -map 1:a:0`，單一音軌，AAC 128k |
| 字幕燒入 | ASS 格式，時間根據 TTS probe 動態對齊，**FontSize 82**，白字 `&H00FFFFFF`，黑框寬 5，MarginV 280 |

輸出規格：1080×1920 (9:16), 30fps, H.264 CRF 18, AAC 128k 44100Hz stereo, 字幕燒入

#### 管線 A — Gemini API 注意事項

| 項目 | 說明 |
|------|------|
| 總請求大小 | **20 MB** 上限（含文字 prompt + inline 圖片 base64） |
| **Prompt 長度** | **精簡在 300 字（英文）以內**。Flash Image 適合精簡 prompt，長 prompt 消耗更多 TPM 容易觸發 429 |
| Prompt 語言 | **英文**打 API 較穩定（中文 prompt 消耗更多 tokens 且容易觸發 429） |
| reference image | 壓縮至 ~20KB（800×450, JPEG quality 80），每張 inline 圖片消耗 ~1,120 tokens |
| urllib timeout | **300 秒**（正常 20 秒，高負載可達 60-200 秒） |
| 請求間隔 | 至少 **12 秒**（免費版圖片生成有隱性配額） |
| Fallback 模型 | `gemini-3.1-flash-image-preview` 429 時自動切換 `gemini-3-pro-image-preview`（不同配額路徑） |
| 429 退避 | 切換 fallback 模型，或指數退避 20s → 40s → 60s |
| 503 高需求 | 等待 30s → 60s → 120s |

#### 管線 A — 全自動腳本模板

每集可建立獨立 `run_full.py`，包含劇本資料+圖卡 prompt+TTS+組裝，一次跑完：
```
python test_output/epXX_topic/run_full.py
```
參考 `test_output/ep58_nap_timing/run_full.py`。

**腳本必須在 `__main__` 開頭呼叫 `preflight_check.run_preflight()`**，自動檢查：
- Prompt 長度 ≤ 300 字（超過就擋）
- 旁白總長預估 ≤ 60 秒（中文 ~4字/秒 × atempo 1.1）
- 多音字掃描（常見多音字字典比對，標記風險）
- 敏感詞掃描（中國平台禁用詞清單）
- Prompt 標準語句（No English / Bottom 20% / Traditional Chinese）
- 事實查核閘門（`facts_checked=True` 才放行）

檢查模組：`scripts/preflight_check.py`

**生成後檢查（post-check）：**
- 底部 20% 模糊/遮罩偵測：比較底部與中間區域的邊緣細節量，底部過於平滑就警告
- 用法：`python scripts/preflight_check.py --postcheck test_output/epXX/`
- 圖卡生成後自動跑，有問題的卡片建議重生成（prompt 加 `NO blur NO gradient NO white bar at bottom`）

## 事實查核閘門（劇本→生產之間，必經）

```
研究 → 劇本 → 🔍 事實查核 → 圖卡 → TTS → 組裝
```

| 查核項 | 說明 |
|--------|------|
| **數據溯源** | 旁白中每個數字必須對應到具體研究來源 URL + 原文引述，**不得補腦推斷** |
| **交叉比對** | 用 web search 驗證關鍵宣稱（至少查 2 個獨立來源） |
| **不得概括** | AI 不能從摘要推斷原始研究沒有明確寫出的數據（如「約一半」需查實際百分比） |
| **來源層級** | 優先引用：原始論文 > 系統性回顧 > 官方指引 > 新聞報導 |
| **多音字掃描** | TTS 旁白完成後檢查破音字，用同音異體字替代 |
| **敏感詞掃描** | 檢查中國平台敏感詞（如「推翻」→「不成立」） |

### 管線 B：Seedance 影片（EP09 成熟版）

完整流程：角色設計 → 素材生成 → Prompt 撰寫 → 即夢手動提交 → 後製組裝。

#### 步驟 1：角色設計

| 角色類型 | 外觀來源 |
|---------|---------|
| 年輕女性（20-26） | 農民曆工廠 `almanac_factory/generate_daily_script.py` 的 `build_random_appearance()`，隨機組合臉型/眼型/眉型/鼻型/唇型/髮型/妝容/服裝 |
| 中年/年長者 | Agent 自行設計外觀描述 |

#### 步驟 2：素材生成（Gemini `gemini-3.1-flash-image-preview`）

**API 限速規則：**
- 每次圖片生成請求間隔 **至少 10 秒**（免費版有隱性圖片配額限制）
- 429 錯誤：指數退避 10s → 20s → 30s
- 503 高需求：等待 20s → 40s → 60s
- 帶 reference image 請求：壓縮至 ~20KB（800×450, JPEG quality 80）避免超時
- 不要批次一次送超過 10 張，分批跑

| 產出物 | 說明 |
|--------|------|
| `character_turnaround.png` | 角色定裝照（3:2 白底，多角度+多表情），Seedance 人物 identity lock，**唯一含人臉的素材** |
| `face_reference.jpg` | 臉部特寫備用，角色漂移嚴重時額外上傳，**含人臉** |
| `mascot_turnaround.png` | **每集必生成**，以 `3d_reference_clean.jpg` 為 ref（壓縮後上傳），含當集服裝/多角度+多表情 |
| `scene01~05.jpg` | 場景環境圖（9:16），**不含人臉、不含人物全身**，僅環境/物件/手部特寫，無小靜 |
| `live_scene06_mascot.jpg` | 結尾場景：**只有小靜**（以 3d_reference_clean 為 ref），無人物，小靜坐在場景物件上 |

#### 步驟 3：Seedance Prompt 撰寫（songguoxs 格式）

```
全域規格（風格/光影/場景氛圍）

图片N 的人物形象作为本片主角。
[图片N 的3D石虎吉祥物"小静"作为本片配角。]  ← 僅 Part2

[00:00-00:05] 场景参考 图片N 。動作描述。
  她用台湾口音普通话说："對白"
[00:05-00:10] ...

Sound：音效描述
Music：配樂描述
禁止：任何文字、字幕、LOGO或水印。
```

- 2 Parts × 15-18 秒，對白直接寫進 prompt（Seedance 自動配音，不用 TTS）
- 動作逐句拆解微表情/手勢（說"X"時——動作Y）
- 場景參考圖為無人臉環境圖，Seedance 根據 turnaround 自動合成人物
- 小靜固定在 Part2 最後一段蹦跳出場 + 品牌收尾

#### 步驟 4：即夢平台手動提交

Part1 上傳：`character_turnaround` + 場景環境圖（無人臉）
Part2 上傳：`character_turnaround` + `mascot_turnaround` + 場景環境圖（無人臉）+ `live_scene06_mascot.jpg`（小靜構圖參考）
每段生成 3-5 次，手動挑最佳 take。

#### 步驟 5：後製組裝（Agent 自動）

| 步驟 | 工具 | 說明 |
|------|------|------|
| 合併 | ffmpeg | Part1.mp4 + Part2.mp4 concat |
| 字幕 | ffmpeg + ASS | 與旁白一致、字體略大、白色字黑色描邊、畫面下半部中間 |

不用 TTS，Seedance 內建配音。`scripts/assemble_episode.py` 處理。

## 審查四層機制（v3.1）

reviewer 迴圈最多 3 輪，詳見 `configs/workflow_produce_episode.yaml`：
- **鎖死層**：schema 完整性、語言、醫療宣稱、品牌結尾、core_claim、single_takeaway
- **事實查核層（v3.1 新增）**：旁白每個數據必須溯源到具體研究 URL，不得補腦推斷，交叉比對至少 2 個獨立來源
- **視覺品牌層**：小靜一致性（不重複、不濫用、表情匹配）、hero object 主導、標題可讀、底部 20% 無任何文字
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
| `characters/mascot/3d_reference_clean.jpg` | 3D exact reference（每次生成必須附上） |
| `characters/mascot/3d_main_card_reference.jpg` | 封面卡範例參考 |
| `configs/mascot_3d_spec.json` | 3D 規格：identity/material/lighting lock、pose family |
| `docs/mascot_design_plan.md` | 設計決策紀錄與標竿案例 |

### 設計原則

- **3D identity lock 永遠不改**：頭身比、斑點（非條紋）、額頭白線、耳後白斑、磨砂塑膠材質、sage green apron
- **每次生成必須附 3d_reference_clean.jpg 作為 exact reference**，防止 Gemini 漂移
- **管線 A**：小靜直接在 Gemini prompt 中注入 reference image 一次直出
- **管線 B**：每集必須以 `3d_reference_clean.jpg` 為 ref 生成小靜 turnaround 定裝照（多角度+多表情），上傳即夢作為 identity lock；結尾場景另外生成人物+小靜同框圖作為構圖參考
- **出場限制**：只在開場卡和結尾卡出現，每張圖最多一隻，禁止當 badge/貼紙/浮水印
- **可變元素由 scriptwriter 在 `mascot_strategy` 欄位指定**：
  - `presence`：both / opening_only / closing_only / none
  - `opening_expression`：8 種（default/surprised/thinking/happy/reminder/goodbye/worried/proud）
  - `opening_pose`：6 種（hug_object_side/lean_on_object/think_with_object/hold_badge/point_up/greet_viewer）
  - `outfit`：5 種（apron/none/sport_vest/sleep_cap/doctor_coat），預設 apron
  - `prop`：主題相關手持小道具（icon 級別），可選
  - `scale_vs_object`：small（配角）/ equal / large
