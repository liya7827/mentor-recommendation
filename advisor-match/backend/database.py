from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "mentors_data.json"
TABLE_NAME = "mentors"
UNLIMITED_VALUES = {"", "不限", "all", "ALL", "All"}
ALLOWED_PROVINCES = {"南京", "云南"}


def safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def is_unlimited(value: object) -> bool:
    return safe_text(value) in UNLIMITED_VALUES


def _load_data() -> list[dict]:
    if not DATA_FILE.exists():
        raise FileNotFoundError("mentors_data.json is not found")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_columns() -> list[str]:
    data = _load_data()
    if not data:
        return []
    return list(data[0].keys())


def get_total_records() -> int:
    return len(_load_data())


def query_mentors(filters: dict[str, str] | None = None) -> list[dict]:
    filters = filters or {}
    data = _load_data()

    province_filter = safe_text(filters.get("province", ""))
    title_filter = safe_text(filters.get("title", ""))

    result = []
    for item in data:
        province = safe_text(item.get("province", ""))
        title = safe_text(item.get("title", ""))

        if not is_unlimited(province_filter) and province != province_filter:
            continue
        if not is_unlimited(title_filter) and title != title_filter:
            continue

        cleaned = {key: safe_text(item.get(key, "")) for key in get_columns()}
        result.append(cleaned)

    return result
