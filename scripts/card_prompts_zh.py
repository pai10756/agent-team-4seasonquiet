"""
圖卡 Prompt 建構器（全中文版）

取代 generate_card.py 中的英文 prompt builders。
匯入方式：from card_prompts_zh import PROMPT_BUILDERS_ZH
"""

PALETTE = {
    "cream": "#F6F1E7",
    "sage": "#A8B88A",
    "olive_dark": "#4E5538",
    "brown": "#3B2A1F",
    "warm_wood": "#C4A882",
}

BRAND_STYLE = f"""生成一張 1080x1920 的 9:16 直式圖卡。
品牌視覺系統（必須嚴格遵守）：
- 背景：儘量使用真實攝影照片填滿整張圖卡，搭配適度的圖表或插圖
- 標題：大號粗體繁體中文，深橄欖色 {PALETTE['olive_dark']}，必須是畫面中最大最醒目的元素
- 副標題：較小字，棕色 {PALETTE['brown']}，在標題下方
- 徽章：鼠尾草綠 {PALETTE['sage']} 圓角矩形
- 整體風格：溫暖、可信賴、成熟、乾淨
- 底部 20% 安全區不放文字，但可以有背景圖片延伸，不要刻意留白底色
- 照片背景上的文字加白色半透明陰影確保可讀性
"""

NEGATIVE = """
禁止：
- 不要浮水印、商標、簽名、SynthID 標記
- 不要星星、閃光、鑽石、角落裝飾
- 不要重複吉祥物（每張最多一隻）
- 不要霓虹色、強烈陰影、純白背景
- 絕對不要任何英文文字
- 不要手機介面、導航列、按鈕
- 圖片四角邊緣必須乾淨
"""

MASCOT = """
吉祥物「小靜」（3D 磨砂塑膠玩具，Pop Mart 品質）：
- 台灣石虎，大圓頭小身體，頭身比 1:1
- 溫暖黃棕色身體，圓形深棕色斑點（不是條紋）
- 額頭兩條粗白色垂直條紋
- 黑色耳尖，耳後白斑
- 粉紅三角鼻，大圓深棕眼帶白色高光
- 磨砂塑膠材質，無毛皮質感
- 鼠尾草綠圍裙，胸前白色碗葉圖示
- 必須與參考圖完全一致
"""


def build_poster_cover(scene: dict, episode: dict) -> str:
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    badge = scene.get("badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "溫暖的室內場景，柔和自然光")
    has_mascot = scene.get("mascot_presence", False)
    interaction = scene.get("mascot_interaction_mode", "")
    expr = scene.get("mascot_expression", "thinking")
    pose = scene.get("mascot_pose", "hug_object_side")

    prompt = f"""{BRAND_STYLE}

版面：上方標題區，中下方主視覺，背景用真實攝影照片填滿。

標題（最大粗體深橄欖色）：「{main_text}」
副標題（較小棕色）：「{sub_text}」
"""
    if badge:
        prompt += f"徽章（右上角鼠尾草綠圓角矩形）：「{badge}」\n"
    prompt += f"\n主視覺物件：{hero}\n背景場景：{bg}\n"

    if has_mascot:
        pose_desc = interaction if interaction else f"表情{expr}，姿勢{pose}"
        prompt += f"\n吉祥物（僅一隻，配角，佔畫面 20-30%）：\n{MASCOT}\n{pose_desc}\n"

    prompt += NEGATIVE
    return prompt


def build_comparison_card(scene: dict, episode: dict) -> str:
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    badge = scene.get("badge_text", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")

    prompt = f"""{BRAND_STYLE}

版面：上方標題，中間對比排版，清晰的視覺對比。
背景用真實攝影照片或溫暖米白底搭配圖表插圖。

標題（最大粗體深橄欖色）：「{main_text}」
副標題（較小棕色）：「{sub_text}」
"""
    if badge:
        prompt += f"徽章（右上角鼠尾草綠圓角矩形）：「{badge}」\n"
    if source_badge:
        prompt += f"來源標註（下方，鼠尾草綠圓角矩形小字）：「{source_badge}」\n"

    prompt += f"\n對比視覺內容：{hero}\n\n不要吉祥物。乾淨的資訊圖表風格。所有文字必須是繁體中文。\n{NEGATIVE}"
    return prompt


def build_evidence_card(scene: dict, episode: dict) -> str:
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "溫暖米白底搭配圖表")

    prompt = f"""{BRAND_STYLE}

版面：上方標題，中間數據視覺化或證據呈現。
背景用真實攝影照片或溫暖底色搭配圖表。

標題（最大粗體深橄欖色）：「{main_text}」
副標題（較小棕色）：「{sub_text}」
"""
    if source_badge:
        prompt += f"來源標註（下方，鼠尾草綠圓角矩形小字）：「{source_badge}」\n"

    prompt += f"\n證據視覺內容：{hero}\n背景：{bg}\n\n不要吉祥物。乾淨權威的現代資訊圖表風格。\n{NEGATIVE}"
    return prompt


def build_safety_reminder(scene: dict, episode: dict) -> str:
    main_text = scene.get("on_screen_text_main", "")
    sub_text = scene.get("on_screen_text_sub", "")
    source_badge = scene.get("source_badge_text", "")
    hero = scene.get("hero_object", "")
    bg = scene.get("background_scene", "溫暖的生活場景")

    prompt = f"""{BRAND_STYLE}

這張圖卡使用真實攝影照片當背景，填滿整張圖卡。
攝影風格：Sony A7IV, 50mm f/1.8, 淺景深, 暖色調, 自然窗光。

版面：
- 上方：大標題和副標題，加白色半透明陰影確保在照片上清晰可讀
- 中下方：攝影主題內容
- 整張圖片從上到下填滿，不留白

標題（最大粗體深橄欖色，加文字陰影）：「{main_text}」
副標題（較小棕色）：「{sub_text}」
"""
    if source_badge:
        prompt += f"來源標註（下方小字）：「{source_badge}」\n"

    prompt += f"\n攝影主題：{hero}\n場景：{bg}\n\n不要吉祥物，不要插圖，純攝影加文字疊加。\n{NEGATIVE}"
    return prompt


def build_brand_closing(scene: dict, episode: dict) -> str:
    main_text = scene.get("on_screen_text_main", "時時靜好")
    sub_text = scene.get("on_screen_text_sub", "我是小靜，我們下次見！")
    bg = scene.get("background_scene", "柔和溫暖的背景")
    interaction = scene.get("mascot_interaction_mode", "")
    expr = scene.get("mascot_expression", "goodbye")
    pose = scene.get("mascot_pose", "greet_viewer")

    pose_desc = interaction if interaction else f"表情溫暖微笑，一隻爪子揮手道別"

    prompt = f"""{BRAND_STYLE}

版面：
- 上方居中：品牌名「{main_text}」大號粗體深橄欖色
- 品牌名下方：「{sub_text}」較小棕色
- 中下方：吉祥物小靜，佔畫面 50-60%，是這張卡的主角
- 背景：{bg}，柔和散景，溫暖夢幻

吉祥物（僅一隻，這張卡的主角）：
{MASCOT}
{pose_desc}
吉祥物要大、突出、居中在畫面下半部。

重要規則：
- 只顯示上述指定的文字，不要加額外文字、標籤、按鈕
- 不要重複已顯示的文字
- 一隻吉祥物，不要重複
{NEGATIVE}"""
    return prompt


PROMPT_BUILDERS_ZH = {
    "poster_cover": build_poster_cover,
    "comparison_card": build_comparison_card,
    "evidence_card": build_evidence_card,
    "safety_reminder": build_safety_reminder,
    "brand_closing": build_brand_closing,
}
