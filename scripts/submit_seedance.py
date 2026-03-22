"""
Seedance 2.0 影片生成模組 — asset_gen agent 使用。

透過 jimeng-free-api-all 本地 API 提交影片生成請求。
支援 image-to-video（@圖片N 引用）。

用法:
  python scripts/submit_seedance.py --prompt "@1 場景動起來" --images scene_1.jpg --output video.mp4

  # 帶角色設定卡（通過人臉偵測）
  python scripts/submit_seedance.py --prompt "@1 場景動起來" --images scene_1.jpg character_card.jpg --output video.mp4

環境變數:
  JIMENG_API_URL — jimeng-free-api-all 的 URL（預設 http://localhost:8000）
  JIMENG_SESSION_ID — 即夢 session ID（必填）

Seedance 規則:
  - 場景圖不能有正面人臉（會被擋）
  - 需要人物時，提供角色設定卡（turnaround sheet / character card）作為額外 @引用
  - Prompt 用中文效果最好，<2000 字
  - 只描述動態和鏡頭，不重複描述圖片已有的內容
  - 不支援 negative prompt
"""

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request

JIMENG_API = os.environ.get("JIMENG_API_URL", "http://localhost:8000")
SESSION_ID = os.environ.get("JIMENG_SESSION_ID", "da1e4092c23518585e9eeff0735ec949")


def log(msg: str):
    print(f"[seedance] {msg}", file=sys.stderr)


def check_api_health() -> bool:
    """檢查 jimeng-free-api-all 是否可用。"""
    try:
        req = urllib.request.Request(f"{JIMENG_API}/ping", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def submit_video(prompt: str, images: list[str], ratio: str = "9:16",
                 duration: int = 5, model: str = "seedance-2.0") -> dict:
    """提交影片生成請求，回傳 API 回應。"""
    if not SESSION_ID:
        return {"error": "JIMENG_SESSION_ID 未設定"}

    url = f"{JIMENG_API}/v1/videos/generations"

    # @圖片N → @N
    prompt = re.sub(r"@圖片(\d+)", r"@\1", prompt)
    prompt = re.sub(r"@图片(\d+)", r"@\1", prompt)

    boundary = f"----SeedanceBoundary{int(time.time())}"
    body_parts = []

    def add_field(name, value):
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )

    add_field("model", model)
    add_field("prompt", prompt)
    add_field("ratio", ratio)
    add_field("duration", str(duration))

    text_body = "".join(body_parts).encode("utf-8")

    file_parts = []
    for img_path in images:
        if not os.path.exists(img_path):
            return {"error": f"圖片不存在: {img_path}"}
        mime = mimetypes.guess_type(img_path)[0] or "image/jpeg"
        filename = os.path.basename(img_path)
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        with open(img_path, "rb") as f:
            file_data = f.read()
        file_parts.append(header + file_data + b"\r\n")

    closing = f"--{boundary}--\r\n".encode("utf-8")
    full_body = text_body + b"".join(file_parts) + closing

    req = urllib.request.Request(
        url, data=full_body,
        headers={
            "Authorization": f"Bearer {SESSION_ID}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def download_video(video_url: str, output_path: str) -> bool:
    """下載影片。"""
    log(f"下載中: {output_path}")
    try:
        if "jimeng.com" in video_url or "volces.com" in video_url:
            proxy_url = f"{JIMENG_API}/proxy/{video_url}"
        else:
            proxy_url = video_url

        req = urllib.request.Request(proxy_url)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            with open(output_path, "wb") as f:
                f.write(data)
            size_mb = len(data) / 1024 / 1024
            log(f"已下載: {size_mb:.1f}MB → {output_path}")
            return True
    except Exception as e:
        log(f"下載失敗: {e}")
        return False


def generate_seedance_video(prompt: str, images: list[str], output_path: str,
                            ratio: str = "9:16", duration: int = 5) -> dict:
    """
    完整流程：健康檢查 → 提交 → 下載。

    images 清單中可包含場景圖和角色設定卡。
    Seedance 會以 @1, @2, ... 依序引用。

    回傳:
        {"success": bool, "video_path": str, "error": str}
    """
    if not check_api_health():
        return {"success": False, "error": "seedance_api_unavailable"}

    if not SESSION_ID:
        return {"success": False, "error": "JIMENG_SESSION_ID 未設定"}

    log(f"提交: ratio={ratio}, duration={duration}s, images={len(images)}")
    result = submit_video(prompt, images, ratio, duration)

    if "error" in result:
        log(f"提交失敗: {result['error']}")
        return {"success": False, "error": result["error"]}

    # jimeng-free-api-all 內部已輪詢完畢，直接回傳影片 URL
    data = result.get("data", [])
    if not data:
        code = result.get("code", 0)
        msg = result.get("message", "")
        return {"success": False, "error": f"API code {code}: {msg}"}

    video_url = data[0].get("url", "")
    if not video_url:
        return {"success": False, "error": "API 回應無 video URL"}

    log(f"影片就緒: {video_url[:80]}...")

    ok = download_video(video_url, output_path)
    if not ok:
        return {"success": False, "error": "下載失敗"}

    return {
        "success": True,
        "video_path": output_path,
        "video_url": video_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Seedance 2.0 影片生成")
    parser.add_argument("--prompt", required=True, help="影片 prompt（用 @1 @2 引用圖片）")
    parser.add_argument("--images", nargs="*", default=[], help="參考圖片路徑（場景圖 + 角色設定卡）")
    parser.add_argument("--output", "-o", required=True, help="輸出影片路徑")
    parser.add_argument("--ratio", default="9:16", help="畫面比例")
    parser.add_argument("--duration", type=int, default=5, help="時長（秒，4-15）")
    parser.add_argument("--model", default="seedance-2.0", help="模型名稱")
    args = parser.parse_args()

    result = generate_seedance_video(
        args.prompt, args.images, args.output,
        args.ratio, args.duration,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
