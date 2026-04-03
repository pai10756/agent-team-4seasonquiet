"""
Pre-flight 自動檢查模組 — 每集生產前必跑

用法：
  from preflight_check import run_preflight
  run_preflight(cards, narrations, facts_checked=True)

或 CLI：
  python scripts/preflight_check.py --cards "prompt1|||prompt2" --narrations "台詞1|||台詞2"
"""
import re
import sys


# ══════════════════════════════════════
# 1. Prompt 長度檢查（≤ 300 英文字）
# ══════════════════════════════════════
def check_prompt_length(cards: list[tuple[str, str]], max_words: int = 300) -> list[str]:
    """cards: [(name, prompt_text), ...]"""
    errors = []
    for name, prompt in cards:
        word_count = len(prompt.split())
        if word_count > max_words:
            errors.append(f"❌ {name}: prompt {word_count} 字，超過上限 {max_words} 字")
        else:
            print(f"  ✓ {name}: {word_count}/{max_words} 字")
    return errors


# ══════════════════════════════════════
# 2. 旁白總長預估（中文 ≤ 60 秒）
# ══════════════════════════════════════
def check_narration_length(narrations: list[str], max_seconds: float = 60.0,
                           chars_per_second: float = 4.0, atempo: float = 1.1) -> list[str]:
    """預估旁白總長。中文約 4 字/秒，atempo 1.1 加速後。"""
    errors = []
    total_chars = 0
    for i, text in enumerate(narrations):
        chars = len(re.sub(r'[，。、；！？\s]+', '', text))
        total_chars += chars
        est = chars / chars_per_second / atempo
        print(f"  seg_{i+1:02d}: {chars} 字 ≈ {est:.1f}s")

    total_est = total_chars / chars_per_second / atempo
    print(f"  合計: {total_chars} 字 ≈ {total_est:.1f}s (上限 {max_seconds}s)")
    if total_est > max_seconds:
        errors.append(f"❌ 旁白預估 {total_est:.1f}s 超過 {max_seconds}s，需精簡 {total_chars - int(max_seconds * chars_per_second * atempo)} 字")
    return errors


# ══════════════════════════════════════
# 3. 多音字掃描
# ══════════════════════════════════════
POLYPHONE_DICT = {
    "數": ("「數」有 shǔ(動詞:去數) / shù(名詞:數量) 兩音", "算"),
    "長": ("「長」有 zhǎng(成長) / cháng(長度) 兩音", None),
    "重": ("「重」有 zhòng(重量) / chóng(重複) 兩音", None),
    "還": ("「還」有 hái(還是) / huán(歸還) 兩音", None),
    "得": ("「得」有 dé(得到) / de(助詞) / děi(必須) 三音", None),
    "了": ("「了」有 le(助詞) / liǎo(了解) 兩音", None),
    "行": ("「行」有 xíng(行走) / háng(行業) 兩音", None),
    "度": ("「度」有 dù(溫度) / duó(度量) 兩音", None),
    "分": ("「分」有 fēn(分開) / fèn(份量) 兩音", None),
    "降": ("「降」有 jiàng(下降) / xiáng(投降) 兩音", None),
    "量": ("「量」有 liáng(測量) / liàng(數量) 兩音", None),
    "率": ("「率」有 lǜ(比率) / shuài(率領) 兩音", None),
    "調": ("「調」有 tiáo(調整) / diào(調查) 兩音", None),
    "間": ("「間」有 jiān(中間) / jiàn(間隔) 兩音", None),
    "著": ("「著」有 zhe(助詞) / zháo(著火) / zhù(著作) 三音", None),
    "血": ("「血」有 xuè(書面) / xiě(口語) 兩音", None),
    "壓": ("「壓」有 yā(壓力) / yà(壓軸) 兩音", None),
    "發": ("「發」有 fā(發生) / fà(頭髮) 兩音", None),
    "樂": ("「樂」有 lè(快樂) / yuè(音樂) 兩音", None),
    "覺": ("「覺」有 jué(感覺) / jiào(睡覺) 兩音", None),
    "少": ("「少」有 shǎo(多少) / shào(少年) 兩音", None),
    "中": ("「中」有 zhōng(中間) / zhòng(中獎) 兩音", None),
    "切": ("「切」有 qiē(切開) / qiè(一切) 兩音", None),
}


# 常見無風險組合（不需要警告）
POLYPHONE_SAFE = {
    "分": ["分鐘", "分析", "分享", "分鐘內", "分之", "百分", "十分", "部分"],
    "了": ["了解", "了不起"],  # 助詞「了」太常見，只警告特定組合
    "間": ["時間", "之間", "中間", "期間"],
    "重": ["重要", "重點", "重新"],
    "發": ["發現", "發表", "發生", "發展"],
    "血": ["血管", "血壓", "血液", "血糖"],
    "調": ["調查", "調整", "調節"],
    "量": ["數量", "質量", "能量", "份量", "劑量", "熱量", "飲水量"],
    "降": ["下降", "降低"],
    "覺": ["感覺", "知覺", "視覺"],
}


def check_polyphones(narrations: list[str]) -> list[str]:
    """掃描多音字，標記可能唸錯的位置。跳過常見安全組合。"""
    warnings = []
    for i, text in enumerate(narrations):
        for char, (desc, alt) in POLYPHONE_DICT.items():
            if char not in text:
                continue
            # 檢查是否在安全組合中
            safe_words = POLYPHONE_SAFE.get(char, [])
            # 助詞「了」只警告特定組合，跳過一般用法
            if char == "了" and "了解" not in text and "了不起" not in text:
                continue
            all_safe = all(
                any(sw in text[max(0,j-2):j+3] for sw in safe_words)
                for j, c in enumerate(text) if c == char
            )
            if all_safe:
                continue
            ctx = ""
            for j, c in enumerate(text):
                if c == char:
                    start = max(0, j - 3)
                    end = min(len(text), j + 4)
                    ctx = text[start:end]
                    break
            alt_hint = f" → 建議改用「{alt}」" if alt else ""
            warnings.append(f"  ⚠️ seg_{i+1:02d}: 「{ctx}」{desc}{alt_hint}")
    return warnings


# ══════════════════════════════════════
# 4. 敏感詞掃描（中國平台）
# ══════════════════════════════════════
SENSITIVE_WORDS = [
    "推翻", "革命", "政變", "獨立", "鎮壓", "屠殺", "六四",
    "共產", "民主", "自由", "人權", "維權", "法輪", "達賴",
    "習近平", "毛澤東", "天安門", "西藏", "新疆", "台獨",
    "死亡率",  # 頻道調性：改用「風險」
    "超級食物",  # 醫療宣稱禁用
]


def check_sensitive_words(narrations: list[str]) -> list[str]:
    """掃描敏感詞。"""
    errors = []
    for i, text in enumerate(narrations):
        for word in SENSITIVE_WORDS:
            if word in text:
                errors.append(f"  ❌ seg_{i+1:02d}: 含敏感詞「{word}」")
    return errors


# ══════════════════════════════════════
# 5. Prompt 標準語句檢查
# ══════════════════════════════════════
REQUIRED_PHRASES = [
    "No English",
    "No phone UI",
    "Bottom 20%",
    "Traditional Chinese",
]


def check_prompt_standards(cards: list[tuple[str, str]]) -> list[str]:
    """檢查 prompt 是否包含必要的標準語句。"""
    warnings = []
    for name, prompt in cards:
        for phrase in REQUIRED_PHRASES:
            if phrase.lower() not in prompt.lower():
                warnings.append(f"  ⚠️ {name}: 缺少「{phrase}」")
    return warnings


# ══════════════════════════════════════
# 主函數
# ══════════════════════════════════════
def run_preflight(cards: list[tuple[str, str]], narrations: list[str],
                  facts_checked: bool = False) -> bool:
    """
    執行所有 pre-flight 檢查。
    cards: [(name, prompt_text), ...]
    narrations: [text1, text2, ...]
    facts_checked: 是否已完成事實查核
    Returns True if all passed.
    """
    print("=" * 50)
    print("🔍 Pre-flight 自動檢查")
    print("=" * 50)

    all_errors = []

    # 1. Prompt 長度
    print("\n📏 Prompt 長度檢查（≤ 300 字）：")
    all_errors.extend(check_prompt_length(cards))

    # 2. 旁白總長
    print("\n⏱️ 旁白總長預估（≤ 60 秒）：")
    all_errors.extend(check_narration_length(narrations))

    # 3. 多音字
    print("\n🔤 多音字掃描：")
    poly_warnings = check_polyphones(narrations)
    if poly_warnings:
        for w in poly_warnings:
            print(w)
    else:
        print("  ✓ 無多音字風險")

    # 4. 敏感詞
    print("\n🚫 敏感詞掃描：")
    sensitive = check_sensitive_words(narrations)
    if sensitive:
        all_errors.extend(sensitive)
        for s in sensitive:
            print(s)
    else:
        print("  ✓ 無敏感詞")

    # 5. Prompt 標準語句
    print("\n📋 Prompt 標準語句檢查：")
    std_warnings = check_prompt_standards(cards)
    if std_warnings:
        for w in std_warnings:
            print(w)
    else:
        print("  ✓ 標準語句完整")

    # 6. 事實查核閘門
    print("\n🔬 事實查核：")
    if facts_checked:
        print("  ✓ 已完成事實查核")
    else:
        all_errors.append("❌ 事實查核未完成！請先用 web search 驗證所有數據")
        print("  ❌ 未完成！請先驗證所有數據")

    # 結果
    print("\n" + "=" * 50)
    if all_errors:
        print(f"🚨 發現 {len(all_errors)} 個問題，請修正後再跑：")
        for e in all_errors:
            print(f"  {e}")
        print("=" * 50)
        return False
    else:
        print("✅ 全部通過，可以開始生產！")
        print("=" * 50)
        return True


if __name__ == "__main__":
    # CLI demo
    print("Pre-flight check module loaded.")
    print("Usage: from preflight_check import run_preflight")
    print("       run_preflight(cards, narrations, facts_checked=True)")
