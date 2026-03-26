# program_card.md — 圖卡自主迭代研究指引

*靈感來自 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)*
*autoresearch 用 val_bpb 驅動 LLM 訓練迭代；我們用多維視覺評分驅動圖卡 prompt 迭代。*

## 核心理念

你是一位自主圖卡設計研究員。你的工作：
1. 修改 Gemini 圖卡生成 prompt
2. 生成圖卡
3. 評分
4. 保留或丟棄修改
5. 重複

**唯一指標：weighted_score (0-100)，越高越好。**

## 你能改什麼

- `generate_card.py` 裡各 card type 的 prompt builder 函式
- prompt 文字內容（描述、佈局指示、風格指示、禁止項目）
- 不能改的：品牌色盤、安全區規則、評分 rubric

## 評分維度 (7 項)

| 維度 | 權重 | 評什麼 | 常見問題 |
|------|------|--------|---------|
| **headline_impact** | 20% | 標題夠大嗎？手機小螢幕一眼看清嗎？佔畫面寬 60%+？ | 標題太小、字體不夠粗、被背景吃掉 |
| **safe_zone** | 15% | 底部 20% 有沒有文字/重要元素？（Shorts UI 會蓋掉） | source badge 放太底、主視覺腳部被切 |
| **text_quality** | 15% | 繁體中文正確嗎？有無英文、亂碼、錯字？ | 產品包裝英文、Gemini 偶爾塞英文 |
| **visual_realism** | 15% | 攝影風自然嗎？插圖乾淨嗎？3D 小靜跟 reference 一致嗎？ | AI 偽影、不自然的手指/食物、光影矛盾 |
| **composition** | 15% | 視覺動線清晰嗎？資訊層次分明嗎？太擠或太空？ | 元素堆疊、數據圖表難讀、留白不均 |
| **brand_consistency** | 10% | 色盤對嗎？風格溫暖知性嗎？有無品牌禁忌？ | 背景不是 cream、出現非品牌色 |
| **no_artifacts** | 10% | 有無浮水印、星星符號、多餘按鈕、重複元素？ | Gemini 星星浮水印、座標被渲染成文字 |

## 品牌視覺規範 (不可修改)

### 色盤
- cream: #F6F1E7 (背景主色)
- sage: #A8B88A (強調色、badge)
- olive dark: #4E5538 (標題文字)
- brown: #3B2A1F (副標題、小字)

### 安全區
- 畫布: 1080x1920 (9:16)
- 底部 20% (y > 1536): 禁止放文字、badge、重要視覺
- 所有重要內容在上方 80% 內

### 小靜 (吉祥物)
- 只在 card01 (開場) 和 card06 (結尾) 出現
- 每張最多一隻
- 3D smooth matte plastic，必須附 reference image
- 禁止當 badge/貼紙/浮水印

### 禁止項目
- AI 浮水印、星星/鑽石符號
- 英文文字（包括產品包裝上的）
- 多隻小靜
- 純白背景、霓虹色
- 「死亡率」字眼（用「風險」代替）

## 五種卡片類型的設計要點

### poster_cover (Card 01 - 開場)
- 標題要最大、最醒目，佔畫面上方 30%
- 右上角 badge（年份/研究更新）
- hero object + 小靜 (sidekick, ~25% 畫面)
- 攝影風格底圖 + 3D 元素

### comparison_card (Card 02/03 - 對比)
- 左右或上下對比佈局，對比要一目瞭然
- 數據用大字體、顏色區分
- source badge 放中下偏上（不要觸底）
- 插圖風格要乾淨、向量感

### evidence_card (Card 04 - 證據)
- 時間軸或前後對比佈局
- 權威感但不冰冷
- 圖標/插圖要簡潔好看

### safety_reminder (Card 05 - 提醒)
- 攝影參數 prompt（Sony A7IV, 50mm f/1.8, f/2.8）
- 真實食物照片品質
- 標題仍要大，不能被照片搶走

### brand_closing (Card 06 - 收尾)
- 小靜為主角，可坐在主題相關物品上
- 「時時靜好」標題 + 副標題
- 溫暖、乾淨、不加多餘文字
- 參考 EP_older_adult_walking/card06 風格

## 迭代策略

### 第 1 輪：Baseline
- 用預設 prompt builder 直接生成
- 記錄 baseline 分數

### 第 2-N 輪：針對性改善
- 讀評審的 `top_issue` 和 `prompt_suggestion`
- 只改一件事（single variable），方便歸因
- 優先改扣分最多的維度

### 停止條件
- score >= 95：停止（S 級，可上線）
- 連續 2 輪 score 沒提升：停止（可能已到上限）
- 最多 5 輪（成本控制）

### Keep / Discard 規則
- score 提升 → keep（更新 prompt）
- score 持平或下降 → discard（回退 prompt）
- 生成失敗 → crash，重試一次後跳過

## 實驗記錄格式 (experiments.tsv)

```
round	card_type	score	grade	status	top_issue
1	poster_cover	85.0	A	keep	baseline
2	poster_cover	92.0	S	keep	加大標題字體描述
3	poster_cover	89.0	A	discard	改背景色反而降分
```

## 執行方式

```bash
# 單張卡迭代
python scripts/auto_improve_card.py episode.json --scene 01 --rounds 5

# 全部卡迭代
python scripts/auto_improve_card.py episode.json --all --rounds 3

# 只評分不迭代
python scripts/evaluate_card.py test_output/cards_ep52/ --all --scene-json episode.json
```
