from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import jieba
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT.parent
RAW_DB_PATH = PROJECT_ROOT / "data" / "raw" / "mentors_ynu_latest.db"
OUTPUT_DIR = PROJECT_ROOT / "data" / "clean"
CLEAN_DB_PATH = OUTPUT_DIR / "mentors_clean.db"
CLEAN_CSV_PATH = OUTPUT_DIR / "mentors_clean.csv"

TARGET_COLUMNS = [
    "id",
    "name",
    "school",
    "province",
    "title",
    "college",
    "research_area",
    "email",
    "homepage",
    "keywords",
]

STOP_WORDS = {
    "的", "和", "与", "及", "等", "研究", "方向", "领域", "学院", "大学", "团队", "技术", "系统", "理论", "方法",
}

COLUMN_ALIASES = {
    "homepage": ["homepage", "homepage_url", "url", "profile_url"],
    "research_area": ["research_area", "area", "research_direction", "direction"],
    "province": ["province", "region", "location", "area_region"],
}


def clean_text(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def pick_column(raw_df: pd.DataFrame, target: str) -> pd.Series:
    for column in [target, *COLUMN_ALIASES.get(target, [])]:
        if column in raw_df.columns:
            return raw_df[column]
    return pd.Series([""] * len(raw_df), index=raw_df.index)


def normalize_title(value: object) -> str:
    text = clean_text(value)
    if not text or text in {"无", "未公开", "未知", "None", "nan"}:
        return "未公开" if text == "未公开" else ""
    if "副教授" in text:
        return "副教授"
    if "副研究员" in text:
        return "副研究员"
    if "助理研究员" in text:
        return "助理研究员"
    if "助理教授" in text:
        return "助理教授"
    if "教授" in text:
        return "教授"
    if "研究员" in text:
        return "研究员"
    if "讲师" in text:
        return "讲师"
    return text


def extract_keywords(row: pd.Series) -> str:
    existing = clean_text(row.get("keywords", ""))
    if existing:
        return existing
    source = " ".join(clean_text(row.get(col, "")) for col in ["research_area", "college", "school", "title"])
    words = [
        word.strip()
        for word in jieba.lcut(source)
        if len(word.strip()) > 1 and word.strip() not in STOP_WORDS
    ]
    return " ".join(dict.fromkeys(words))


def clean_mentor_database() -> pd.DataFrame:
    if not RAW_DB_PATH.exists():
        raise FileNotFoundError(f"source database not found: {RAW_DB_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(RAW_DB_PATH) as conn:
        raw_df = pd.read_sql_query("SELECT * FROM mentors", conn)

    clean_df = pd.DataFrame()
    for column in TARGET_COLUMNS:
        clean_df[column] = pick_column(raw_df, column)

    for column in TARGET_COLUMNS:
        clean_df[column] = clean_df[column].map(clean_text)

    clean_df["id"] = clean_df["id"].map(clean_text)
    clean_df["title"] = clean_df["title"].map(normalize_title)
    clean_df["keywords"] = clean_df.apply(extract_keywords, axis=1)

    with sqlite3.connect(CLEAN_DB_PATH) as conn:
        clean_df[TARGET_COLUMNS].to_sql("mentors", conn, index=False, if_exists="replace")

    clean_df[TARGET_COLUMNS].to_csv(CLEAN_CSV_PATH, index=False, encoding="utf-8-sig")
    shutil.copy2(RAW_DB_PATH, OUTPUT_DIR / "source_mentors_ynu.db")
    return clean_df[TARGET_COLUMNS]


if __name__ == "__main__":
    df = clean_mentor_database()
    print(f"clean rows: {len(df)}")
    print(f"clean database: {CLEAN_DB_PATH}")
    print(f"clean csv: {CLEAN_CSV_PATH}")

