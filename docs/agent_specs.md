# Agent 規格與三層規範

## Agent 團隊總覽

| Agent | 模型 | 職責 | 載入的 Skill/知識 |
|-------|------|------|-------------------|
| **radix** (Coordinator) | claude-sonnet-4-5 | 接單、拆解、調度、回報 | 生產管線流程 |
| **researcher** | claude-sonnet-4-5 | 選題、查證 USDA/PubMed 數據 | web-search, web-fetch |
| **scriptwriter** | claude-opus-4-6 | 產出 episode JSON + Seedance prompt | **seedance skill** + episode JSON schema |
| **asset_gen** | claude-sonnet-4-5 | 場景圖(Gemini) + TTS(ElevenLabs) + 圖卡(Pillow) | shell |
| **assembler** | claude-sonnet-4-5 | 呼叫 assemble_episode.py 組裝 | shell |
| **reviewer** | claude-opus-4-6 | Hook 力度、數據正確性、格式規範 | CLAUDE.md 注意陷阱清單 |

## 三層規範設計原則

**鎖死 WHAT，放開 HOW。**

```
鎖死（不可違反）        ← 規格、品牌、事實
  │
  ├─ 有彈性的護欄        ← 風格偏好、歷史經驗
  │
  └─ 完全自由            ← 創意表達、角度選擇
```

---

## 契約 Schema（Source of Truth）

所有 agent 之間的交接格式以 `schemas/` 目錄下的 JSON Schema 為唯一標準：

| Schema | 產出者 | 消費者 | 說明 |
|--------|--------|--------|------|
| `episode.schema.json` | scriptwriter | reviewer, asset_gen, assembler | 主契約：episode JSON 的完整欄位定義 |
| `review_result.schema.json` | reviewer | scriptwriter, radix | 結構化審查結果，含錯誤代碼和自動修正標記 |
| `research_report.schema.json` | researcher | scriptwriter | 研究報告格式，含認知反差點和數據可信度 |

Reviewer 的鎖死層檢查項目直接對應 `review_result.schema.json` 中定義的 violation codes。

---

## Scriptwriter 三層規範

### 鎖死層（寫進 system prompt，對應 review_result violation codes）

| 規則 | 原因 | Violation Code |
|------|------|----------------|
| JSON schema 必須完整（所有必填欄位） | 下游 asset_gen 和 assembler 會壞掉 | `SCHEMA_INCOMPLETE` |
| 字幕繁體中文，Seedance prompt 簡體中文 | 平台限制 | `SUBTITLE_NOT_ZHTW` / `PROMPT_NOT_ZHCN` |
| 每句 6-12 字 | 字幕可讀性 | `SUBTITLE_TOO_LONG` / `SUBTITLE_TOO_SHORT` |
| 結尾必須提到頻道名「時時靜好」+ 告別語 | 品牌辨識（允許措辭變體） | `MISSING_BRAND_CLOSING` |
| 營養數據必須附 USDA/衛福部來源 | 公信力 | `MISSING_DATA_SOURCE` |
| 不說「超級食物」、不做療效宣稱 | 法規合規 | `MEDICAL_CLAIM` |
| 總時長 ~33 秒（3+15+15） | 格式規格 | `DURATION_OUT_OF_RANGE` |

### 護欄層（寫進記憶，可被績效數據覆寫）

```
- Hook 優先用「顛覆認知」框架
- 排行榜倒數揭曉比直接告知更有效
- 正面框架（「換這個吃更好」）優於恐嚇框架
- 數字反差越大越好（3倍以上才有感）
- 台灣口音指定：「用台湾口音普通话说」
```

### 自由層（不限制）

- Hook 的具體切入角度
- 口播的遣詞用字、語氣節奏
- 場景敘事的情緒弧線
- 排行榜的揭曉順序鋪排
- hook_variants 的多樣性

---

## Asset_gen 三層規範

### 鎖死層

| 規則 | 原因 |
|------|------|
| 9:16 豎屏，720×1280 | 平台規格 |
| 場景圖不可有人臉 | Seedance 審查會擋 |
| 場景圖結尾加「不要任何文字、人物、水印、LOGO」 | 避免生成雜物 |
| 定裝照用 Gemini 生成，Seedance 只做影片 | 工具分工 |
| Seedance prompt 用時間戳分鏡法 | SKILL.md 規範 |

### 護欄層

```
- 食材特寫用微距+淺景深效果最好
- 廚房場景用略高俯角比平視更有食慾感
- Part1 開場鏡頭用推進（dolly in）製造臨場感
- 圖卡用暖橘色系 bar chart，深色背景
```

### 自由層

- 具體的鏡頭運動組合
- Seedance prompt 的鏡頭語言選擇
- 圖卡的排版創意
- 場景圖的構圖細節
- BGM 的節奏搭配建議

---

## 不需要鎖死的元素

以下元素在討論中確認**不需鎖死**，留給 agent 創意空間：

| 元素 | 理由 |
|------|------|
| 角色年齡/性別/外貌 | 觀眾追的是「有用的知識」不是「AI 阿姨的臉」 |
| 場景地點 | 不同主題適合不同場景（菜市場、廚房、餐桌） |
| 結尾台詞逐字措辭 | 只需保留「時時靜好」+ 告別語的框架 |
| 影片型態 | Seedance / 圖卡 / 混合型 / 圖文快剪由 agent 判斷 |

鎖死的是**視覺調性**（暖色溫、自然光、生活感）而不是具體場景。

---

## Reviewer 當品質閘門

與其把所有規則都塞給 scriptwriter/asset_gen，讓它們自由發揮，用 reviewer 守門：

```
scriptwriter 自由產出
  → reviewer 檢查鎖死層（不過就打回）
  → reviewer 對照護欄層（標注偏離但不一定打回）
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
- **violation codes**: 機器可讀錯誤代碼 + field_path + fix_hint
- **auto_fixable 標記**: scriptwriter 可自動修正 vs 需人工判斷

---

## Hook 分層生成

每集產出 3-5 個 hook 變體，按認知層級分類：

| 認知層級 | 觀眾狀態 | Hook 特徵 |
|---------|----------|----------|
| 完全不知道 | 不知道自己有問題 | 製造問題意識 |
| 知道問題 | 知道問題，不知道解法 | 提供方向 |
| 知道解法 | 知道解法，選錯方法 | 破除迷思 |
| 已是觀眾 | 看過頻道，要更深入 | 進階知識 |

存在 JSON 的 `hook_variants` 欄位，未來有績效數據後可自動選擇。
