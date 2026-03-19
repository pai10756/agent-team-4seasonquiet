# Seedance API 自動化方案

目前 Seedance（即夢）沒有官方 API，但有多個開源逆向方案可實現全自動化。

## 核實結果（2026-03-19）

Grok AI 提供的 `wwwzhouhui/seedance2.0` 資訊經核實 **全部正確**。

## 推薦方案

### 1. jimeng-free-api-all（首選）

- **作者**：wwwzhouhui（同 seedance2.0 作者）
- **Stars**：536
- **優勢**：同時支援圖片+影片生成，**OpenAI 相容 API 格式**，更適合程式化整合
- **部署**：Docker 一鍵部署

### 2. seedance2.0（Web UI）

- **Repo**：github.com/wwwzhouhui/seedance2.0
- **Stars**：v0.0.2，活躍維護
- **架構**：React 19 + Express 4.21 + Vite 6
- **部署**：Docker（docker-compose.yml）
- **API 端點**：
  - `POST /api/generate-video` — 提交生成任務（multipart/form-data）
  - `GET /api/task/:taskId` — 查詢任務狀態
  - `GET /api/video-proxy?url=` — 代理即夢 CDN（CORS bypass）
  - `GET /api/health` — 健康檢查

### 3. jimeng-mcp-server（MCP 整合）

- **作者**：wwwzhouhui
- **Stars**：36
- **優勢**：MCP 伺服器，讓 Claude / Cherry Studio 直接呼叫即夢
- **適用**：如果 OpenClaw 支援 MCP 就更直接

## 共同限制

| 項目 | 說明 |
|------|------|
| **逆向工程** | 使用 Playwright-core 繞過即夢 `a_bogus` 簽名，非官方 API |
| **SessionID 過期** | 有效期有限，需定期重新取得 |
| **需要即夢帳號** | 中國大陸手機號 +86，需購買積分 |
| **穩定性** | 即夢平台更新可能導致 API 失效 |

## 對生產管線的意義

如果 API 穩定可用，Seedance 生成不再需要手動操作：

```
radix 收到指令
  → scriptwriter 寫 JSON + Seedance prompt
  → asset_gen 生成場景圖（Gemini API）
  → asset_gen 呼叫 jimeng-free-api-all 生成 Part1 影片  ← 原本手動
  → asset_gen 截圖 → 生成定裝照 → 生成 Part2 影片     ← 也自動化
  → assembler 組裝最終影片
  → radix 回報：「影片好了，請審片」
```

## 建議優先順序

1. 先部署 `jimeng-free-api-all`（Docker），驗證穩定性
2. 試試 `jimeng-mcp-server`，如果 OpenClaw 支援 MCP 更直接
3. SessionID 過期問題需監控——radix heartbeat 定期檢查 API 健康

## 其他相關專案

| 專案 | Stars | 說明 |
|------|-------|------|
| dongshuyan/dreamina2api | 67 | 海外版 Dreamina API |
| LiJunYi2/dreamina-api | 22 | Dreamina via Cloudflare Workers |
| Anil-matcha/Seedance-2.0-API | 57 | Python wrapper |
| PCPrincipal67/seedance-chain | 25 | 長影片自動化 via Volcano Ark |
| fkxianzhou/ComfyUI-Jimeng-API | 31 | ComfyUI 節點 |
