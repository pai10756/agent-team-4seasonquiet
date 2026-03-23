"""
Schema 驗證工具 — 所有 agent 腳本共用。

驗證 JSON 資料是否符合 schemas/ 下的 JSON Schema 定義。
支援三種 schema：episode、review_result、research_report。

用法:
  # 作為模組引入
  from validate_schema import validate_episode, validate_review, validate_research

  # 命令列驗證
  python scripts/validate_schema.py episode path/to/episode.json
  python scripts/validate_schema.py review_result path/to/review.json
  python scripts/validate_schema.py research_report path/to/report.json
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("請安裝 jsonschema: pip install jsonschema")
    sys.exit(1)

BASE = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = BASE / "schemas"

_schema_cache: dict[str, dict] = {}

SCHEMA_FILES = {
    "episode": "episode.schema.json",
    "review_result": "review_result.schema.json",
    "research_report": "research_report.schema.json",
}


def load_schema(schema_name: str) -> dict:
    """載入並快取 JSON Schema。"""
    if schema_name in _schema_cache:
        return _schema_cache[schema_name]

    filename = SCHEMA_FILES.get(schema_name)
    if not filename:
        raise ValueError(f"未知的 schema: {schema_name}，可用: {list(SCHEMA_FILES.keys())}")

    schema_path = SCHEMAS_DIR / filename
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 檔案不存在: {schema_path}")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _schema_cache[schema_name] = schema
    return schema


def validate(data: dict, schema_name: str) -> list[str]:
    """
    驗證資料是否符合指定 schema。

    回傳:
        空 list = 驗證通過
        非空 list = 每個元素是一條錯誤訊息
    """
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors


def validate_episode(data: dict) -> list[str]:
    return validate(data, "episode")


def validate_review(data: dict) -> list[str]:
    return validate(data, "review_result")


def validate_research(data: dict) -> list[str]:
    return validate(data, "research_report")


def main():
    if len(sys.argv) < 3:
        print("用法: python scripts/validate_schema.py <schema_name> <json_file>")
        print(f"可用 schema: {', '.join(SCHEMA_FILES.keys())}")
        sys.exit(1)

    schema_name = sys.argv[1]
    json_path = Path(sys.argv[2])

    if not json_path.exists():
        print(f"檔案不存在: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    errors = validate(data, schema_name)

    if errors:
        print(f"驗證失敗 ({len(errors)} 個錯誤):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"驗證通過: {json_path.name} 符合 {schema_name} schema")


if __name__ == "__main__":
    main()
