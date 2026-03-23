# Agent 規格與三層規範（v3）

## Agent 團隊總覽

| Agent | 模型 | 職責 | 載入的 Skill/知識 |
|-------|------|------|-------------------|
| **radix** (Coordinator) | claude-sonnet-4-5 | 接單、拆解、調度、回報 | 生產管線流程 |
| **researcher** | claude-sonnet-4-5 | 選題、查證數據、提供視覺物件建議 | web-search, web-fetch |
| **scriptwriter** | claude-opus-4-6 | 產出 v3 episode JSON（含視覺導演稿） | seedance skill + episode schema v3 |
| **asset_gen** | claude-sonnet-4-5 | 4 階段素材生成（layout→bg→mascot→compose） | shell + brand_visual_tokens |
| **assembler** | claude-sonnet-4-5 | 呼叫 assemble_episode.py 組裝影片 | shell |
| **reviewer** | claude-opus-4-6 | 三層審查（鎖死+視覺品牌+護欄） | review_result schema v3 |

## 三層規範設計原則

**鎖死 WHAT，放開 HOW。**

```
鎖死（不可違反）        ← 規格、品牌、事實、視覺一致性
  │
  ├─ 視覺品牌（v3 新增）  ← 小靜一致性、hero object、標題主導
  │
  ├─ 有彈性的護欄        ← 風格偏好、歷史經驗
  │
  └─ 完全自由            ← 創意表達、角度選擇
```

---

## 契約 Schema（Source of Truth）

所有 agent 之間的交接格式以 `schemas/` 目錄下的 JSON Schema 為唯一標準：

| Schema | 產出者 | 消費者 | v3 變更 |
|--------|--------|--------|---------|
| `episode.schema.json` | scriptwriter | reviewer, asset_gen, assembler | 新增 core_claim, single_takeaway, mascot_strategy, scenes[], visual_style_token |
| `review_result.schema.json` | reviewer | scriptwriter, radix | 新增 visual_brand_layer + 20 個新 violation codes + visual_checklist |
| `research_report.schema.json` | researcher | scriptwriter | 新增 good_cover_objects, mascot_recommended_pose, visual_risk_notes 等視覺欄位 |

---

## Scriptwriter 三層規範

### 鎖死層（程式化檢查，violation 即 fail）

| 規則 | 原因 | Violation Code |
|------|------|----------------|
| JSON schema 必填欄位完整 | 下游會壞 | `SCHEMA_INCOMPLETE` |
| 字幕繁體中文 | 觀眾語言 | `SUBTITLE_NOT_ZHTW` |
| Seedance prompt 簡體中文 | 平台限制 | `PROMPT_NOT_ZHCN` |
| 每句 6-12 字（上限 15） | 字幕可讀性 | `SUBTITLE_TOO_LONG` / `SUBTITLE_TOO_SHORT` |
| 結尾含「時時靜好」+ 告別語 | 品牌辨識 | `MISSING_BRAND_CLOSING` |
| 營養數據附 USDA/衛福部來源 | 公信力 | `MISSING_DATA_SOURCE` |
| 不說「超級食物」、不做療效宣稱 | 法規合規 | `MEDICAL_CLAIM` |
| 總時長 ~33 秒 | 格式規格 | `DURATION_OUT_OF_RANGE` |
| hook_variants ≥ 3 個 | 測試需求 | `HOOK_VARIANTS_INSUFFICIENT` |
| type_rationale ≥ 10 字 | 決策可追溯 | `TYPE_RATIONALE_MISSING` |
| core_claim ≥ 10 字 | v3 必填 | `MISSING_CORE_CLAIM` |
| single_takeaway ≥ 5 字 | v3 必填 | `MISSING_SINGLE_TAKEAWAY` |

### 視覺品牌層（v3 新增，程式化 + LLM 複查）

| 規則 | Violation Code |
|------|----------------|
| 小靜最多出現 2 張卡（開場+結尾） | `MASCOT_OVERUSED` |
| 每張卡最多 1 隻小靜 | `DUPLICATE_3D_MASCOT` |
| 中間卡不出現小靜（預設） | `MASCOT_OVERUSED` |
| 開場表情與 hook 情緒匹配 | `EMOTION_MISMATCH_WITH_HEADLINE` |
| poster_cover 必須有 hero_object | `NO_CLEAR_HERO_OBJECT` |
| 非 closing 卡必須有 on_screen_text_main | `HEADLINE_NOT_DOMINANT` |
| mascot_strategy.presence 與 scenes 一致 | `MASCOT_NOT_SUPPORTING_MAIN_MESSAGE` |

視覺 checklist（Yes/No 快速審查，供 LLM 最終確認）：
- 這張圖是否只有一個主訊息？
- 視覺是否支援該主訊息？
- 觀眾 1 秒內能否讀到主標？
- 觀眾 3 秒內能否理解在講什麼？
- 是否只有一隻小靜？
- 小靜是否沒有被用作 badge/貼紙？
- 表情是否正確服務標題？
- 字是否夠大（高齡友善）？
- 畫面是否不過滿？

### 護欄層（LLM 判斷，偏離記錄但不阻擋）

```
- Hook 優先用「顛覆認知」框架
- 排行榜倒數揭曉比直接告知更有效
- 正面框架（「換這個吃更好」）優於恐嚇框架
- 數字反差越大越好（3倍以上才有感）
```

### 自由層（不限制）

- Hook 的具體切入角度和遣詞用字
- 情緒弧線和揭曉順序
- hero object 的具體選擇（從 researcher 建議中選）
- 場景卡數量（≥2 即可）

---

## Asset_gen 三層規範

### 鎖死層

| 規則 | 原因 |
|------|------|
| 9:16 豎屏，1080×1920（v3 升級） | 平台規格 |
| 底圖不含小靜（分開生成） | 防止重複小靜 |
| 小靜以 3d_reference.jpg 為 exact reference | 身份一致性 |
| 小靜透明背景 PNG，與底圖分離 | 合成需求 |
| 色盤遵循 brand_visual_tokens.json | 品牌一致性 |

### 護欄層

```
- hero object 佔畫面 50-70%
- 小靜佔畫面 20-30%（sidekick 角色）
- 標題字用 olive_dark #4E5538
- 背景偏暖色系（cream / morandi）
```

### 自由層

- 背景構圖細節
- 光線角度微調
- 小靜在畫面中的精確位置

---

## Reviewer 三層品質閘門

```
scriptwriter 自由產出
  → reviewer 檢查鎖死層（不過就打回）
  → reviewer 檢查視覺品牌層（不過就打回）
  → reviewer 對照護欄層（標注偏離但不阻擋）
  → 自由層完全不管
  → 通過 → 進入 asset_gen
```

### 收斂機制（防止無限 loop）

```
第 1 輪審查 → fail
  → scriptwriter 根據 auto_fixable violations 自動修正
第 2 輪審查 → fail
  → 同上，再修一輪
第 3 輪審查 → 仍 fail
  → 檢查：剩餘 violations 是否全部 needs_human？
    ├─ 是 → pass_with_notes，通知人工，管線繼續
    └─ 否 → 終止工作流，回報錯誤給 radix
```

Reviewer 輸出格式見 `schemas/review_result.schema.json`，包含：
- **verdict**: pass / fail / pass_with_notes
- **lock_layer**: 鎖死層 violations
- **visual_brand_layer**: 視覺品牌層 violations + checklist
- **guardrail_layer**: 護欄層 notes
- **auto_fixable / needs_human**: 分類

---

## Hook 分層生成

每集產出 3-5 個 hook 變體，按認知層級分類：

| 認知層級 | 觀眾狀態 | Hook 特徵 |
|---------|----------|----------|
| unaware | 不知道自己有問題 | 製造問題意識 |
| problem_aware | 知道問題，不知道解法 | 提供方向 |
| solution_aware | 知道解法，選錯方法 | 破除迷思 |
| audience | 看過頻道，要更深入 | 進階知識 |

---

## 不需要鎖死的元素

| 元素 | 理由 |
|------|------|
| 角色年齡/性別/外貌 | 觀眾追的是「有用的知識」不是人臉 |
| 場景地點 | 不同主題適合不同場景 |
| 結尾台詞逐字措辭 | 只需保留「時時靜好」+ 告別語框架 |
| 影片型態 | 由 scriptwriter 根據數據密度和情緒判斷 |
| hero object 選擇 | researcher 建議，scriptwriter 最終決定 |
