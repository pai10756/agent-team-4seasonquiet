#!/usr/bin/env bash
# Health Digest Factory — 每日研究速報產線
# 排程：每天 07:30 執行
# 流程：抓論文 → GPT-5.4 篩選翻譯 → 推播 Telegram → 比對主題庫

set -euo pipefail

FACTORY_DIR="$HOME/.openclaw/data-radix/health_digest_factory"
LOG_DIR="$FACTORY_DIR/logs"
mkdir -p "$LOG_DIR"

LOGFILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

# 載入 Telegram 通知
source "$HOME/.openclaw/scripts/notify_telegram.sh"

exec > >(tee -a "$LOGFILE") 2>&1

echo "========================================"
echo "🏥 Health Digest Factory — $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

FAIL=0

# Step 1: 抓取 PubMed 論文（近 7 天）
echo ""
echo "📥 Step 1: 抓取 PubMed 論文..."
if ! python3 "$FACTORY_DIR/scripts/fetch_papers.py" 7; then
    echo "❌ Step 1 失敗"
    FAIL=1
fi

# Step 2: GPT-5.4 篩選+翻譯
if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "🤖 Step 2: 產出研究速報..."
    if ! python3 "$FACTORY_DIR/scripts/generate_digest.py"; then
        echo "❌ Step 2 失敗"
        FAIL=1
    fi
fi

# Step 3: 推播 Telegram（HTML 格式）
if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "📱 Step 3: 推播 Telegram..."
    if ! python3 "$FACTORY_DIR/scripts/publish_telegram.py"; then
        echo "❌ Step 3 失敗"
        FAIL=1
    fi
fi

# Step 4: 比對主題庫（Gemini flash）
if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "📋 Step 4: 比對主題庫..."
    if ! GOOGLE_API_KEY="${GEMINI_API_KEY:-$GOOGLE_API_KEY}" python3 "$FACTORY_DIR/scripts/match_digest_to_topics.py"; then
        echo "⚠️ Step 4 比對失敗（不影響主流程）"
    fi
fi

echo ""
echo "========================================"
if [ "$FAIL" -eq 0 ]; then
    echo "✅ Health Digest Factory 完成 — $(date '+%H:%M:%S')"
else
    echo "❌ Health Digest Factory 失敗 — $(date '+%H:%M:%S')"
    notify "❌ *Health Digest Factory 失敗*
請檢查 log: $LOGFILE"
fi
echo "========================================"

exit $FAIL
