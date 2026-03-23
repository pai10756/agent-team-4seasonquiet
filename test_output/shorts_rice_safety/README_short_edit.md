# Shorts 自動剪輯 — 飯菜冷藏篇

## 產出檔案

| 檔案 | 用途 |
|------|------|
| `final_short_rice_safety_v1.mp4` | 最終輸出（1080x1920, ~33s, H.264+AAC） |
| `edit_timeline.json` | 時間軸設定檔（所有段落、overlay、字幕、旁白） |
| `asset_manifest.json` | 素材清單 |
| `tts/` | ElevenLabs 生成的旁白音檔 |

## 如何重跑

```bash
python scripts/assemble_shorts_overlay.py \
  --config test_output/shorts_rice_safety/edit_timeline.json \
  --output test_output/shorts_rice_safety/final_short_rice_safety_v1.mp4
```

## 如何修改

### 調整時間軸
編輯 `edit_timeline.json` 的 `segments` 陣列：
- `time_range`: 該段在最終影片的時間範圍
- `video_trim`: 從來源影片裁切的時間範圍
- `overlays`: PNG overlay 的位置、大小、透明度
- `subtitle`: 字幕文案與時間
- `narration`: TTS 旁白文案

### 替換素材
直接替換同名 PNG/MP4 檔案，重跑腳本即可。

### 調整旁白
- 修改 `narration` 欄位的文案
- 刪除 `tts/` 目錄讓系統重新生成
- 語速/風格在 `narration.voice_settings` 調整

### 加入 BGM
在 `edit_timeline.json` 的 `bgm.file` 填入 BGM 檔名（放在同目錄下），volume 建議 0.04-0.08。

## 依賴

- Python 3.10+
- moviepy 2.x (`pip install moviepy`)
- Pillow (`pip install Pillow`)
- numpy
- ffmpeg（系統安裝或 `pip install imageio-ffmpeg`）
- ElevenLabs API key（環境變數 `ELEVENLABS_API_KEY`）

## 素材來源

- 影片：Seedance 2.0 生成（image-to-video）
- PNG overlays：Gemini 生成（3D poster style）
- 場景底圖：`test_output/seedance_fridge_test/`
