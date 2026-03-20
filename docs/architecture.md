# Agent Team 架構設計

## 整體架構

```
你（LINE / Telegram）
  │
  ▼
radix（Coordinator / 主 Agent）
  ├── researcher      — 選題研究
  ├── scriptwriter    — 劇本撰寫
  ├── asset_gen       — 素材生成
  ├── assembler       — 影片組裝
  └── reviewer        — 品質審查
```

## 為什麼 radix 當 Coordinator

- radix 是既有的 OpenClaw 主 agent（`~/.openclaw/data-radix/`）
- 不需另創 coordinator，避免多一層調度延遲
- Worker agents 作為 radix 透過 `agentToAgent` 調度的子 agent

## 任務流

```
radix 收到指令（如「做一集維生素C排行榜」）
  → researcher：查 USDA 數據、找認知反差點
  → scriptwriter（載入 seedance skill）：
      ├─ 產出 3-5 個 hook 變體（分認知層級）
      ├─ 產出完整 episode JSON + Seedance prompt
      └─ 參考歷史績效記憶選 hook
  → reviewer：審查 hook 力度 + 數據正確性
  → asset_gen：
      ├─ Gemini → 場景圖 + 定裝照
      ├─ jimeng-free-api-all → Seedance 影片（全自動化）
      ├─ ElevenLabs → TTS（排行榜型）
      └─ Pillow → 圖卡（排行榜型）
  → assembler：assemble_episode.py → 最終 MP4
  → radix 記憶更新：上傳後回收績效 → 存入記憶
```

## 影片型態選擇（由 agent 判斷）

型態不鎖死，scriptwriter 根據以下決策邏輯選擇：

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

### 判斷流程

1. 需要比較幾個東西？ ≥3 → 圖卡/混合型；1-2 → Seedance/圖文快剪
2. 有沒有情緒轉折？有 → Seedance；沒有 → 圖卡
3. 需不需要展示動作？需要 → Seedance；不需要 → 圖卡
4. 成本考量：Seedance 44-88 點/集 vs 圖卡 0 點

### JSON 標注

完整欄位定義見 `schemas/episode.schema.json`（source of truth）。

```json
{
  "type": "standard | ranking | hybrid | quick_cut",
  "type_rationale": "選擇這個型態的理由..."
}
```

## 工具分工

| 工具 | 用途 | 備註 |
|------|------|------|
| **Gemini** | 定裝照、場景圖、食材圖 | 免費，所有圖片生成統一用 Gemini |
| **Seedance（即夢）** | 影片生成 | 只做影片，不做圖片 |
| **ElevenLabs** | TTS 語音 | 排行榜型使用 |
| **Pillow + ffmpeg** | 圖卡動畫 | 排行榜型使用，全自動 |

## Scriptwriter 兩階段工作法

```
Agent 先想（創意腦）
  │  思考：故事、情緒弧線、場景、人物反應
  ▼
創意劇本（自然語言中間產物）
  │  調用 seedance skill（技術翻譯）
  │  翻譯成鏡頭語言、時間戳分鏡、@圖片引用
  ▼
最終 Seedance prompt（可直接貼進即夢）
```

- Agent 決定「拍什麼、為什麼拍、什麼情緒」
- Skill 決定「怎麼拍、什麼鏡頭、什麼參數」
- JSON 中 `creative_direction` 是 agent 產物，`seedance_prompts` 是 skill 產物

## 角色資產庫

角色定裝照由 Gemini 生成，集中管理於 `../elder_kitchen/characters/`。
每集劇本 JSON 透過 `character_id` 指定角色，asset_gen 從資產庫讀取定裝照。
Part1 和 Part2 都導入同一張定裝照，確保人物一致性。

## 自我改進迴圈

```
YouTube Studio（手動或 API）
  → 每集上傳 7 天後回收數據（完播率、點擊率、分享數）
  → 回饋給 radix 的 Markdown 記憶系統
  → 下一集 scriptwriter 自動參考績效記憶
  → hook 越來越準
```
