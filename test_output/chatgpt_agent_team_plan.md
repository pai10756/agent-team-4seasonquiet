一、先重新定義整個頻道的品牌與美術系統
1. 頻道定位

請在系統層明確寫死：

品牌名：時時靜好
受眾：中高齡者、照顧者、一般家庭健康決策者
內容任務：用低壓、可信、好懂的方式，幫觀眾理解健康與生活迷思
美術氣質：溫暖、清楚、成熟、可信、生活感，不幼態、不廉價、不聳動
2. 視覺母風格

把目前新風格命名成固定 style token，例如：

STYLE_SHIZHI_POSTER_REALISM_V1

定義如下：

主體比例：寫實底圖 70–80%，向量元素 20–30%
封面語法：大標題海報風
底圖語法：單一寫實 hero object
品牌語法：小靜只作品牌輔助角色
資訊語法：每張圖只講一件事
情緒語法：角色表情必須服務標題情緒
3. 色彩規格

固定 palette，不讓每次亂漂：

奶油白：背景與留白主色
淺鼠尾草綠：品牌底條、badge、分隔塊
深橄欖／深棕：主標題
柔和暖木色：生活照片常見基底
避免高飽和紅、亮藍、廉價金色、螢光漸層

這一點很重要。
因為你要的是「生活健康品牌」，不是「醫療警報圖」或「保健品廣告」。

二、重新定義「小靜」在系統中的角色，不再讓模型亂用
1. 小靜的正確定位

請在全系統寫死：

小靜 = 品牌主持人，不是每張圖都要出現的裝飾貼圖。

小靜允許的任務
開場提問
關鍵提醒
片尾打招呼 / 自我介紹
品牌辨識
小靜不允許的任務
每張圖都站在角落
變成 logo badge
同一張圖出現兩隻
當底部浮水印貼紙
在資訊卡中搶走主視覺
2. 小靜出現頻率規則

先定成硬規則：

第 1 張：可出現
第 2–5 張：預設不出現
第 6 張：可出現
除非特別指定，其他卡禁止小靜
3. 小靜互動模式

把互動模式做成欄位，不要只靠 prompt 描述：

{
  "mascot_presence": "opening_only | closing_only | both | none",
  "mascot_interaction_mode": "hug_object | lean_on_object | greet_viewer | hold_badge | think_with_object",
  "mascot_count": 1,
  "allow_mascot_logo": false,
  "allow_mascot_badge": false,
  "allow_duplicate_mascot": false
}
4. 小靜表情對應表

這個非常重要，因為你剛剛已經抓到：
問句標題不能配驚嚇表情。

請建立表情映射表：

問句 / 迷思型封面 → thinking / curious / slightly puzzled
研究翻轉 / 發現型 → attentive
提醒型 → reminder
品牌收尾 → goodbye
慶祝型很少用，避免太幼態
三、scriptwriter 要從「寫稿」升級成「導演稿 + 視覺稿」

你現在 scriptwriter 的問題，不是內容不會寫，而是寫完之後太像報告，不像要交給設計與剪輯的拍板文件。

請把輸出 schema 升級成這樣：

{
  "episode_title": "",
  "core_claim": "",
  "single_takeaway": "",
  "audience_promise": "",
  "visual_style_token": "STYLE_SHIZHI_POSTER_REALISM_V1",
  "mascot_strategy": {
    "presence": "both",
    "opening_expression": "thinking",
    "closing_expression": "goodbye",
    "allow_middle_cards": false
  },
  "scenes": [
    {
      "scene_id": "01",
      "scene_role": "hook",
      "scene_goal": "",
      "on_screen_text_main": "",
      "on_screen_text_sub": "",
      "visual_type": "poster_cover",
      "hero_object": "",
      "photo_realism_ratio": 0.75,
      "vector_ratio": 0.25,
      "mascot_presence": true,
      "mascot_count": 1,
      "mascot_expression": "",
      "mascot_interaction_mode": "",
      "source_badge_text": "",
      "do_not_include": []
    }
  ]
}
必加欄位說明
core_claim

這支片真正要講的唯一核心。
例如雞蛋片：

「真正更該注意的是整體搭配中的飽和脂肪，不是只把雞蛋當成罪魁禍首。」

single_takeaway

觀眾離開前只要記住這一句。
例如：

「吃對搭配，比怕蛋更重要。」

scene_role

讓後面 agent 知道這張卡的角色：

hook
flip
compare
evidence
reminder
closing
visual_type

讓 asset_gen 不會每張都用同樣模板：

poster_cover
comparison_card
evidence_card
safety_reminder
brand_closing
四、researcher 的輸出要更貼近短影音設計，不只丟資料

你現在 researcher 有資料，但對設計端還不夠友善。
請多產出下面這些欄位：

{
  "cognitive_gap": "",
  "one_sentence_hook": "",
  "misbelief_to_correct": "",
  "safe_claim": "",
  "unsafe_claims_to_avoid": [],
  "visualizable_objects": [],
  "good_cover_objects": [],
  "comparison_objects": [],
  "audience_sensitivity_notes": []
}
以雞蛋主題為例
misbelief_to_correct

「一天只能吃一顆蛋」

safe_claim

「近年研究支持，影響 LDL 的因素更接近整體飲食中的飽和脂肪，而不是只看蛋的飲食膽固醇。」

unsafe_claims_to_avoid
「雞蛋怎麼吃都沒差」
「膽固醇完全不用管」
「吃蛋可以降膽固醇」
good_cover_objects
白殼雞蛋
水煮蛋
木桌早餐場景
清爽餐盤

這樣 scriptwriter 和 asset_gen 就不用自己猜。

五、asset_gen 要改成「先構圖規格，後生成」，不要直接亂出圖

這是最大改造重點。

你現在 asset_gen 很像「拿 prompt 就生圖」，但你真正要的是：

先決定版型，再去生成素材。

建議改成兩段式
A. Layout Planner

先輸出設計骨架：

{
  "canvas": "1080x1920",
  "layout_type": "poster_cover",
  "headline_zone": {
    "x": 80,
    "y": 120,
    "w": 920,
    "h": 420
  },
  "hero_object_zone": {
    "x": 140,
    "y": 620,
    "w": 700,
    "h": 700
  },
  "mascot_zone": {
    "x": 640,
    "y": 980,
    "w": 260,
    "h": 360
  },
  "footer_brand_zone": {
    "x": 0,
    "y": 1660,
    "w": 1080,
    "h": 260
  }
}
B. Visual Generator

再去生成：

寫實底圖
小靜透明素材
badge
footer strip
這樣的好處
可以避免文字壓到主體
可以避免小靜亂跑到角落
可以避免右下角再長一隻 mascot
可以讓每張卡保持統一的品牌秩序
六、請加入「封面卡專用規則」

這是你現在 90 分首頁最成功的地方，要寫死成模板。

Cover Card 規則
規則 1：只有一個主問題

例如：

一天只能吃一顆蛋？
白粥煮太爛，升糖指數飆高？
晚上散步，真的比早上好？
規則 2：主標一定超大

這個不是 subtitle card，是 poster cover。

規則 3：只放一個 hero object
雞蛋
白粥
咖啡杯
香蕉
不能同時放 4 樣東西。
規則 4：小靜只能是「情緒輔助」
問句 → 思考
提醒 → 提醒
片尾 → 打招呼
規則 5：視覺與語意一致

CDC 明確建議文字與視覺要互相強化，不要讓看圖與看字得到不同訊號。

七、Reviewer 要新增「美感與品牌一致性審查層」

你現在 reviewer 偏 schema 與醫療風險，這還不夠。
請新增一層 visual_brand_review。

新的 fail codes
[
  "MULTIPLE_MAIN_MESSAGES",
  "VISUAL_NOT_SUPPORTING_MESSAGE",
  "TOO_MANY_OBJECTS",
  "TEXT_HARD_TO_SCAN",
  "CHEAP_SOCIAL_POSTER_STYLE",
  "MASCOT_OVERUSED",
  "DUPLICATE_MASCOT",
  "MASCOT_STICKER_LIKE",
  "PHOTO_VECTOR_NOT_INTEGRATED",
  "OLDER_AUDIENCE_UNFRIENDLY",
  "HEADLINE_NOT_DOMINANT",
  "NO_CLEAR_HERO_OBJECT",
  "EMOTION_MISMATCH_WITH_HEADLINE"
]
Reviewer 的審核問題改成 Yes/No
主訊息
這張圖是否只有一個主訊息？
視覺是否支援該主訊息？
掃讀性
觀眾 1 秒內能否讀到主標？
觀眾 3 秒內能否理解這張在講什麼？
小靜
是否只有一隻？
是否沒有 badge / 貼紙 / 浮水印分身？
表情是否正確服務標題？
高齡友善
字是否夠大？
畫面是否過滿？
是否避免過度雜訊？

NN/g 對 older adults 的研究與一般 readability 原則都支持這種做法：層級清楚、資訊少、易掃描，比堆細節更重要。

八、Assembler 不只是拼接，要有「品牌節奏」

你現在 assembler 若只是 ffmpeg 串起來，作品還是會像資訊卡輪播。

請加上固定節奏：

節奏模板
0–3 秒：超大問句封面
3–8 秒：翻轉卡
8–15 秒：比較卡
15–23 秒：研究卡
23–29 秒：提醒卡
29–33 秒：品牌片尾卡
動畫規則
封面卡：慢速 push-in 或輕微漂移
中段卡：簡單 cut / slide，不要花俏轉場
研究卡：badge 淡入即可
片尾卡：小靜揮手或輕微點頭
禁止事項
不要鏡頭晃動
不要大量飛入字
不要抖音式轟炸轉場
不要每張卡都動一堆元素

這種節奏比較符合健康知識內容，也符合視覺介入能提升健康資訊理解的證據方向。2024 系統性回顧指出，視覺化、尤其是影片型健康材料，能有效提升健康理解，但前提是設計不是增加負擔，而是幫助理解。

九、建立「設計 token 與禁止 token」資料庫，讓 Claude Code 真正可維護

請不要把所有美感規則都塞在 prompt 裡。
應拆成設定檔。

brand_visual_tokens.json
{
  "headline_style": "large_poster_chinese",
  "layout_style": "single_hero_object",
  "background_style": "warm_realistic_lifestyle",
  "palette": {
    "cream": "#F6F1E7",
    "sage": "#A8B88A",
    "olive_dark": "#4E5538",
    "brown_text": "#3B2A1F"
  },
  "mascot_policy": {
    "default_presence": "opening_closing_only",
    "max_count_per_image": 1,
    "allow_logo_mascot": false,
    "allow_corner_mascot": false,
    "allow_footer_mascot": false
  }
}
negative_design_tokens.json
{
  "forbidden": [
    "duplicate mascot",
    "corner mascot",
    "badge mascot",
    "watermark mascot",
    "cheap social poster",
    "neon gradient",
    "medical fear warning",
    "too many food objects",
    "small unreadable text",
    "busy collage",
    "children worksheet style"
  ]
}



一、先把 3D 小靜從「提示詞參考」升級成「品牌角色規格」

你現在最危險的地方是：
雖然有一張滿意的 3D 小靜，但模型還是可能每次偷偷改：

臉型
眼睛比例
耳朵形狀
豹紋位置
圍裙綠色
材質從霧面塑膠變亮面公仔
光線從柔光變商品攝影硬光

所以第一件事不是繼續生圖，而是建立 mascot_3d_spec.json。

建議規格
{
  "character_name": "小靜",
  "species": "Taiwanese leopard cat mascot",
  "reference_image": "/mnt/data/3d_main_card.jpg",
  "identity_lock": {
    "same_face": true,
    "same_markings": true,
    "same_green_apron": true,
    "same_tail_shape": true,
    "same_ear_shape": true
  },
  "material_lock": {
    "material": "smooth matte plastic",
    "finish": "low gloss",
    "contrast": "low",
    "shadow": "very soft"
  },
  "lighting_lock": {
    "style": "studio softbox lighting",
    "background_mood": "muted pastel / morandi"
  },
  "pose_family": [
    "hug_object_side",
    "lean_on_object",
    "greet_viewer",
    "think_with_object"
  ]
}

這一步很重要，因為你不是在做一次性藝術創作，而是在做 角色一致性的品牌系統。

二、把 asset_gen 改成四段式，不要再一次出整張

這是穩定輸出的核心。

你現在如果還是「一句 prompt → 直接出封面」，穩定度一定差。
建議改成下面四段：

Stage 1：Layout Planner

先決定版型，不生成圖。

輸出例如：

{
  "layout_type": "poster_cover_3d_mascot",
  "headline_zone": {"x": 72, "y": 110, "w": 936, "h": 430},
  "badge_zone": {"x": 820, "y": 90, "w": 180, "h": 180},
  "hero_object_zone": {"x": 280, "y": 760, "w": 520, "h": 700},
  "mascot_zone": {"x": 180, "y": 950, "w": 260, "h": 360},
  "footer_zone": {"x": 0, "y": 1680, "w": 1080, "h": 240}
}
Stage 2：Background / Hero Object Generator

只生底圖與主物件。
例如雞蛋封面只生成：

木桌
暖室內背景
一顆大白蛋

禁止先把小靜一起生成。

Stage 3：3D Mascot Generator

只生一隻小靜透明素材，嚴格使用 /mnt/data/3d_main_card.jpg 當角色參考。

這一階段只允許輸出：

單角色
透明背景
指定 pose
指定 expression
Stage 4：Composer

最後才把：

背景
主物件
3D 小靜
標題
badge
品牌底條
組起來。

這樣做的好處是：

不會再冒出第二隻小靜
不會角色和字搶位
不會角色比例亂飛
不會每次風格飄走

這種「把視覺元素拆開再組合」的做法，也更符合 CDC 所說的「用視覺線索強調主訊息」：大小、位置、留白、對比都應該是刻意安排，而不是碰運氣。

三、scriptwriter 要新增「3D 封面控制欄位」

請不要再只寫一句 prompt。
改成結構化：

{
  "scene_id": "01",
  "scene_role": "hook_cover",
  "headline_main": "一天只能\n吃一顆蛋？",
  "headline_sub": "這句話，可能早就過時了",
  "badge_text": "2025\n研究更新",
  "visual_style_token": "STYLE_SHIZHI_3D_POSTER_V1",
  "hero_object": "one large realistic white egg",
  "hero_object_priority": "primary",
  "mascot_presence": true,
  "mascot_count": 1,
  "mascot_render_mode": "3d_exact_reference",
  "mascot_pose": "hug_object_side",
  "mascot_expression": "thinking_curious",
  "mascot_scale_vs_object": "small",
  "allow_extra_mascot": false,
  "allow_logo_mascot": false,
  "do_not_include": [
    "duplicate mascot",
    "bottom-right mascot",
    "extra decorative mascot",
    "multiple eggs",
    "busy background"
  ]
}

這樣 Claude Code 才能在 pipeline 裡真的控住，而不是只把需求藏在 prompt 裡。

四、建立「3D 小靜專用審查器」

reviewer 現在一定要多一層：

mascot_consistency_review

必查項
是否只有一隻小靜
是否與 reference image 為同一角色
是否維持同一材質感
是否維持同一圍裙 / 花紋 / 臉型
是否出現在正確區域
是否搶走主物件
表情是否與標題一致
新 fail codes
[
  "DUPLICATE_3D_MASCOT",
  "MASCOT_IDENTITY_DRIFT",
  "MASCOT_MATERIAL_DRIFT",
  "MASCOT_SCALE_TOO_LARGE",
  "MASCOT_NOT_SUPPORTING_MAIN_MESSAGE",
  "HEADLINE_EMOTION_MISMATCH",
  "HERO_OBJECT_NOT_DOMINANT",
  "PHOTO_3D_INTEGRATION_POOR"
]

這裡的核心邏輯其實和 CDC Clear Communication Index 一樣：
一個主訊息、視覺支援主訊息、重要資訊易辨識。

五、把封面與片尾做成固定模板

你現在已經知道 opener 與 closing 的最佳解：

Cover Template
上方超大問句標題
中下方一顆大主物件
一隻小靜與主物件互動
右上 badge
底部品牌底條可有可無
嚴禁第二隻小靜
Closing Template
上方大字收尾句
中下方乾淨生活背景
一隻小靜面向觀眾打招呼
「嗨，我是小靜」或「我是小靜，我們下次見」
不要任何 mascot logo / badge

請把這兩個模板做成：

cover_card_template_3d.json
closing_card_template_3d.json

以後每一支片只換：

主題物件
標題
表情
互動動作

其他都不要亂動。

六、給 Claude Code 的實作指令

你可以直接丟這段給它：

請把目前「時時靜好」圖卡型 Shorts workflow 升級為 3D 吉祥物穩定輸出系統。

目標：
- 封面品牌吉祥物小靜全面改為 3D 版
- 必須使用 /mnt/data/3d_main_card.jpg 作為 exact reference
- 不可重新設計角色
- 必須穩定維持同一角色身份、材質、燈光、色調、圍裙、豹紋與臉型

請修改以下模組：

1. researcher
新增欄位：
- good_cover_objects
- mascot_recommended_pose
- visual_risk_notes

2. scriptwriter
新增欄位：
- mascot_render_mode
- mascot_pose
- mascot_expression
- mascot_scale_vs_object
- allow_extra_mascot
- allow_logo_mascot

3. asset_gen
改成四段式：
- layout planner
- background/hero object generation
- 3D mascot generation with exact reference
- final composition

4. reviewer
新增 mascot_consistency_review
fail codes 至少包含：
- DUPLICATE_3D_MASCOT
- MASCOT_IDENTITY_DRIFT
- MASCOT_MATERIAL_DRIFT
- MASCOT_SCALE_TOO_LARGE
- HERO_OBJECT_NOT_DOMINANT

5. assembler
對圖卡型短影音使用固定節奏：
- 0–3 秒封面
- 3–8 秒翻轉
- 8–15 秒比較
- 15–23 秒研究
- 23–29 秒提醒
- 29–33 秒片尾

請新增設定檔：
- mascot_3d_spec.json
- brand_visual_tokens_3d.json
- cover_card_template_3d.json
- closing_card_template_3d.json
- negative_design_tokens_3d.json

第一個 regression test 請用雞蛋與膽固醇主題。