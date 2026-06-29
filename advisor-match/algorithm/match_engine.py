from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import jieba
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "mentors_data.json"
TABLE_NAME = "mentors"
RETURN_FIELDS = ["id", "name", "title", "school", "province", "college", "area", "score", "email", "homepage_url"]
MIN_SCORE = 0.05
STOP_WORDS = {"的", "和", "与", "及", "等", "研究", "方向", "领域", "本人", "相关", "技术", "系统", "理论", "方法", "不限"}


@dataclass(frozen=True)
class TfidfState:
    records: list[dict]
    vectorizer: TfidfVectorizer | None
    matrix: object | None
    index_by_id: dict[str, int]


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _tokenize(text: object) -> str:
    words = []
    for word in jieba.lcut(_safe_text(text)):
        word = word.strip()
        if len(word) > 1 and word not in STOP_WORDS:
            words.append(word)
    return " ".join(words)


def _candidate_text(mentor: dict) -> str:
    research_area = _safe_text(mentor.get("research_area") or mentor.get("area"))
    keywords = _safe_text(mentor.get("keywords"))
    return " ".join([research_area, research_area, keywords, keywords])


def _normalize_candidate(mentor: dict, score: float = 0.0) -> dict:
    return {
        "id": _safe_text(mentor.get("id")),
        "name": _safe_text(mentor.get("name")),
        "title": _safe_text(mentor.get("title")),
        "school": _safe_text(mentor.get("school")),
        "province": _safe_text(mentor.get("province")),
        "college": _safe_text(mentor.get("college")),
        "area": _safe_text(mentor.get("research_area") or mentor.get("area")),
        "score": float(score),
        "email": _safe_text(mentor.get("email")),
        "homepage_url": _safe_text(mentor.get("homepage") or mentor.get("homepage_url")),
    }


def _load_records() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [{key: _safe_text(item.get(key, "")) for key in item.keys()} for item in data]


def _build_state() -> TfidfState:
    records = _load_records()
    if not records:
        return TfidfState([], None, None, {})

    texts = [_tokenize(_candidate_text(record)) for record in records]
    if not any(texts):
        return TfidfState(records, None, None, {record.get("id", ""): index for index, record in enumerate(records)})

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(texts)
    index_by_id = {_safe_text(record.get("id")): index for index, record in enumerate(records)}
    return TfidfState(records, vectorizer, matrix, index_by_id)


_STATE = _build_state()


def reload_model() -> TfidfState:
    global _STATE
    _STATE = _build_state()
    return _STATE


def match(expected_direction: str, candidates: Iterable[dict] | pd.DataFrame | None = None, top_k: int = 10, min_score: float = MIN_SCORE) -> list[dict]:
    if not _safe_text(expected_direction):
        return []
    if candidates is None:
        return []

    records = candidates.to_dict("records") if isinstance(candidates, pd.DataFrame) else list(candidates)
    if not records or _STATE.vectorizer is None or _STATE.matrix is None:
        return []

    query_text = _tokenize(expected_direction)
    if not query_text:
        return []

    candidate_records = []
    candidate_indices = []
    for record in records:
        mentor_id = _safe_text(record.get("id"))
        if mentor_id in _STATE.index_by_id:
            candidate_records.append(record)
            candidate_indices.append(_STATE.index_by_id[mentor_id])

    if not candidate_indices:
        return []

    query_vec = _STATE.vectorizer.transform([query_text])
    candidate_matrix = _STATE.matrix[candidate_indices]
    scores = cosine_similarity(query_vec, candidate_matrix).flatten()

    results = []
    for record, score in zip(candidate_records, scores):
        score_value = round(float(score), 4)
        if score_value < min_score:
            continue
        results.append(_normalize_candidate(record, score_value))

    results.sort(key=lambda item: item["score"], reverse=True)
    unique_results = []
    seen = set()
    for item in results:
        identity = (item["name"], item["school"], item["area"])
        if identity in seen:
            continue
        seen.add(identity)
        unique_results.append(item)
    return unique_results[:top_k]


def get_all_advisors(candidates: Iterable[dict] | pd.DataFrame) -> list[dict]:
    records = candidates.to_dict("records") if isinstance(candidates, pd.DataFrame) else list(candidates)
    return [_normalize_candidate(record, 0.0) for record in records]
