"""
小靜服裝自動選擇模組

根據主題關鍵字自動選擇小靜的服裝，用在 prompt 生成時。
"""

OUTFIT_RULES = [
    {
        "outfit": "sleep_cap",
        "prompt_fragment": "wearing a tiny beige nightcap with small star, NO apron",
        "zh_fragment": "戴著米色小睡帽（有小星星），不穿圍裙",
        "keywords": ["睡眠", "午睡", "補眠", "失眠", "作息", "生理時鐘", "晝夜節律",
                     "sleep", "nap", "insomnia", "circadian"],
    },
    {
        "outfit": "sport_vest",
        "prompt_fragment": "wearing a light blue sport vest instead of apron",
        "zh_fragment": "穿著淺藍色運動背心，不穿圍裙",
        "keywords": ["運動", "肌力", "快走", "體適能", "平衡", "跌倒", "太極", "伸展",
                     "肌少症", "園藝運動", "exercise", "muscle", "walking", "balance"],
    },
    {
        "outfit": "doctor_coat",
        "prompt_fragment": "wearing a tiny white doctor coat instead of apron",
        "zh_fragment": "穿著迷你白色醫生袍，不穿圍裙",
        "keywords": ["醫學", "健檢", "血壓", "血糖", "癌症", "失智", "帕金森",
                     "medical", "doctor", "diagnosis", "screening"],
    },
    {
        "outfit": "apron",
        "prompt_fragment": "wearing sage green apron with white bowl-leaf icon",
        "zh_fragment": "穿著鼠尾草綠圍裙（碗葉圖示）",
        "keywords": ["飲食", "營養", "烹調", "食物", "咖啡", "茶", "喝水", "纖維",
                     "膽固醇", "cooking", "diet", "nutrition", "food", "coffee", "tea", "water"],
    },
]

# 預設（找不到匹配時）
DEFAULT_OUTFIT = {
    "outfit": "apron",
    "prompt_fragment": "wearing sage green apron with white bowl-leaf icon",
    "zh_fragment": "穿著鼠尾草綠圍裙（碗葉圖示）",
}


def select_outfit(topic_title: str, core_claim: str = "") -> dict:
    """
    根據主題標題和核心宣稱自動選擇小靜服裝。

    Returns: {"outfit": str, "prompt_fragment": str, "zh_fragment": str}
    """
    combined = (topic_title + " " + core_claim).lower()

    for rule in OUTFIT_RULES:
        for kw in rule["keywords"]:
            if kw.lower() in combined:
                return rule

    return DEFAULT_OUTFIT


def get_mascot_prompt(topic_title: str, core_claim: str = "") -> str:
    """
    回傳完整的小靜英文 prompt 片段（含服裝）。
    用在圖卡 prompt 裡。
    """
    outfit = select_outfit(topic_title, core_claim)
    return (
        f"EXACT 3D mascot from reference: matte plastic leopard cat, "
        f"white forehead stripes, dark spots not stripes, big dark brown eyes, pink nose. "
        f"{outfit['prompt_fragment']}. ONE only."
    )


if __name__ == "__main__":
    # 測試
    tests = [
        "午睡超過30分鐘反而傷身",
        "每天8杯水的迷思",
        "園藝治療長肌肉抗肌少症",
        "咖啡不會讓你脫水",
        "週末補眠有沒有用",
        "太極拳與認知功能",
        "血壓控制新觀念",
    ]
    for t in tests:
        r = select_outfit(t)
        print(f"  {t} → {r['outfit']} ({r['zh_fragment']})")
