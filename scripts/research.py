"""
研究資料搜集模組 — researcher agent 的工具腳本。

負責搜集原始資料（不做整合判斷），整合由 OpenClaw researcher agent (Sonnet) 完成。

v2 多角度搜尋：
  Step 0. Gemini 拆解主題為 2-3 個搜尋子面向
  Step 1. Gemini + Google Search grounding — 逐面向搜尋，合併去重
  Step 2. PubMed E-utilities — 逐面向搜尋，合併去重
  Step 3. USDA FoodData Central — 營養數據查證

輸出模式：
  --mode collect  → 輸出原始搜集資料 JSON（給 agent 整合用）
  --mode full     → 腳本內用 Gemini 整合為 research_report.schema.json（獨立執行用）

用法:
  # 搜集模式（推薦，由 researcher agent 整合）
  python scripts/research.py --topic "地瓜 vs 白飯 升糖指數" --mode collect -o raw.json

  # 完整模式（腳本自行整合，獨立執行用）
  python scripts/research.py --topic "地瓜 vs 白飯 升糖指數" --topic-id 7 --mode full -o report.json

環境變數:
  GEMINI_API_KEY — Gemini API key（必填，用於搜尋）
  GEMINI_SEARCH_MODEL — 搜尋用模型（預設 gemini-2.5-flash）
  NCBI_API_KEY — PubMed API key（選填，提高速率限制）
  USDA_API_KEY — USDA FoodData Central API key（選填）
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from validate_schema import validate_research

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_SEARCH_MODEL = os.environ.get("GEMINI_SEARCH_MODEL", "gemini-2.5-flash")
GEMINI_QUICK_MODEL = os.environ.get("GEMINI_QUICK_MODEL", "gemini-3-flash-preview")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")


def log(msg: str):
    print(f"[researcher] {msg}", file=sys.stderr)


# ── Gemini 輔助（輕量任務用 flash）────────────────────────────

def _gemini_quick(prompt: str, max_tokens: int = 200) -> str:
    """輕量 Gemini 呼叫（翻譯、提取關鍵字），用 2.0-flash（非 thinking 模型）。"""
    if not GEMINI_API_KEY:
        return ""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_QUICK_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 8192},
    }).encode()

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"].strip()
    except Exception as e:
        log(f"Gemini quick 呼叫失敗: {e}")

    return ""


# ── Gemini + Google Search Grounding ──────────────────────────

def gemini_grounded_search(query: str, system_prompt: str = "") -> dict:
    """用 Gemini + Google Search grounding 搜尋，回傳文字+來源。"""
    if not GEMINI_API_KEY:
        log("錯誤: 請設定 GEMINI_API_KEY")
        return {"error": "GEMINI_API_KEY 未設定"}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_SEARCH_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"parts": [{"text": query}]}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        },
    }

    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        log(f"Gemini API 錯誤 HTTP {e.code}: {body}")
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        log(f"Gemini API 錯誤: {e}")
        return {"error": str(e)}

    text = ""
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "text" in part:
            text += part["text"]

    grounding = data.get("candidates", [{}])[0].get("groundingMetadata", {})
    sources = []
    for chunk in grounding.get("groundingChunks", []):
        web = chunk.get("web", {})
        if web.get("uri"):
            sources.append({"url": web["uri"], "title": web.get("title", "")})

    return {"text": text, "sources": sources}


# ── PubMed E-utilities ────────────────────────────────────────

def pubmed_search(query: str, max_results: int = 5) -> list[dict]:
    """搜尋 PubMed，回傳文章摘要列表。"""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "sort": "relevance",
        "retmode": "json",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    search_url = f"{base}/esearch.fcgi?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(search_url, timeout=30) as resp:
            search_data = json.loads(resp.read())
    except Exception as e:
        log(f"PubMed 搜尋失敗: {e}")
        return []

    ids = search_data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        log("PubMed: 無結果")
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "json",
        "rettype": "abstract",
    }
    if NCBI_API_KEY:
        fetch_params["api_key"] = NCBI_API_KEY

    fetch_url = f"{base}/esummary.fcgi?{urllib.parse.urlencode(fetch_params)}"

    try:
        with urllib.request.urlopen(fetch_url, timeout=30) as resp:
            fetch_data = json.loads(resp.read())
    except Exception as e:
        log(f"PubMed 摘要取得失敗: {e}")
        return []

    results = []
    for pmid in ids:
        article = fetch_data.get("result", {}).get(pmid, {})
        if not article or "error" in article:
            continue
        authors = article.get("authors", [])
        first_author = authors[0].get("name", "") if authors else ""
        year = article.get("pubdate", "")[:4]
        journal = article.get("fulljournalname", article.get("source", ""))

        results.append({
            "pmid": pmid,
            "title": article.get("title", ""),
            "citation": f"{first_author} et al., {journal}, {year}",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "year": year,
            "journal": journal,
        })

    log(f"PubMed: 找到 {len(results)} 篇")
    return results


# ── USDA FoodData Central ─────────────────────────────────────

def usda_search(food_query: str, max_results: int = 3) -> list[dict]:
    """搜尋 USDA FoodData Central，回傳營養數據。"""
    params = {
        "query": food_query,
        "pageSize": str(max_results),
        "dataType": "SR Legacy,Foundation",
        "api_key": USDA_API_KEY,
    }
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log(f"USDA 搜尋失敗: {e}")
        return []

    results = []
    for food in data.get("foods", []):
        nutrients = {}
        for n in food.get("foodNutrients", []):
            name = n.get("nutrientName", "")
            if name:
                nutrients[name] = {
                    "value": n.get("value", 0),
                    "unit": n.get("unitName", ""),
                }
        results.append({
            "fdc_id": food.get("fdcId"),
            "description": food.get("description", ""),
            "nutrients": nutrients,
        })

    log(f"USDA: 找到 {len(results)} 項")
    return results


# ── Claude Code WebSearch（補強層）─────────────────────────────

def claude_web_search(queries: list[str]) -> dict:
    """
    用 Claude Code CLI 的 WebSearch 補搜 Gemini grounding 漏掉的研究。
    一次傳入多個 query，讓 Claude 批次搜尋後回傳結構化結果。
    """
    if not queries:
        return {"text": "", "sources": []}

    queries_text = "\n".join(f"- {q}" for q in queries)
    prompt = (
        f"Use WebSearch to search for each of the following queries. "
        f"For each query, find the most authoritative sources "
        f"(prioritize: Nature, NEJM, JAMA, BMJ, Lancet, AJCN, Cochrane, "
        f"USDA, WHO, large RCTs, meta-analyses).\n\n"
        f"Queries:\n{queries_text}\n\n"
        f"For each finding, output in this exact format (one per line):\n"
        f"FINDING: [key finding] | SOURCE: [citation] | URL: [url] | TYPE: [rct/meta_analysis/cohort/review/guideline]"
    )

    try:
        # 移除所有 Claude Code session 環境變數以允許巢狀呼叫
        env = os.environ.copy()
        for key in list(env.keys()):
            if key.startswith("CLAUDE") and key != "CLAUDE_API_KEY":
                env.pop(key)

        result = subprocess.run(
            ["claude", "-p", prompt,
             "--allowedTools", "WebSearch",
             "--output-format", "text"],
            capture_output=True, text=True, encoding="utf-8",
            timeout=180, cwd=str(BASE), env=env,
        )
        if result.returncode != 0:
            log(f"Claude WebSearch 失敗: {result.stderr[:200]}")
            return {"text": "", "sources": []}

        output = result.stdout.strip()

        # 解析結構化輸出
        sources = []
        findings_text = []
        for line in output.split("\n"):
            if line.startswith("FINDING:"):
                parts = line.split(" | ")
                finding = {}
                for part in parts:
                    part = part.strip()
                    if part.startswith("FINDING:"):
                        finding["finding"] = part[8:].strip()
                    elif part.startswith("SOURCE:"):
                        finding["citation"] = part[7:].strip()
                    elif part.startswith("URL:"):
                        finding["url"] = part[4:].strip()
                    elif part.startswith("TYPE:"):
                        finding["study_type"] = part[5:].strip()
                if finding.get("finding"):
                    findings_text.append(finding["finding"])
                if finding.get("url"):
                    sources.append(finding)

        # 也保留原始文字（包含非結構化的部分）
        return {
            "text": output,
            "sources": sources,
            "findings": findings_text,
        }

    except subprocess.TimeoutExpired:
        log("Claude WebSearch 逾時 (180s)")
        return {"text": "", "sources": []}
    except FileNotFoundError:
        log("Claude CLI 未安裝或不在 PATH 中，跳過 WebSearch 補強")
        return {"text": "", "sources": []}
    except Exception as e:
        log(f"Claude WebSearch 錯誤: {e}")
        return {"text": "", "sources": []}


# ── Step 0: 子面向拆解 ────────────────────────────────────────

def _decompose_angles(topic: str) -> list[str]:
    """用 Gemini 將主題拆成 3 個搜尋子面向。獨立 API 呼叫，temperature 0.5。"""
    if not GEMINI_API_KEY:
        return [topic]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_QUICK_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        f"Task: split a health topic into 3 search angles separated by |||.\n"
        f"Rules: each angle uses DIFFERENT keywords. Mix English and Chinese. "
        f"You MUST output exactly 3 angles separated by |||.\n\n"
        f"Topic: 黑巧克力和咖啡抗老化\n"
        f"Angle1 ||| Angle2 ||| Angle3: dark chocolate cocoa flavanol antioxidant cardiovascular RCT ||| "
        f"coffee daily intake mortality longevity meta-analysis cohort study ||| "
        f"theobromine epigenetic aging telomere DNA methylation biomarker\n\n"
        f"Topic: 白粥升糖指數\n"
        f"Angle1 ||| Angle2 ||| Angle3: white rice porridge congee glycemic index GI blood sugar ||| "
        f"rice cooking time starch gelatinization nutrition ||| "
        f"diabetes diet carbohydrate postprandial glucose response\n\n"
        f"Topic: {topic}\n"
        f"Angle1 ||| Angle2 ||| Angle3:"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 8192},
    }).encode()

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                raw = part["text"].strip()
                angles = [a.strip() for a in raw.split("|||") if a.strip()]
                angles = [a for a in angles if len(a) > 10]
                if len(angles) >= 2:
                    return angles[:3]
    except Exception as e:
        log(f"子面向拆解失敗: {e}")

    return [topic]


# ── 資料搜集（collect 模式，v2 多角度）─────────────────────────

def collect_raw_data(topic: str, food_keywords: list[str] | None = None) -> dict:
    """
    v2 多角度搜集：先拆子面向，再逐面向搜 Gemini + PubMed，合併去重。
    """
    log(f"開始搜集: {topic}")

    # Step 0: 拆解子面向
    log("Step 0: 拆解搜尋子面向...")
    angles = _decompose_angles(topic)
    log(f"子面向 ({len(angles)}): {angles}")

    time.sleep(0.5)

    # Step 1: Gemini + Google Search grounding（逐面向搜尋）
    system_prompt = (
        "你是營養學和健康科學的研究助手。"
        "搜尋時優先找：系統回顧(meta-analysis)、RCT、WHO/衛福部/USDA指南。"
        "回答要包含具體數字、研究年份、期刊名稱。"
        "用繁體中文回答。"
    )
    all_gemini_text = []
    seen_urls = set()
    all_gemini_sources = []

    for i, angle in enumerate(angles):
        search_query = (
            f"最新研究: {angle}\n"
            f"請搜尋：1) 學術研究和系統回顧 2) 官方營養指南 "
            f"3) 具體數據和比較數字 4) 常見迷思 vs 實際研究發現"
        )
        log(f"Step 1.{i+1}: Gemini 搜尋 [{angle[:40]}...]")
        result = gemini_grounded_search(search_query, system_prompt)
        if "error" not in result:
            all_gemini_text.append(result.get("text", ""))
            for src in result.get("sources", []):
                url = src.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_gemini_sources.append(src)
        else:
            log(f"  搜尋失敗: {result['error']}")
        if i < len(angles) - 1:
            time.sleep(1)

    time.sleep(1)

    # Step 2: PubMed（逐面向搜尋，去重）
    log("Step 2: PubMed 多角度搜尋...")
    seen_pmids = set()
    all_pubmed = []

    for i, angle in enumerate(angles):
        en_query = _gemini_quick(
            f"Convert this Chinese health/nutrition topic into a PubMed search query. "
            f"Use MeSH-compatible English terms. Use AND between concept groups, "
            f"OR between synonyms. Wrap multi-word terms in quotes. "
            f"Output ONLY the query string, nothing else.\n"
            f"Example: '地瓜 vs 白飯 升糖指數' → '\"sweet potato\" AND \"glycemic index\"'\n"
            f"Example: '鈣質吸收 維生素D' → 'calcium absorption AND \"vitamin D\"'\n\n"
            f"Topic: {angle}"
        )
        if not en_query:
            en_query = angle
        log(f"Step 2.{i+1}: PubMed [{en_query[:50]}...]")
        articles = pubmed_search(en_query)
        for art in articles:
            pmid = art.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                all_pubmed.append(art)
        if i < len(angles) - 1:
            time.sleep(0.5)

    log(f"PubMed 合計: {len(all_pubmed)} 篇（去重後）")
    time.sleep(0.5)

    # Step 3: USDA
    usda_data = []
    keywords = food_keywords
    if not keywords:
        kw_text = _gemini_quick(
            f"從以下主題中提取可在 USDA FoodData Central 搜尋的食材英文名。"
            f"每行一個，最多 3 個。如果主題不涉及具體食材，回覆 NONE。\n\n主題: {topic}"
        )
        if kw_text and "NONE" not in kw_text.upper():
            keywords = [line.strip() for line in kw_text.split("\n") if line.strip()]

    if keywords:
        log(f"Step 3: USDA 查詢 {keywords}...")
        for kw in keywords[:3]:
            results = usda_search(kw)
            usda_data.extend(results)
            time.sleep(0.3)
    else:
        log("Step 3: 無食材關鍵字，跳過 USDA")

    # Step 4: Claude WebSearch 補強（針對高證據等級研究）
    claude_data = {"text": "", "sources": [], "findings": []}
    补_queries = [
        f"{topic} RCT randomized controlled trial clinical trial",
        f"{topic} meta-analysis systematic review large cohort study",
        f"{topic} official guidelines WHO USDA dietary recommendations",
    ]
    log("Step 4: Claude WebSearch 補強（搜尋頂刊 RCT / meta-analysis）...")
    claude_data = claude_web_search(补_queries)
    if claude_data.get("sources"):
        log(f"Claude WebSearch: 找到 {len(claude_data['sources'])} 筆補強來源")
    else:
        log("Claude WebSearch: 無補強結果或 CLI 不可用")

    return {
        "topic": topic,
        "search_angles": angles,
        "google_search": {
            "summary": "\n\n---\n\n".join(all_gemini_text),
            "sources": all_gemini_sources,
        },
        "claude_search": claude_data,
        "pubmed": all_pubmed,
        "usda": usda_data,
        "search_model": GEMINI_SEARCH_MODEL,
    }


# ── Gemini 整合（full 模式，獨立執行用）──────────────────────

def synthesize_with_gemini(topic: str, topic_id: int, raw_data: dict) -> dict:
    """用 Gemini 將原始資料整合為 research_report JSON。獨立執行時的 fallback。"""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY 未設定"}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_SEARCH_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    prompt = f"""你是「時時靜好」YouTube Shorts 頻道的研究員。
請將以下研究資料整合為一份結構化研究報告 JSON。

## 主題
{topic}

## Google Search 研究結果
{raw_data.get('google_search', {}).get('summary', '（無）')[:4000]}

## Google Search 來源
{json.dumps(raw_data.get('google_search', {}).get('sources', []), ensure_ascii=False)[:2000]}

## Claude WebSearch 補強（頂刊 RCT / meta-analysis）
{raw_data.get('claude_search', {}).get('text', '（無）')[:4000]}

## Claude WebSearch 結構化來源
{json.dumps(raw_data.get('claude_search', {}).get('sources', []), ensure_ascii=False)[:2000]}

## PubMed 文獻
{json.dumps(raw_data.get('pubmed', []), ensure_ascii=False)[:3000]}

## USDA 營養數據
{json.dumps(raw_data.get('usda', []), ensure_ascii=False)[:2000]}

## 輸出格式（research_report.schema.json）

{{
  "topic": "研究主題（繁體中文）",
  "topic_id": {topic_id},
  "cognitive_gap": {{
    "common_belief": "大眾普遍認知",
    "actual_finding": "研究實際發現",
    "contrast_magnitude": "反差程度描述"
  }},
  "verified_data": [
    {{
      "claim": "可引用的數據聲明",
      "source_citation": "來源引用（期刊+年份 或 機構）",
      "source_url": "https://...",
      "confidence": "high/medium/low"
    }}
  ],
  "sources": [
    {{
      "citation": "引用格式",
      "url": "https://...",
      "key_finding": "關鍵發現",
      "study_type": "rct/meta_analysis/cohort/cross_sectional/review/guideline/database"
    }}
  ],
  "recommended_type": "standard/ranking/hybrid/quick_cut",
  "type_reasoning": "為什麼建議此型態",
  "engagement_signals": {{
    "virality_score": 8,
    "reasons": ["理由1"],
    "risks": ["風險1"]
  }},
  "ranking_candidates": [
    {{"item": "食材", "value": 100, "unit": "mg/100g", "source": "USDA"}}
  ]
}}

### 規則
- 數據必須有出處，不可捏造
- PubMed/USDA 有數據優先使用
- confidence: high=RCT/系統回顧, medium=觀察性研究, low=單一小型研究
- 認知反差越大越好，但必須基於真實研究
- 比較 ≥3 → ranking/hybrid，有情緒轉折 → standard，純數據 → ranking/quick_cut
- ranking_candidates 只在建議 ranking/hybrid 時填
- 繁體中文輸出

### 期刊可信度判斷（重要）
- 優先引用：Nature 系列、NEJM、JAMA、BMJ、Lancet、AJCN、Circulation、PLoS Medicine、Cochrane Reviews、USDA/WHO/衛福部官方指南
- 可引用但標注中等可信度：一般 SCI 期刊（有 PubMed 收錄、IF>2）
- 降級或避免引用：
  - 被 Jeffrey Beall 列入掠奪性期刊名單的期刊
  - 被 Web of Science 除名的期刊
  - 影響因子可疑或自引率異常高的期刊
  - 例如：Aging (aging-us.com) 已被 Web of Science 除名，應降級為 low confidence
- 若研究來自可信機構（如 King's College London）但發表在可疑期刊，引用時寫機構名而非期刊名
- 同一主張如有多個來源，優先引用最高等級期刊的版本

只輸出 JSON。"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
        },
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        return {"error": f"Gemini HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "text" in part:
            text = part["text"].strip()
            if text.startswith("```"):
                lines = text.split("\n")
                start = 1
                end = len(lines)
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip() == "```":
                        end = i
                        break
                text = "\n".join(lines[start:end])
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                return {"error": f"JSON 解析失敗: {e}", "raw": text[:500]}

    return {"error": "Gemini 回應中無文字"}


# ── CLI ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="研究資料搜集")
    parser.add_argument("--topic", required=True, help="研究主題")
    parser.add_argument("--topic-id", type=int, default=0, help="選題庫 ID")
    parser.add_argument("--food-keywords", nargs="*", help="額外食材關鍵字（英文）")
    parser.add_argument("--mode", choices=["collect", "full"], default="collect",
                        help="collect=原始資料（給 agent 整合）, full=完整報告（腳本自行整合）")
    parser.add_argument("--output", "-o", required=True, help="輸出 JSON 路徑")
    args = parser.parse_args()

    # 搜集原始資料
    raw_data = collect_raw_data(args.topic, args.food_keywords)

    if args.mode == "collect":
        result = raw_data
    else:
        # full 模式：用 Gemini 整合（獨立執行時的 fallback）
        log("整合模式: 用 Gemini 整合報告...")
        result = synthesize_with_gemini(args.topic, args.topic_id, raw_data)
        if "error" not in result:
            errors = validate_research(result)
            if errors:
                log(f"警告: 報告有 {len(errors)} 個 schema 錯誤")
                for e in errors[:5]:
                    log(f"  {e}")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"已存: {output_path}")

    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
