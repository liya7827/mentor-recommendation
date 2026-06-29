from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithm.match_engine import get_all_advisors, match  # noqa: E402
from backend.database import ALLOWED_PROVINCES, get_columns, get_total_records, is_unlimited, query_mentors, safe_text  # noqa: E402
from backend.llm_reason import (  # noqa: E402
    AI_UNAVAILABLE_MESSAGE,
    DEFAULT_REASON,
    enrich_match_reasons,
    generate_compare_advice,
    generate_favorite_advice,
    log_ai_exception,
    test_doubao_connection,
)


ALLOWED_ORIGINS = ["http://127.0.0.1:5500", "http://localhost:5500"]

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app, resources={r"/api/*": {"origins": "*"}})


def _success(message: str, recommendations: list[dict], status: int = 200):
    return jsonify({"success": True, "message": message, "recommendations": recommendations, "total": len(recommendations)}), status


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "message": message, "recommendations": [], "total": 0}), status


def _log_route_exception(route_name: str, error: Exception) -> None:
    print(f"AI route failed: {route_name}", flush=True)
    print("AI success status: False", flush=True)
    print("AI text length: 0", flush=True)
    log_ai_exception(error)


def _log_ai_success(route_name: str, advice: str) -> None:
    print(f"AI route success: {route_name}", flush=True)
    print("AI success status: True", flush=True)
    print(f"AI text length: {len(advice or '')}", flush=True)


@app.get("/api/health")
def health_check():
    try:
        return jsonify({
            "success": True,
            "message": "服务正常",
            "table": "mentors",
            "total_records": get_total_records(),
            "columns": get_columns(),
        })
    except Exception:
        return jsonify({"success": False, "message": "服务暂不可用"}), 500


@app.get("/api/advisors")
def advisors():
    try:
        return _success("查询成功", get_all_advisors(query_mentors()))
    except Exception:
        return _error("导师列表服务暂不可用", 500)


@app.get("/api/ai/test")
def ai_test():
    try:
        test_doubao_connection()
        return jsonify({"success": True, "message": "豆包 API 已成功接入"})
    except Exception as exc:
        log_ai_exception(exc)
        return jsonify({"success": False, "message": AI_UNAVAILABLE_MESSAGE}), 503


@app.post("/api/match")
def match_advisor():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("请求体必须是 JSON 对象")

    required_fields = ["province", "title", "expected_direction"]
    missing_fields = [field for field in required_fields if field not in body]
    if missing_fields:
        return _error("缺少参数：" + "、".join(missing_fields))

    filters = {field: safe_text(body.get(field)) for field in required_fields}
    if filters["province"] not in ALLOWED_PROVINCES:
        return _error("地区只允许南京或云南")
    if is_unlimited(filters["expected_direction"]):
        return _error("研究方向不能为空")

    try:
        candidates = query_mentors(filters)
        if not candidates:
            return _success("没有符合条件的导师", [])
        recommendations = match(expected_direction=filters["expected_direction"], candidates=candidates, top_k=10)
        if not recommendations:
            return _success("没有符合条件的导师", [])
        try:
            recommendations = enrich_match_reasons(recommendations, filters["expected_direction"], limit=3)
        except Exception:
            recommendations = [dict(item) for item in recommendations]
            for item in recommendations[:3]:
                item["match_reason"] = DEFAULT_REASON
        return _success("匹配成功", recommendations)
    except Exception:
        return _error("匹配服务暂不可用", 500)


@app.post("/api/ai/compare")
def ai_compare():
    body = request.get_json(silent=True)
    mentors = (body.get("mentors") or body.get("advisors")) if isinstance(body, dict) else None
    if not isinstance(mentors, list) or not 2 <= len(mentors) <= 3:
        return jsonify({"success": False, "message": "请选择 2-3 位导师进行智能对比"}), 400
    try:
        advice = generate_compare_advice(mentors)
        if not safe_text(advice):
            raise RuntimeError("AI advice is empty")
        _log_ai_success("/api/ai/compare", advice)
        return jsonify({"success": True, "advice": advice})
    except Exception as exc:
        _log_route_exception("/api/ai/compare", exc)
        return jsonify({"success": False, "message": AI_UNAVAILABLE_MESSAGE}), 503


@app.post("/api/ai/favorites")
def ai_favorites():
    body = request.get_json(silent=True)
    mentors = (body.get("mentors") or body.get("advisors")) if isinstance(body, dict) else None
    if not isinstance(mentors, list) or not 2 <= len(mentors) <= 3:
        return jsonify({"success": False, "message": "请选择 2-3 位心仪导师生成智能建议"}), 400
    try:
        advice = generate_favorite_advice(mentors)
        if not safe_text(advice):
            raise RuntimeError("AI advice is empty")
        _log_ai_success("/api/ai/favorites", advice)
        return jsonify({"success": True, "advice": advice})
    except Exception as exc:
        _log_route_exception("/api/ai/favorites", exc)
        return jsonify({"success": False, "message": AI_UNAVAILABLE_MESSAGE}), 503


if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    print("研究生导师智能推荐系统 Flask 后端")
    print(f"健康检查: http://{host}:{port}/api/health")
    print(f"匹配接口: POST http://{host}:{port}/api/match")
    app.run(host=host, port=port, debug=False, use_reloader=False)
