from algorithm.match_engine import MIN_SCORE, get_all_advisors, match
from backend.database import query_mentors


EXPECTED_FIELDS = {"id", "name", "title", "school", "province", "college", "area", "score", "email", "homepage_url"}


def test_get_all_advisors_uses_latest_database_rows_without_removed_fields():
    advisors = get_all_advisors(query_mentors())

    assert len(advisors) == 1075
    assert advisors[0]["school"] in {"云南大学", "南京大学"}
    assert set(advisors[0].keys()) == EXPECTED_FIELDS
    assert "tier" not in advisors[0]
    assert "major" not in advisors[0]
    assert "pub" not in advisors[0]


def test_match_returns_sorted_python_float_scores():
    candidates = query_mentors({"province": "云南", "title": "教授"})
    results = match("无机化学 稀贵金属分离 物理化学", candidates, top_k=10)

    assert results
    assert len(results) <= 10
    assert all(isinstance(item["score"], float) for item in results)
    assert [item["score"] for item in results] == sorted([item["score"] for item in results], reverse=True)


def test_same_query_is_stable():
    candidates = query_mentors({"province": "云南", "title": "教授"})
    first = match("无机化学 稀贵金属分离 物理化学", candidates, top_k=10)
    second = match("无机化学 稀贵金属分离 物理化学", candidates, top_k=10)

    assert first == second


def test_minimum_score_threshold_filters_unrelated_query():
    candidates = query_mentors({"province": "云南", "title": "教授"})
    results = match("zzzxxyyqqq unrelatedtoken", candidates, top_k=10, min_score=MIN_SCORE)

    assert results == []


def test_match_uses_expected_direction_and_not_title_or_school_as_soft_text():
    candidates = query_mentors({"province": "云南", "title": ""})
    chemistry_results = match("无机化学 稀贵金属分离 物理化学", candidates, top_k=10)
    teaching_results = match("英语 翻译 教学", candidates, top_k=10)

    assert chemistry_results
    assert teaching_results
    assert chemistry_results[0]["area"] != teaching_results[0]["area"] or chemistry_results[0]["name"] != teaching_results[0]["name"]


def test_missing_values_are_empty_strings_not_none():
    result = match("无机化学", query_mentors({"province": "云南", "title": "教授"}), top_k=1)[0]

    assert set(result.keys()) == EXPECTED_FIELDS
    for key, value in result.items():
        if key != "score":
            assert value is not None
            assert isinstance(value, str)
    assert result["province"] == "云南"
