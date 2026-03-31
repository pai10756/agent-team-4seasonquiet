#!/usr/bin/env python3
"""
Health Digest ↔ 主題庫比對器
讀取每日健康研究速報，用 Gemini 比對時時靜好 50 題主題庫，
產出：佐證更新 + 候選新主題。

用法：
  python3 match_digest_to_topics.py                    # 用今天的 digest
  python3 match_digest_to_topics.py 2026-03-31         # 指定日期
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── 路徑設定 ──────────────────────────────────────────────────────────────
FACTORY_DIR = Path("/home/shany/.openclaw/data-radix/health_digest_factory")
DIGEST_DIR = FACTORY_DIR / "outputs" / "digests"
OUTPUT_DIR = FACTORY_DIR / "outputs" / "topic_matching"

# 主題庫（純文字摘要，避免讀整份 markdown）
TOPICS_50 = {
    1: "生理時鐘紊亂與失智風險",
    2: "午睡的最佳時機",
    3: "睡不好，大腦老更快",
    4: "光照如何重設你的生理時鐘",
    5: "晚間藍光對睡眠的真正影響",
    6: "睡眠呼吸中止：沉默的健康殺手",
    7: "入睡儀式：打造你的黃金 30 分鐘",
    8: "週末補眠真的有用嗎？",
    9: "腸道菌相多樣性：纖維種類比份量重要",
    10: "雞蛋與膽固醇：被冤枉的好食物",
    11: "台灣人纖維攝取嚴重不足",
    12: "喝水迷思：真的需要八杯水嗎？",
    13: "抗發炎飲食的日常實踐",
    14: "克菲爾與益生元纖維的黃金組合",
    15: "喝茶的長壽密碼",
    16: "咖啡不會讓你脫水",
    17: "烹調方式決定營養價值",
    18: "代謝飲食法：2026 新趨勢",
    19: "走路的科學：每天幾步最有效？",
    20: "太極拳與認知功能",
    21: "平衡訓練：預防跌倒的關鍵",
    22: "六分鐘快走啟動大腦前額葉",
    23: "居家簡易肌力訓練",
    24: "柔軟度與伸展的真實效果",
    25: "任何年齡開始運動都不嫌晚",
    26: "園藝勞動也是運動",
    27: "記憶力衰退不等於失智",
    28: "終身學習如何保護大腦",
    29: "社交活動是大腦的維他命",
    30: "音樂對大腦的神奇力量",
    31: "益智遊戲真的能防失智嗎？",
    32: "雙語能力與認知儲備",
    33: "手寫 vs. 打字：哪個更護腦？",
    34: "閱讀習慣與大腦老化速度",
    35: "控制血壓就是保護大腦",
    36: "長輩血糖藥可能要減量",
    37: "骨密度三寶：膠原蛋白＋鈣＋維生素 D",
    38: "膝蓋痛不代表不能動",
    39: "肌少症：比骨質疏鬆更可怕",
    40: "健康老化的最佳飲食模式",
    41: "孤獨感對健康的傷害超乎想像",
    42: "感恩練習如何化解孤獨",
    43: "找到人生目標就是最好的長壽藥",
    44: "壓力管理：呼吸法的科學根據",
    45: "當志工讓心理更健康",
    46: "森林浴：大自然的抗焦慮處方",
    47: "吃飯不要只吃白粥",
    48: "「少量多餐」不一定適合每個人",
    49: "走路比跑步更適合長輩減脂",
    50: "睡太多也是健康警訊",
}

# ── Gemini API ────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Telegram 推播
TELEGRAM_BOT_TOKEN = "8432291848:AAHRGf9c0YQQe4g0H24msEWSi-LMau1oshQ"
TELEGRAM_CHAT_ID = "8345829865"
TELEGRAM_API = f"https://telegram-api-proxy.shanyinpai.workers.dev/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def gemini_call(prompt: str, api_key: str, timeout: int = 60) -> str:
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }).encode("utf-8")
    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def send_telegram(text: str) -> None:
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        TELEGRAM_API, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if not result.get("ok"):
            print(f"⚠️ Telegram 發送失敗: {result}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Telegram 例外: {e}", file=sys.stderr)


def build_topics_text() -> str:
    lines = []
    for num, title in sorted(TOPICS_50.items()):
        lines.append(f"#{num} {title}")
    return "\n".join(lines)


def match(digest: list, api_key: str) -> dict:
    digest_text = json.dumps(digest, ensure_ascii=False, indent=2)
    topics_text = build_topics_text()

    prompt = f"""你是「時時靜好」YouTube Shorts 頻道的選題顧問。頻道定位：台灣中高齡觀眾的實證健康內容。

以下是今天的健康研究速報（來自 PubMed 最新論文）：
{digest_text}

以下是頻道現有的 50 個主題：
{topics_text}

請做兩件事：

**任務一：佐證比對**
檢查每篇速報是否跟現有 50 題中的某個主題高度相關。如果相關，記錄下來作為該主題的最新實證佐證。

**任務二：候選新主題**
如果某篇速報的主題不在 50 題之內，但對台灣長輩有實用價值且適合做成 Shorts，就列為候選新主題。

**輸出格式**：只輸出一個 JSON object，包含兩個欄位：
- "evidence_updates": 一個 array，每個元素包含：
  - "topic_id": 對應的主題編號（整數）
  - "topic_title": 主題名稱
  - "digest_title": 速報標題
  - "relevance": 簡短說明為何相關（一句話）
  - "doi": 論文 DOI
  - "date": 論文日期
- "new_candidates": 一個 array，每個元素包含：
  - "suggested_title": 建議的主題名稱（口語化、長輩看得懂）
  - "digest_title": 來源速報標題
  - "reason": 為何值得做成 Shorts（一句話）
  - "doi": 論文 DOI
  - "suggested_category": 建議歸入哪一類（睡眠/營養/運動/大腦/慢性病/心理/反直覺）
  - "suggested_format": 建議的視覺格式代碼（A-H）

如果某篇速報既不相關也不值得做新主題，就跳過。
只輸出 JSON，不要加說明文字。"""

    text = gemini_call(prompt, api_key)
    return json.loads(text)


def build_telegram_summary(result: dict, date_str: str) -> str:
    lines = [f"📋 *主題庫比對報告* — {date_str}\n"]

    evidence = result.get("evidence_updates", [])
    candidates = result.get("new_candidates", [])

    if evidence:
        lines.append("*🔬 佐證更新*")
        for e in evidence:
            lines.append(
                f"• #{e['topic_id']} {e['topic_title']}\n"
                f"  ← _{e['digest_title']}_\n"
                f"  {e['relevance']}"
            )
        lines.append("")

    if candidates:
        lines.append("*💡 候選新主題*")
        for c in candidates:
            lines.append(
                f"• *{c['suggested_title']}*\n"
                f"  來源：_{c['digest_title']}_\n"
                f"  {c['reason']}\n"
                f"  分類：{c['suggested_category']} | 格式：{c['suggested_format']}"
            )
        lines.append("")

    if not evidence and not candidates:
        lines.append("今天的速報與現有主題無直接關聯，也沒有新主題候選。")

    lines.append("📂 完整 JSON 已存入 topic\\_matching/")
    return "\n".join(lines)


def main():
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)

    # 決定日期
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = now.strftime("%Y%m%d")

    # 讀取 digest
    digest_file = DIGEST_DIR / f"digest_{date_str}.json"
    if not digest_file.exists():
        # 嘗試 YYYY-MM-DD 格式
        alt = DIGEST_DIR / f"digest_{date_str.replace('-', '')}.json"
        if alt.exists():
            digest_file = alt
        else:
            print(f"❌ 找不到 digest: {digest_file}")
            sys.exit(1)

    print(f"📖 讀取 digest: {digest_file.name}")
    digest = json.loads(digest_file.read_text(encoding="utf-8"))
    print(f"  共 {len(digest)} 篇速報")

    # API key
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        # 嘗試從 .env 讀取
        env_file = FACTORY_DIR.parent / "almanac_factory" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GOOGLE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("❌ 未設定 GOOGLE_API_KEY")
        sys.exit(1)

    # Gemini 比對
    print("🤖 Gemini 比對中...")
    try:
        result = match(digest, api_key)
    except Exception as e:
        print(f"❌ Gemini 比對失敗: {e}")
        sys.exit(1)

    evidence = result.get("evidence_updates", [])
    candidates = result.get("new_candidates", [])
    print(f"  佐證更新: {len(evidence)} 筆")
    print(f"  候選新主題: {len(candidates)} 筆")

    # 儲存結果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"match_{date_str}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 已存: {out_file}")

    # 推播 Telegram
    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str
    tg_msg = build_telegram_summary(result, display_date)
    print("📱 推播 Telegram...")
    send_telegram(tg_msg)

    print("✅ 完成")


if __name__ == "__main__":
    main()
