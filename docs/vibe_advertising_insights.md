# Vibe Advertising 啟發筆記

來源：@jacobgrowth X 貼文「How To ACTUALLY Build an AI UGC Content Machine」
日期：2026-03-18，498K views

## 核心概念

**Vibe Advertising = 設定意圖，agent 全權執行。**

> "the real unlock isn't faster production. it's removing yourself from the production loop entirely"

你設定產品、受眾、調性、轉化目標，以下所有環節（hooks、scripts、visual direction、model selection、rendering、variations、multilingual）自動執行。

## Jacob 的 5 步管線

### Step 1: 輸入（一段話）
一個產品描述 + 一個目標客群畫像 + 一個調性方向。Agent 需要的所有資訊。

### Step 2: Hook 生成（按認知層級）
20 個 hook 變體，按受眾認知狀態分層：
- **Cold**：不知道產品存在，需要先浮現問題
- **Problem Aware**：知道有問題，沒找到解法
- **Solution Aware**：試過替代品，需要換的理由
- **Product Aware**：見過品牌，還沒轉換

### Step 3: 完整劇本 + 視覺指導
每個 hook 展開成完整劇本：節奏、視覺指導、B-roll 建議、情緒教練、停頓時機。
Agent 像好的 creative director 一樣下 brief。

### Step 4: 模型路由（Arcads API）
Agent 根據鏡頭需求，自動路由到最適合的模型：
- **Sora 2 Pro**：真人口播（lip sync + 表情最強）
- **Nano Banana**：量產 UGC 風（速度快、成本低）
- **Seedance**：高級電影感（產品 shot、aspirational lifestyle）
- **Kling Motion Control**：物理真實感（手部動作、倒水、塗抹）
- **Veo 3.1**：環境音內建

### Step 5: 多語言版本
同一 reference image + 同一視覺方向 + 不同語言 prompt（含口音指導）。
一個下午產出 47 支廣告，跨 4 語言、3 模型、4 認知層級。

## 自我改進迴圈（最有價值的部分）

```
第一批影片 → 上傳 → 累積績效數據
  → 哪些 hook 3 秒完播？
  → 哪些腳本帶動點擊？
  → 哪些認知層級轉化？
  → 哪些視覺風格留住注意力？
  → 回饋給 agent → 下一批自動優化
```

## 對「時時靜好」的映射

| Jacob 做法 | 我們的對應 | 差異 |
|-----------|----------|------|
| Claude Cowork 當 creative director | radix (OpenClaw) 當 coordinator | 本質相同 |
| Arcads API 統一多模型 | jimeng-free-api-all + Gemini API | 他有 5 種模型，我們主力 Seedance |
| 一段話描述產品+受眾 | 一句話指定主題 | 我們的系列格式已固定，intent 更簡潔 |
| 20 hook × 4 awareness level | 3-5 hook 變體 | 他做廣告要量測，我們做有機內容要精準 |
| 模型路由 | Seedance + 圖卡雙軌 | 未來可加 Kling |
| 績效回饋自動優化 | **待建設** | 最大缺口 |

## 關鍵差異

Jacob 做**廣告**（追求量大 + A/B test），我們做**有機內容**（追求每集精準命中）。

所以：
- 不需要一次產 47 個變體
- 但每集的 hook 都必須建立在前幾集的績效回饋之上
- Content Rewards 模式（pay per view organic content）更接近我們的場景

## 可行升級

1. **Hook 分層生成**（立即可做）— 每集產 3-5 個 hook 變體
2. **自我改進迴圈**（中期建設）— YouTube 績效回饋 → radix 記憶 → 下集優化
3. **多模型路由**（進階）— 加入 Kling（烹飪動作真實感）
