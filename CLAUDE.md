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
