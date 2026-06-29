import pytest

import backend.app as backend_app
import backend.llm_reason as llm_reason
from backend.app import app


@pytest.fixture(autouse=True)
def clear_ai_env(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_MODEL", raising=False)
    monkeypatch.delenv("ARK_BASE_URL", raising=False)


def payload(**overrides):
    data = {
        "province": "云南",
        "title": "不限",
        "expected_direction": "无机化学 稀贵金属分离 物理化学",
    }
    data.update(overrides)
    return data


def sample_mentor(identifier="1"):
    return {
        "id": identifier,
        "name": "测试导师",
        "title": "教授",
        "school": "云南大学",
        "province": "云南",
        "college": "化学科学与工程学院",
        "area": "无机化学",
        "score": 0.8,
        "email": "",
        "homepage_url": "",
    }


def test_health_check_uses_latest_clean_data_without_local_paths():
    with app.test_client() as client:
        response = client.get("/api/health")
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["table"] == "mentors"
    assert body["total_records"] == 1075
    assert body["columns"] == ["id", "name", "school", "province", "title", "college", "research_area", "email", "homepage", "keywords"]
    assert "database" not in body
    assert "csv" not in body
    assert "tier" not in body["columns"]
    assert "major" not in body["columns"]
    assert "pub" not in body["columns"]


def test_three_parameter_match_request():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="教授"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["recommendations"]
    assert body["total"] == len(body["recommendations"])
    assert "match_reason" in body["recommendations"][0]


def test_match_no_longer_requires_tier():
    data = payload(title="教授")
    assert "tier" not in data

    with app.test_client() as client:
        response = client.post("/api/match", json=data)

    assert response.status_code == 200


def test_invalid_province_returns_400():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(province="北京"))
        body = response.get_json()

    assert response.status_code == 400
    assert body["message"] == "province 只允许南京或云南"


def test_empty_expected_direction_returns_400():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(expected_direction=""))
        body = response.get_json()

    assert response.status_code == 400
    assert body["success"] is False
    assert body["message"] == "expected_direction 不能为空"


def test_allowed_cors_origin_is_returned():
    with app.test_client() as client:
        response = client.options("/api/match", headers={"Origin": "http://127.0.0.1:5500"})

    assert response.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5500"


def test_disallowed_cors_origin_is_not_returned():
    with app.test_client() as client:
        response = client.options("/api/match", headers={"Origin": "http://example.com"})

    assert response.headers.get("Access-Control-Allow-Origin") is None


def test_professor_filter_does_not_return_associate_professor():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="教授"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["recommendations"]
    assert all(item["title"] == "教授" for item in body["recommendations"])
    assert all("副教授" not in item["title"] for item in body["recommendations"])


def test_associate_professor_filter_does_not_return_professor():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="副教授", expected_direction="建筑 规划 桥梁 抗震 结构"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["recommendations"]
    assert all(item["title"] == "副教授" for item in body["recommendations"])


def test_province_hard_filter_limits_candidates():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(province="南京", title="教授", expected_direction="新闻 传播 法学"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["recommendations"]
    assert all(item["province"] == "南京" for item in body["recommendations"])


def test_no_candidate_returns_empty_recommendations():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="不存在的职称"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["recommendations"] == []
    assert body["total"] == 0


def test_scores_are_descending_and_fields_are_complete():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="教授"))
        body = response.get_json()

    required = {"id", "name", "title", "school", "province", "college", "area", "score", "email", "homepage_url"}
    scores = [item["score"] for item in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    for index, item in enumerate(body["recommendations"]):
        assert required.issubset(item.keys())
        if index < 3:
            assert "match_reason" in item
        else:
            assert "match_reason" not in item
        assert "tier" not in item
        assert "major" not in item
        assert "pub" not in item


def test_match_works_without_doubao_api_key():
    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="教授"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["recommendations"]
    assert body["recommendations"][0]["match_reason"] == "暂无智能推荐理由"


def test_ai_reason_failure_does_not_break_tfidf(monkeypatch):
    def raise_reason(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(backend_app, "enrich_match_reasons", raise_reason)

    with app.test_client() as client:
        response = client.post("/api/match", json=payload(title="教授"))
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["recommendations"]
    assert body["recommendations"][0]["match_reason"] == "暂无智能推荐理由"


def test_ai_compare_requires_two_or_three_mentors():
    with app.test_client() as client:
        response = client.post("/api/ai/compare", json={"mentors": [sample_mentor()]})
        body = response.get_json()

    assert response.status_code == 400
    assert body["success"] is False
    assert body["advice"] == ""


def test_ai_compare_success_and_advisors_alias(monkeypatch):
    monkeypatch.setattr(backend_app, "generate_compare_advice", lambda mentors: "对比建议")

    with app.test_client() as client:
        response = client.post("/api/ai/compare", json={"advisors": [sample_mentor("1"), sample_mentor("2")]})
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["advice"] == "对比建议"


def test_ai_favorites_requires_non_empty_list():
    with app.test_client() as client:
        response = client.post("/api/ai/favorites", json={"mentors": []})
        body = response.get_json()

    assert response.status_code == 400
    assert body["success"] is False
    assert body["advice"] == ""


def test_ai_favorites_success(monkeypatch):
    monkeypatch.setattr(backend_app, "generate_favorite_advice", lambda mentors: "择师建议")

    with app.test_client() as client:
        response = client.post("/api/ai/favorites", json={"mentors": [sample_mentor("1"), sample_mentor("2")]})
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["advice"] == "择师建议"


def test_llm_defaults_use_doubao_ark_settings():
    api_key, model, base_url = llm_reason._settings()

    assert api_key == ""
    assert model == "doubao-seed-2-0-lite-260428"
    assert base_url == "https://ark.cn-beijing.volces.com/api/v3"


def test_doubao_responses_api_uses_responses_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = '{"output_text":"豆包 API 已成功接入"}'

        def json(self):
            return {"output_text": "豆包 API 已成功接入"}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_MODEL", "doubao-seed-2-0-lite-260428")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    monkeypatch.setattr(llm_reason.requests, "post", fake_post)

    result = llm_reason.test_doubao_connection()

    assert result == "豆包 API 已成功接入"
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["timeout"] == (10, 90)
    assert captured["json"] == {
        "model": "doubao-seed-2-0-lite-260428",
        "input": "请回复：豆包 API 已成功接入",
        "max_output_tokens": 50,
    }


def test_doubao_read_timeout_retries_once(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        ok = True
        status_code = 200
        text = '{"output_text":"成功"}'

        def json(self):
            return {"output_text": "成功"}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise llm_reason.requests.exceptions.ReadTimeout("timeout")
        return FakeResponse()

    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setattr(llm_reason.requests, "post", fake_post)

    assert llm_reason._post_responses("测试", max_tokens=100) == "成功"
    assert calls["count"] == 2


def test_ai_prompt_uses_compact_mentor_payload(monkeypatch):
    captured = {}
    long_area = "人工智能" * 120

    def fake_chat(messages, max_tokens):
        captured["text"] = messages[-1]["content"]
        captured["max_tokens"] = max_tokens
        return "建议内容"

    monkeypatch.setattr(llm_reason, "_chat", fake_chat)

    advice = llm_reason.generate_compare_advice([
        {
            "id": "1",
            "name": "张三",
            "title": "教授",
            "school": "云南大学",
            "province": "云南",
            "college": "信息学院",
            "area": long_area,
            "score": 0.9,
            "email": "hidden@example.com",
            "homepage_url": "https://example.com",
            "tier": "old",
            "major": "old",
            "pub": "old",
        },
        {
            "id": "2",
            "name": "李四",
            "title": "副教授",
            "school": "南京大学",
            "province": "南京",
            "college": "新闻传播学院",
            "research_area": "传播学",
            "score": 0.8,
        },
    ])

    assert advice == "建议内容"
    assert captured["max_tokens"] == 380
    assert "hidden@example.com" not in captured["text"]
    assert "homepage_url" not in captured["text"]
    assert "tier" not in captured["text"]
    assert "major" not in captured["text"]
    assert "pub" not in captured["text"]
    assert long_area not in captured["text"]
    assert "200到300字" in captured["text"]


def test_ai_compare_timeout_returns_specific_message(monkeypatch):
    timeout = llm_reason.requests.exceptions.ReadTimeout("timeout")

    def raise_timeout(*args, **kwargs):
        raise llm_reason.ArkAPIError("timeout", request_url="https://ark.cn-beijing.volces.com/api/v3/responses", original=timeout)

    monkeypatch.setattr(backend_app, "generate_compare_advice", raise_timeout)

    with app.test_client() as client:
        response = client.post("/api/ai/compare", json={"mentors": [sample_mentor("1"), sample_mentor("2")]})
        body = response.get_json()

    assert response.status_code == 504
    assert body["message"] == "AI 生成时间较长，请稍后重试或减少对比导师数量。"


def test_doubao_base_url_accepts_markdown_link(monkeypatch):
    monkeypatch.setenv("ARK_BASE_URL", "[https://ark.cn-beijing.volces.com/api/v3](https://ark.cn-beijing.volces.com/api/v3)")

    assert llm_reason._settings()[2] == "https://ark.cn-beijing.volces.com/api/v3"


def test_ai_test_returns_unavailable_without_key():
    with app.test_client() as client:
        response = client.get("/api/ai/test")
        body = response.get_json()

    assert response.status_code == 503
    assert body["success"] is False
    assert body["message"] == "AI 服务暂时不可用，请稍后重试"


def test_ai_test_success_message(monkeypatch):
    monkeypatch.setattr(backend_app, "test_doubao_connection", lambda: "豆包 API 已成功接入")

    with app.test_client() as client:
        response = client.get("/api/ai/test")
        body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "豆包 API 已成功接入"
