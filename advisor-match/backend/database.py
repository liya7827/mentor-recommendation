from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "clean"
DB_PATH = DATA_DIR / "mentors_clean.db"
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


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError("clean database is not ready")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_columns() -> list[str]:
    with connect() as conn:
        rows = conn.execute(f'PRAGMA table_info("{TABLE_NAME}")').fetchall()
        return [row["name"] for row in rows]


def get_total_records() -> int:
    with connect() as conn:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{TABLE_NAME}"').fetchone()[0])


def query_mentors(filters: dict[str, str] | None = None) -> list[dict]:
    filters = filters or {}
    clauses = []
    params: list[str] = []

    with connect() as conn:
        columns = set(get_columns())
        for field in ["province", "title"]:
            value = safe_text(filters.get(field, ""))
            if is_unlimited(value):
                continue
            if field not in columns:
                return []
            clauses.append(f'COALESCE("{field}", "") = ?')
            params.append(value)

        sql = f'SELECT * FROM "{TABLE_NAME}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = conn.execute(sql, params).fetchall()
        return [{key: safe_text(row[key]) for key in row.keys()} for row in rows]
