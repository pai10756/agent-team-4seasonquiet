"""
品質審查腳本 — reviewer agent 使用。

v3: 三層審查 — 鎖死層 + 視覺品牌層 + 護欄層。
鎖死層和視覺品牌層由程式化檢查，護欄層由 reviewer agent (LLM) 補充。
支援 v3 episode schema（scenes[], mascot_strategy, core_claim 等）。

用法:
  python scripts/review_episode.py <episode.json> [--attempt N]

輸出: review_result JSON（stdout），同時存檔到 episode 同目錄。
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from validate_schema import validate_episode


def _sub_text(sub) -> str:
    """Get subtitle text whether sub is a dict or plain string."""
    if isinstance(sub, str):
        return sub
    return sub.get("text", "") if isinstance(sub, dict) else ""


# ── 鎖死層檢查器 ────────────────────────────────────────

def check_schema_incomplete(ep: dict) -> list[dict]:
    """SCHEMA_INCOMPLETE: episode.schema.json 必填欄位是否完整。"""
    errors = validate_episode(ep)
    if not errors:
        return []
    return [{
        "code": "SCHEMA_INCOMPLETE",
        "severity": "error",
        "message": f"Schema 驗證失敗: {len(errors)} 個錯誤",
        "field_path": errors[0].split("]")[0].strip("[") if errors else "(root)",
        "fix_hint": "; ".join(errors[:3]) + ("..." if len(errors) > 3 else ""),
        "auto_fixable": True,
    }]


def check_subtitle_language(ep: dict) -> list[dict]:
    """SUBTITLE_NOT_ZHTW: 字幕是否為繁體中文。"""
    violations = []
    for i, sub in enumerate(ep.get("subtitles", [])):
        text = _sub_text(sub)
        # 簡體中文特徵字檢測
        simplified_chars = set("的这个为与对于关进发动长门时会从见说读请问车东风对开际产党区员")
        found = [c for c in text if c in simplified_chars]
        if len(found) >= 2:
            violations.append({
                "code": "SUBTITLE_NOT_ZHTW",
                "severity": "error",
                "message": f"字幕[{i}]疑似含簡體中文: '{text}'",
                "field_path": f"subtitles[{i}].text",
                "fix_hint": "請將字幕轉為繁體中文",
                "auto_fixable": True,
            })
    return violations


def check_prompt_language(ep: dict) -> list[dict]:
    """PROMPT_NOT_ZHCN: Seedance prompt / scene_image prompt 是否為簡體中文。"""
    violations = []
    # 繁體中文特徵字
    traditional_chars = set("個這為與對於關進發動長門時會從見說讀請問車東風對開際產黨區員裡頭過點麼後學國幾機應變體頭環認識達隨選擇號義歲練習聯網節觀類農辦劃數據轉調")

    for i, scene in enumerate(ep.get("scene_images", [])):
        prompt = scene.get("prompt", "")
        found_trad = [c for c in prompt if c in traditional_chars]
        if len(found_trad) >= 3:
            violations.append({
                "code": "PROMPT_NOT_ZHCN",
                "severity": "error",
                "message": f"scene_images[{i}].prompt 疑似含繁體中文（應為簡體）: 發現 {len(found_trad)} 個繁體字",
                "field_path": f"scene_images[{i}].prompt",
                "fix_hint": "場景圖 prompt 請使用簡體中文（Seedance 平台限制）",
                "auto_fixable": True,
            })

    for key in ("seedance_part1", "seedance_part2"):
        prompt = (ep.get("seedance_prompts") or {}).get(key, "")
        if not prompt:
            continue
        found_trad = [c for c in prompt if c in traditional_chars]
        if len(found_trad) >= 3:
            violations.append({
                "code": "PROMPT_NOT_ZHCN",
                "severity": "error",
                "message": f"seedance_prompts.{key} 疑似含繁體中文: 發現 {len(found_trad)} 個繁體字",
                "field_path": f"seedance_prompts.{key}",
                "fix_hint": "Seedance prompt 請使用簡體中文",
                "auto_fixable": True,
            })

    return violations


def check_subtitle_length(ep: dict) -> list[dict]:
    """SUBTITLE_TOO_LONG / SUBTITLE_TOO_SHORT: 每句 6-12 字（最多 15）。"""
    violations = []
    for i, sub in enumerate(ep.get("subtitles", [])):
        text = _sub_text(sub)
        length = len(text)
        if length > 15:
            violations.append({
                "code": "SUBTITLE_TOO_LONG",
                "severity": "error",
                "message": f"字幕[{i}] '{text}' 共 {length} 字，超過 15 字上限",
                "field_path": f"subtitles[{i}].text",
                "fix_hint": f"請拆成兩句，每句 6-12 字",
                "auto_fixable": True,
            })
        elif length < 2:
            violations.append({
                "code": "SUBTITLE_TOO_SHORT",
                "severity": "error",
                "message": f"字幕[{i}] '{text}' 只有 {length} 字，低於 2 字下限",
                "field_path": f"subtitles[{i}].text",
                "fix_hint": "字幕過短，請合併或補充",
                "auto_fixable": True,
            })
    return violations


def check_brand_closing(ep: dict) -> list[dict]:
    """MISSING_BRAND_CLOSING: 結尾是否提到「時時靜好」+ 告別語。"""
    subtitles = ep.get("subtitles", [])
    if not subtitles:
        return [{
            "code": "MISSING_BRAND_CLOSING",
            "severity": "error",
            "message": "無字幕，無法檢查結尾品牌",
            "field_path": "subtitles",
            "fix_hint": "請加入字幕，結尾需提到「時時靜好」",
            "auto_fixable": True,
        }]

    last_few = " ".join(_sub_text(s) for s in subtitles[-3:])
    if "時時靜好" not in last_few:
        return [{
            "code": "MISSING_BRAND_CLOSING",
            "severity": "error",
            "message": f"最後 3 句字幕未包含「時時靜好」: '{last_few}'",
            "field_path": f"subtitles[{len(subtitles)-1}].text",
            "fix_hint": "結尾字幕需包含「時時靜好」+ 告別語（如「我們下次見」）",
            "auto_fixable": True,
        }]
    return []


def check_data_source(ep: dict) -> list[dict]:
    """MISSING_DATA_SOURCE: 營養數據是否附 USDA/衛福部來源。"""
    sources = ep.get("research_sources", [])
    if not sources:
        return [{
            "code": "MISSING_DATA_SOURCE",
            "severity": "error",
            "message": "research_sources 為空，營養數據必須附來源",
            "field_path": "research_sources",
            "fix_hint": "至少提供一個 USDA/PubMed/衛福部來源（含 citation 和 key_finding）",
            "auto_fixable": False,
        }]
    return []


def check_medical_claim(ep: dict) -> list[dict]:
    """MEDICAL_CLAIM: 是否有「超級食物」或療效宣稱。"""
    forbidden_patterns = [
        r"超級食物", r"超级食物",
        r"治[療癒]", r"治[疗愈]",
        r"根治", r"特效藥", r"特效药",
        r"保證.*治", r"保证.*治",
        r"一定[能可]治",
    ]

    violations = []
    texts_to_check = []

    for i, sub in enumerate(ep.get("subtitles", [])):
        texts_to_check.append((f"subtitles[{i}].text", _sub_text(sub)))

    hvs = ep.get("hook_variants", [])
    if isinstance(hvs, dict):
        for k, v in hvs.items():
            texts_to_check.append((f"hook_variants.{k}", v if isinstance(v, str) else str(v)))
    elif isinstance(hvs, list):
        for i, hv in enumerate(hvs):
            txt = hv.get("text", "") if isinstance(hv, dict) else (hv if isinstance(hv, str) else "")
            texts_to_check.append((f"hook_variants[{i}]", txt))

    texts_to_check.append(("hook_text", ep.get("hook_text", "")))

    yt_desc = (ep.get("youtube_metadata") or {}).get("description", "")
    texts_to_check.append(("youtube_metadata.description", yt_desc))

    for field_path, text in texts_to_check:
        for pattern in forbidden_patterns:
            if re.search(pattern, text):
                violations.append({
                    "code": "MEDICAL_CLAIM",
                    "severity": "error",
                    "message": f"發現療效宣稱 '{pattern}' 於 {field_path}: '{text[:30]}'",
                    "field_path": field_path,
                    "fix_hint": "不說「超級食物」、不做療效宣稱，改用「研究顯示」「可能有助於」等措辭",
                    "auto_fixable": True,
                })
                break

    return violations


def check_duration(ep: dict) -> list[dict]:
    """DURATION_OUT_OF_RANGE: 總時長是否 ~33 秒（±3 秒）。"""
    subtitles = ep.get("subtitles", [])
    if not subtitles:
        return []

    max_end = max((s.get("end", 0) if isinstance(s, dict) else 0 for s in subtitles), default=0)
    if max_end == 0:
        return []  # subtitles lack timing info, skip duration check
    if max_end < 27 or max_end > 39:
        return [{
            "code": "DURATION_OUT_OF_RANGE",
            "severity": "error",
            "message": f"推算總時長 {max_end:.1f}s，應在 30-36s（目標 ~33s）",
            "field_path": "subtitles",
            "fix_hint": f"目前最後字幕結束於 {max_end:.1f}s，請調整為約 33 秒（3s 片頭 + 15s + 15s）",
            "auto_fixable": True,
        }]
    return []


def check_hook_variants(ep: dict) -> list[dict]:
    """HOOK_VARIANTS_INSUFFICIENT: hook_variants 是否 >= 3 個。"""
    variants = ep.get("hook_variants", [])
    if len(variants) < 3:
        return [{
            "code": "HOOK_VARIANTS_INSUFFICIENT",
            "severity": "error",
            "message": f"hook_variants 只有 {len(variants)} 個，需要至少 3 個",
            "field_path": "hook_variants",
            "fix_hint": "請產出 3-5 個 hook 變體，按認知層級分類（unaware/problem_aware/solution_aware/audience）",
            "auto_fixable": True,
        }]
    return []


def check_scene_image_prohibition(ep: dict) -> list[dict]:
    """SCENE_IMAGE_MISSING_PROHIBITION: prompt 結尾是否含「不要任何文字」類禁止語。"""
    prohibition_patterns = [
        r"不要.*文字", r"不要.*水印", r"不要.*LOGO",
        r"没有.*文字", r"無.*文字",
        r"禁止.*文字",
    ]
    violations = []
    for i, scene in enumerate(ep.get("scene_images", [])):
        prompt = scene.get("prompt", "")
        has_prohibition = any(re.search(p, prompt) for p in prohibition_patterns)
        if not has_prohibition:
            violations.append({
                "code": "SCENE_IMAGE_MISSING_PROHIBITION",
                "severity": "error",
                "message": f"scene_images[{i}].prompt 結尾缺少禁止語",
                "field_path": f"scene_images[{i}].prompt",
                "fix_hint": "prompt 結尾請加「不要任何文字、人物、水印、LOGO」",
                "auto_fixable": True,
            })
    return violations


def check_hook_text_length(ep: dict) -> list[dict]:
    """HOOK_TEXT_LENGTH: hook_text 是否在 6-10 字。"""
    ht = ep.get("hook_text", "")
    if len(ht) > 10:
        return [{
            "code": "HOOK_TEXT_LENGTH",
            "severity": "error",
            "message": f"hook_text '{ht}' 共 {len(ht)} 字，超過 10 字上限",
            "field_path": "hook_text",
            "fix_hint": f"請精簡 hook_text 至 6-10 字（目前 {len(ht)} 字）",
            "auto_fixable": True,
        }]
    if len(ht) < 6:
        return [{
            "code": "HOOK_TEXT_LENGTH",
            "severity": "error",
            "message": f"hook_text '{ht}' 只有 {len(ht)} 字，低於 6 字下限",
            "field_path": "hook_text",
            "fix_hint": f"請擴充 hook_text 至 6-10 字（目前 {len(ht)} 字）",
            "auto_fixable": True,
        }]
    return []


def check_type_rationale(ep: dict) -> list[dict]:
    """TYPE_RATIONALE_MISSING: type_rationale 是否足夠具體。"""
    rationale = ep.get("type_rationale", "")
    if len(rationale) < 10:
        return [{
            "code": "TYPE_RATIONALE_MISSING",
            "severity": "error",
            "message": f"type_rationale 過短（{len(rationale)} 字），需要至少 10 字說明選型理由",
            "field_path": "type_rationale",
            "fix_hint": "請說明為什麼選擇此型態（數據密度、情緒轉折、成本等）",
            "auto_fixable": True,
        }]
    return []


def check_core_claim(ep: dict) -> list[dict]:
    """MISSING_CORE_CLAIM: v3 必填 core_claim。"""
    claim = ep.get("core_claim", "")
    if len(claim) < 10:
        return [{
            "code": "MISSING_CORE_CLAIM",
            "severity": "error",
            "message": f"core_claim 缺失或過短（{len(claim)} 字），需要至少 10 字",
            "field_path": "core_claim",
            "fix_hint": "請填寫這支片真正要講的唯一核心（≥10 字）",
            "auto_fixable": True,
        }]
    return []


def check_single_takeaway(ep: dict) -> list[dict]:
    """MISSING_SINGLE_TAKEAWAY: v3 必填 single_takeaway。"""
    takeaway = ep.get("single_takeaway", "")
    if len(takeaway) < 5:
        return [{
            "code": "MISSING_SINGLE_TAKEAWAY",
            "severity": "error",
            "message": f"single_takeaway 缺失或過短（{len(takeaway)} 字），需要至少 5 字",
            "field_path": "single_takeaway",
            "fix_hint": "請填寫觀眾離開前只要記住的一句話（≥5 字）",
            "auto_fixable": True,
        }]
    return []


# ── 鎖死層總檢 ──────────────────────────────────────────

ALL_LOCK_CHECKS = [
    check_schema_incomplete,
    check_subtitle_language,
    check_prompt_language,
    check_subtitle_length,
    check_brand_closing,
    check_data_source,
    check_medical_claim,
    check_duration,
    check_hook_variants,
    check_scene_image_prohibition,
    check_type_rationale,
    check_hook_text_length,
    check_core_claim,
    check_single_takeaway,
]


def run_lock_layer(ep: dict) -> tuple[bool, list[dict]]:
    """執行所有鎖死層檢查，回傳 (passed, violations)。"""
    all_violations = []
    for check_fn in ALL_LOCK_CHECKS:
        all_violations.extend(check_fn(ep))
    passed = len(all_violations) == 0
    return passed, all_violations


# ── 視覺品牌層檢查器（v3 新增） ─────────────────────────

# Load character expression_headline_map for validation
_CHARACTER_PATH = BASE / "characters" / "mascot" / "character.json"
_EXPRESSION_MAP = {}
if _CHARACTER_PATH.exists():
    _char = json.loads(_CHARACTER_PATH.read_text(encoding="utf-8"))
    _EXPRESSION_MAP = _char.get("expression_headline_map", {})
    _VALID_EXPRESSIONS = [k for k in _char.get("expressions", {}).keys() if not k.startswith("_")]
else:
    _VALID_EXPRESSIONS = ["default", "surprised", "thinking", "happy", "reminder", "goodbye", "worried", "proud"]


def check_mascot_overused(ep: dict) -> list[dict]:
    """MASCOT_OVERUSED: 小靜出現在超過 2 張卡（開場+結尾）。"""
    scenes = ep.get("scenes", [])
    if not scenes:
        return []
    mascot_scenes = [s for s in scenes if s.get("mascot_presence")]
    if len(mascot_scenes) > 2:
        ids = [s.get("scene_id", "?") for s in mascot_scenes]
        return [{
            "code": "MASCOT_OVERUSED",
            "severity": "error",
            "message": f"小靜出現在 {len(mascot_scenes)} 張卡 ({', '.join(ids)})，最多允許 2 張（開場+結尾）",
            "field_path": "scenes",
            "fix_hint": "將中間卡的 mascot_presence 設為 false，小靜只出現在開場和結尾卡",
            "auto_fixable": True,
        }]
    return []


def check_duplicate_mascot(ep: dict) -> list[dict]:
    """DUPLICATE_MASCOT / DUPLICATE_3D_MASCOT: 單張卡不能有多隻小靜。"""
    scenes = ep.get("scenes", [])
    violations = []
    for s in scenes:
        count = s.get("mascot_count", 1 if s.get("mascot_presence") else 0)
        if count > 1:
            violations.append({
                "code": "DUPLICATE_3D_MASCOT",
                "severity": "error",
                "message": f"場景 {s.get('scene_id', '?')} mascot_count={count}，每張卡最多 1 隻",
                "field_path": f"scenes[{s.get('scene_id', '?')}].mascot_count",
                "fix_hint": "設定 mascot_count 為 0 或 1",
                "auto_fixable": True,
            })
    return violations


def check_mascot_middle_cards(ep: dict) -> list[dict]:
    """小靜不應出現在中間卡（除非 mascot_strategy.allow_middle_cards=true）。"""
    strategy = ep.get("mascot_strategy", {})
    if strategy.get("allow_middle_cards"):
        return []
    scenes = ep.get("scenes", [])
    violations = []
    for s in scenes:
        if not s.get("mascot_presence"):
            continue
        role = s.get("scene_role", "")
        if role not in ("hook", "closing"):
            violations.append({
                "code": "MASCOT_OVERUSED",
                "severity": "error",
                "message": f"場景 {s.get('scene_id', '?')} (role={role}) 有小靜，中間卡預設禁止",
                "field_path": f"scenes[{s.get('scene_id', '?')}].mascot_presence",
                "fix_hint": "將此卡的 mascot_presence 設為 false",
                "auto_fixable": True,
            })
    return violations


def check_emotion_mismatch(ep: dict) -> list[dict]:
    """EMOTION_MISMATCH_WITH_HEADLINE: 開場表情是否與 hook 情緒匹配。"""
    if not _EXPRESSION_MAP:
        return []
    strategy = ep.get("mascot_strategy", {})
    opening_expr = strategy.get("opening_expression", "")
    if not opening_expr:
        return []

    # Flatten allowed expressions from map
    all_allowed = set()
    for exprs in _EXPRESSION_MAP.values():
        all_allowed.update(exprs)

    if opening_expr not in all_allowed and opening_expr not in _VALID_EXPRESSIONS:
        return [{
            "code": "EMOTION_MISMATCH_WITH_HEADLINE",
            "severity": "error",
            "message": f"opening_expression '{opening_expr}' 不是有效的表情",
            "field_path": "mascot_strategy.opening_expression",
            "fix_hint": f"請從有效表情中選擇: {_VALID_EXPRESSIONS}",
            "auto_fixable": True,
        }]
    return []


def check_hero_object_missing(ep: dict) -> list[dict]:
    """NO_CLEAR_HERO_OBJECT: poster_cover 卡是否有 hero_object。"""
    scenes = ep.get("scenes", [])
    violations = []
    for s in scenes:
        if s.get("visual_type") == "poster_cover" and not s.get("hero_object"):
            violations.append({
                "code": "NO_CLEAR_HERO_OBJECT",
                "severity": "error",
                "message": f"場景 {s.get('scene_id', '?')} (poster_cover) 缺少 hero_object",
                "field_path": f"scenes[{s.get('scene_id', '?')}].hero_object",
                "fix_hint": "poster_cover 卡必須有 hero_object（主視覺物件），如 'one large realistic white egg'",
                "auto_fixable": False,
            })
    return violations


def check_headline_missing(ep: dict) -> list[dict]:
    """HEADLINE_NOT_DOMINANT: 場景卡是否有主標題文字。"""
    scenes = ep.get("scenes", [])
    violations = []
    for s in scenes:
        vt = s.get("visual_type", "")
        if vt in ("poster_cover", "comparison_card", "evidence_card", "safety_reminder"):
            if not s.get("on_screen_text_main"):
                violations.append({
                    "code": "HEADLINE_NOT_DOMINANT",
                    "severity": "error",
                    "message": f"場景 {s.get('scene_id', '?')} ({vt}) 缺少 on_screen_text_main",
                    "field_path": f"scenes[{s.get('scene_id', '?')}].on_screen_text_main",
                    "fix_hint": "此類型卡片需要主標題文字（繁體中文）",
                    "auto_fixable": True,
                })
    return violations


def check_mascot_strategy_presence(ep: dict) -> list[dict]:
    """檢查 mascot_strategy 與 scenes 的 mascot_presence 是否一致。"""
    strategy = ep.get("mascot_strategy", {})
    presence = strategy.get("presence", "both")
    scenes = ep.get("scenes", [])
    if not scenes:
        return []

    violations = []
    has_opening_mascot = any(
        s.get("mascot_presence") and s.get("scene_role") == "hook" for s in scenes
    )
    has_closing_mascot = any(
        s.get("mascot_presence") and s.get("scene_role") == "closing" for s in scenes
    )

    if presence == "both":
        if not has_opening_mascot:
            violations.append({
                "code": "MASCOT_NOT_SUPPORTING_MAIN_MESSAGE",
                "severity": "warning",
                "message": "mascot_strategy.presence=both 但 hook 卡沒有設 mascot_presence=true",
                "field_path": "scenes",
                "fix_hint": "在 hook 卡加上 mascot_presence: true",
                "auto_fixable": True,
            })
        if not has_closing_mascot:
            violations.append({
                "code": "MASCOT_NOT_SUPPORTING_MAIN_MESSAGE",
                "severity": "warning",
                "message": "mascot_strategy.presence=both 但 closing 卡沒有設 mascot_presence=true",
                "field_path": "scenes",
                "fix_hint": "在 closing 卡加上 mascot_presence: true",
                "auto_fixable": True,
            })
    return violations


def build_visual_checklist(ep: dict) -> dict:
    """產生 visual_checklist（Yes/No 快速問題），供 reviewer LLM 後續確認。"""
    scenes = ep.get("scenes", [])
    mascot_scenes = [s for s in scenes if s.get("mascot_presence")]
    hook_scene = next((s for s in scenes if s.get("scene_role") == "hook"), None)

    return {
        "single_main_message": all(
            bool(s.get("on_screen_text_main")) for s in scenes
            if s.get("visual_type") not in ("brand_closing",)
        ),
        "visual_supports_message": bool(hook_scene and hook_scene.get("hero_object")),
        "headline_readable_1s": bool(hook_scene and hook_scene.get("on_screen_text_main")),
        "understandable_3s": bool(ep.get("hook_text")),
        "mascot_single": all(s.get("mascot_count", 1) <= 1 for s in mascot_scenes),
        "mascot_no_badge": not ep.get("mascot_strategy", {}).get("allow_logo_mascot", False),
        "mascot_emotion_correct": True,  # Detailed check by LLM
        "text_large_enough": True,  # Can only verify at render time
        "not_too_busy": len(scenes) <= 8,
        "no_excess_noise": True,  # Detailed check by LLM
    }


def check_negative_visual_markers(ep: dict) -> list[dict]:
    """NEGATIVE_VISUAL_MARKER: hero_object 不可包含否定視覺標記（X、叉、禁止符號等）。
    觀眾會誤解為「這個不能吃」，違反正面框架品牌原則。"""
    negative_patterns = [
        r"\bred['\s]*['\s]*X\b", r"\bcross\b", r"\bslash\b",
        r"\bban\b", r"\bprohibit", r"\bforbid",
        r"\bred mark\b", r"\bred circle\b", r"\bstrike",
        r"打叉", r"紅叉", r"禁止", r"劃掉",
        r"'X'", r'"X"', r"❌", r"✗", r"✘",
    ]
    violations = []
    for scene in ep.get("scenes", []):
        hero = scene.get("hero_object", "")
        for pat in negative_patterns:
            if re.search(pat, hero, re.IGNORECASE):
                violations.append({
                    "code": "NEGATIVE_VISUAL_MARKER",
                    "severity": "error",
                    "message": f"scene {scene.get('scene_id', '?')}: hero_object 含否定標記 '{pat}'，觀眾會誤解為不能吃",
                    "field_path": f"scenes[{scene.get('scene_id', '?')}].hero_object",
                    "fix_hint": "移除 X/叉/禁止符號，改用並排對比、數據差異或箭頭指向等正面視覺方式",
                    "auto_fixable": True,
                })
                break  # one violation per scene is enough
    return violations


ALL_VISUAL_CHECKS = [
    check_mascot_overused,
    check_duplicate_mascot,
    check_mascot_middle_cards,
    check_emotion_mismatch,
    check_hero_object_missing,
    check_headline_missing,
    check_mascot_strategy_presence,
    check_negative_visual_markers,
]


def run_visual_brand_layer(ep: dict) -> tuple[bool, list[dict], dict]:
    """執行所有視覺品牌層檢查，回傳 (passed, violations, checklist)。"""
    all_violations = []
    for check_fn in ALL_VISUAL_CHECKS:
        all_violations.extend(check_fn(ep))
    # Only errors cause failure, warnings don't
    has_errors = any(v.get("severity") == "error" for v in all_violations)
    passed = not has_errors
    checklist = build_visual_checklist(ep)
    return passed, all_violations, checklist


# ── 護欄層（由 LLM 補充，這裡只提供空結構） ───────────────

def run_guardrail_layer_stub() -> list[dict]:
    """護欄層佔位 — 實際由 reviewer agent (LLM) 分析後填入。"""
    return []


# ── 組裝 review_result ──────────────────────────────────

def build_review_result(ep: dict, attempt: int = 1) -> dict:
    """
    執行完整審查，產出符合 review_result.schema.json v3 的結果。

    鎖死層：程式化檢查。
    視覺品牌層：程式化檢查 + checklist（LLM 可後續補充判斷）。
    護欄層：回傳空結構，由 reviewer agent 的 LLM 補充。
    """
    lock_passed, lock_violations = run_lock_layer(ep)
    visual_passed, visual_violations, visual_checklist = run_visual_brand_layer(ep)
    guardrail_notes = run_guardrail_layer_stub()

    all_violations = lock_violations + visual_violations
    auto_fixable_codes = [v["code"] for v in all_violations if v.get("auto_fixable")]
    needs_human_codes = [v["code"] for v in all_violations if not v.get("auto_fixable")]

    if lock_passed and visual_passed:
        verdict = "pass"
        summary = "所有鎖死層和視覺品牌層檢查通過。"
    else:
        verdict = "fail"
        failed_codes = set(v["code"] for v in all_violations if v.get("severity") == "error")
        parts = []
        if not lock_passed:
            parts.append(f"鎖死層 {len(lock_violations)} 個違規")
        if not visual_passed:
            parts.append(f"視覺品牌層 {len(visual_violations)} 個違規")
        summary = f"{'; '.join(parts)}: {', '.join(failed_codes)}"

    return {
        "verdict": verdict,
        "attempt": attempt,
        "lock_layer": {
            "passed": lock_passed,
            "violations": lock_violations,
        },
        "visual_brand_layer": {
            "passed": visual_passed,
            "violations": visual_violations,
            "checklist": visual_checklist,
        },
        "guardrail_layer": {
            "notes": guardrail_notes,
        },
        "summary": summary,
        "auto_fixable": auto_fixable_codes,
        "needs_human": needs_human_codes,
    }


# ── CLI ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/review_episode.py <episode.json> [--attempt N]")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.is_absolute():
        json_path = Path.cwd() / json_path

    attempt = 1
    if "--attempt" in sys.argv:
        idx = sys.argv.index("--attempt")
        if idx + 1 < len(sys.argv):
            attempt = int(sys.argv[idx + 1])

    if not json_path.exists():
        print(f"找不到: {json_path}")
        sys.exit(1)

    ep = json.loads(json_path.read_text(encoding="utf-8"))
    result = build_review_result(ep, attempt)

    # 輸出到 stdout
    output = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")

    # 同時存檔
    out_path = json_path.parent / f"{json_path.stem}_review.json"
    out_path.write_text(output, encoding="utf-8")
    print(f"\n審查結果已存: {out_path}", file=sys.stderr)

    sys.exit(0 if result["verdict"] != "fail" else 1)


if __name__ == "__main__":
    main()
