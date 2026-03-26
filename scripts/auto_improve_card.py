"""
Auto-Improve Card — 自主迭代圖卡生成管線。

靈感來自 Karpathy/autoresearch：
  agent 修改 prompt → 生成圖卡 → 評分 → keep/discard → 重複

Usage:
  python scripts/auto_improve_card.py <episode.json> --scene 01 [--rounds 5] [--output-dir <dir>]
  python scripts/auto_improve_card.py <episode.json> --all [--rounds 3] [--output-dir <dir>]

環境變數:
  GEMINI_API_KEY — Gemini API key
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

from generate_card import build_prompt_for_scene, call_gemini, log as gen_log
from evaluate_card import evaluate_card, get_scene_context, WEIGHTS


def log(msg: str):
    print(f"[auto] {msg}", file=sys.stderr)


EVAL_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

REFINE_PROMPT_TEMPLATE = """你是一位圖卡生成 prompt 工程師。根據評審回饋，修改以下 Gemini 圖卡生成 prompt，使生成的圖卡獲得更高分。

## 評審回饋
{eval_json}

## 原始 Prompt
{original_prompt}

## 修改規則
1. 只修改 prompt 文字，不要改變 JSON 結構
2. 針對扣分最多的維度做重點修改
3. 保留品牌規範（色盤、安全區、中文要求）不可刪除
4. 修改要具體，不要模糊的描述
5. 如果 safe_zone 扣分，把元素位置描述改得更明確
6. 如果 text_quality 扣分（英文出現），加強「所有文字必須繁體中文」的指示
7. 如果 visual_realism 扣分，加強攝影參數或材質描述
8. 如果 no_artifacts 扣分，加強禁止項目

請直接回傳修改後的完整 prompt 文字（純文字，不要 JSON wrapper）。"""


def call_gemini_text_for_refine(prompt: str) -> str | None:
    """Call Gemini to refine a prompt based on evaluation feedback."""
    import base64
    import urllib.request
    import urllib.error

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{EVAL_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }).encode()

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return text.strip() if text else None
    except Exception as e:
        log(f"  Refine API error: {e}")
        return None


def run_experiment(episode_path: Path, scene_id: str, output_dir: Path,
                   max_rounds: int = 5) -> dict:
    """Run the autoresearch-style loop for one scene card."""
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    scene = None
    for s in episode.get("scenes", []):
        if s.get("scene_id") == scene_id:
            scene = s
            break
    if not scene:
        log(f"Scene {scene_id} not found")
        return {}

    scene_ctx = json.dumps(scene, ensure_ascii=False, indent=2)
    output_dir.mkdir(parents=True, exist_ok=True)

    # TSV log (like autoresearch's results.tsv)
    tsv_path = output_dir / "experiments.tsv"
    if not tsv_path.exists():
        tsv_path.write_text(
            "round\tcard_type\tscore\tgrade\tstatus\ttop_issue\n",
            encoding="utf-8"
        )

    best_score = 0.0
    best_path = None
    best_round = 0
    current_prompt_override = None  # None = use default prompt builder

    for round_num in range(1, max_rounds + 1):
        log(f"=== Scene {scene_id} Round {round_num}/{max_rounds} ===")

        # Step 1: Generate card
        log("  Generating card...")
        parts = build_prompt_for_scene(episode, scene, prompt_override=current_prompt_override)
        if not parts:
            log("  ERROR: Failed to build prompt")
            break

        img_bytes = call_gemini(parts)
        if not img_bytes:
            log("  ERROR: Generation failed")
            # Log crash
            with open(tsv_path, "a", encoding="utf-8") as f:
                f.write(f"{round_num}\t{scene.get('visual_type','')}\t0.0\tD\tcrash\tGeneration failed\n")
            time.sleep(2)
            continue

        # Save candidate
        candidate_path = output_dir / f"card{scene_id}_r{round_num:02d}.png"
        candidate_path.write_bytes(img_bytes)
        log(f"  Saved: {candidate_path.name}")

        # Step 2: Evaluate
        log("  Evaluating...")
        time.sleep(1)  # Rate limit
        result = evaluate_card(candidate_path, scene_ctx)
        if not result:
            log("  ERROR: Evaluation failed")
            with open(tsv_path, "a", encoding="utf-8") as f:
                f.write(f"{round_num}\t{scene.get('visual_type','')}\t0.0\tD\tcrash\tEvaluation failed\n")
            continue

        score = result["weighted_score"]
        grade = result["grade"]
        top_issue = result.get("top_issue", "").replace("\t", " ").replace("\n", " ")

        # Step 3: Keep or discard
        if score > best_score:
            status = "keep"
            best_score = score
            best_round = round_num
            best_path = candidate_path
            # Copy as current best
            best_copy = output_dir / f"card{scene_id}_best.png"
            shutil.copy2(candidate_path, best_copy)
            log(f"  KEEP: {score}/100 (Grade {grade}) > previous best {best_score if round_num > 1 else 0}")
        else:
            status = "discard"
            log(f"  DISCARD: {score}/100 (Grade {grade}) <= best {best_score}")

        # Log to TSV
        with open(tsv_path, "a", encoding="utf-8") as f:
            f.write(f"{round_num}\t{scene.get('visual_type','')}\t{score}\t{grade}\t{status}\t{top_issue}\n")

        # Step 4: If score >= 95, stop early (S grade, good enough)
        if score >= 95:
            log(f"  Score >= 95, stopping early!")
            break

        # Step 5: Refine prompt based on feedback (for next round)
        if round_num < max_rounds:
            log("  Refining prompt based on feedback...")
            # Get the text prompt from the parts
            original_text = ""
            for p in parts:
                if "text" in p:
                    original_text = p["text"]
                    break

            eval_summary = json.dumps({
                "scores": result["scores"],
                "remarks": result["remarks"],
                "top_issue": result.get("top_issue", ""),
                "prompt_suggestion": result.get("prompt_suggestion", ""),
            }, ensure_ascii=False, indent=2)

            refine_input = REFINE_PROMPT_TEMPLATE.format(
                eval_json=eval_summary,
                original_prompt=original_text[:3000],  # Truncate if too long
            )
            refined = call_gemini_text_for_refine(refine_input)
            if refined and len(refined) > 100:
                current_prompt_override = refined
                log(f"  Prompt refined ({len(refined)} chars)")
            else:
                log("  Prompt refinement failed, keeping current prompt")

            time.sleep(2)  # Rate limit between rounds

    # Summary
    log(f"\n=== Scene {scene_id} Complete ===")
    log(f"  Best: Round {best_round}, Score {best_score}/100")
    if best_path:
        log(f"  Best card: {best_path.name}")
        # Copy best as final
        final_path = output_dir / f"card{scene_id}.png"
        shutil.copy2(best_path, final_path)
        log(f"  Final: {final_path.name}")

    return {
        "scene_id": scene_id,
        "best_round": best_round,
        "best_score": best_score,
        "total_rounds": min(round_num, max_rounds),
        "best_path": str(best_path) if best_path else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Auto-improve card generation")
    parser.add_argument("episode", help="Episode JSON path")
    parser.add_argument("--scene", help="Scene ID (e.g. 01)")
    parser.add_argument("--all", action="store_true", help="Run all scenes")
    parser.add_argument("--rounds", type=int, default=5, help="Max rounds per scene (default: 5)")
    parser.add_argument("--output-dir", help="Output directory")
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        log("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    episode_path = Path(args.episode)
    if not episode_path.exists():
        log(f"ERROR: {episode_path} not found")
        sys.exit(1)

    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    ep_num = episode.get("episode", "xx")

    output_dir = Path(args.output_dir) if args.output_dir else (
        BASE / "test_output" / f"auto_improve_ep{ep_num}"
    )

    if args.all:
        scenes = [s["scene_id"] for s in episode.get("scenes", [])]
    elif args.scene:
        scenes = [args.scene]
    else:
        log("ERROR: specify --scene or --all")
        sys.exit(1)

    all_results = []
    for sid in scenes:
        result = run_experiment(episode_path, sid, output_dir, args.rounds)
        all_results.append(result)
        time.sleep(3)  # Rate limit between scenes

    # Final summary
    log("\n" + "=" * 60)
    log("  AUTO-IMPROVE SUMMARY")
    log("=" * 60)
    for r in all_results:
        if r:
            log(f"  Scene {r['scene_id']}: {r['best_score']}/100 (Round {r['best_round']}/{r['total_rounds']})")
    avg = sum(r["best_score"] for r in all_results if r) / max(len(all_results), 1)
    log(f"  Average: {avg:.1f}/100")
    log("=" * 60)

    # Save summary
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
