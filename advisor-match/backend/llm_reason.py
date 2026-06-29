from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency may be absent before install
    load_dotenv = None


DEFAULT_REASON = "暂无智能推荐理由"
AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用，请稍后重试"
AI_TIMEOUT_MESSAGE = "AI 生成时间较长，请稍后重试或减少对比导师数量。"
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_ARK_MODEL = "doubao-seed-2-0-lite-260428"
TEST_SUCCESS_MESSAGE = "豆包 API 已成功接入"
DOUBAO_TIMEOUT = (10, 90)
DOUBAO_MAX_RETRIES = 1
DOUBAO_MAX_OUTPUT_TOKENS = 1500
DOUBAO_TEST_MAX_OUTPUT_TOKENS = 300
MAX_AREA_LENGTH = 160
ADVICE_AREA_LENGTH = 140

if load_dotenv:
    load_dotenv()


class ArkAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str = "",
        request_url: str = "",
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.request_url = request_url
        self.original = original


def _safe_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _truncate_text(value: object, limit: int = MAX_AREA_LENGTH) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _normalize_base_url(value: str) -> str:
    text = _safe_text(value)
    match = re.search(r"https?://[^\]\)\s]+", text)
    if match:
        text = match.group(0)
    return text.rstrip("/")


def _settings() -> tuple[str, str, str]:
    api_key = _safe_text(os.getenv("ARK_API_KEY"))
    model = _safe_text(os.getenv("ARK_MODEL")) or DEFAULT_ARK_MODEL
    base_url = _normalize_base_url(os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL)
    return api_key, model, base_url


def is_configured() -> bool:
    api_key, model, base_url = _settings()
    return bool(api_key and model and base_url)


def log_env_diagnostics() -> None:
    api_key, model, base_url = _settings()
    print(f"ARK_API_KEY loaded: {bool(api_key)}", flush=True)
    print(f"ARK_API_KEY length: {len(api_key)}", flush=True)
    print(f"ARK_MODEL: {model}", flush=True)
    print(f"ARK_BASE_URL: {base_url}", flush=True)


def log_ai_exception(error: Exception) -> None:
    if getattr(error, "_doubao_logged", False):
        return
    status_code = getattr(error, "status_code", None)
    response_text = getattr(error, "response_text", "")
    request_url = getattr(error, "request_url", "")
    original = getattr(error, "original", None)
    exception_type = type(original).__name__ if original else type(error).__name__

    print("Doubao API error diagnostics:", flush=True)
    print(f"Exception type: {exception_type}", flush=True)
    print(f"Exception message: {error}", flush=True)
    print(f"HTTP status code: {status_code}", flush=True)
    if response_text:
        print(f"Doubao response length: {len(response_text)}", flush=True)
    print(f"Request URL: {request_url}", flush=True)
    try:
        setattr(error, "_doubao_logged", True)
    except Exception:
        pass


def is_timeout_error(error: Exception) -> bool:
    original = getattr(error, "original", None)
    if isinstance(original, requests.exceptions.ReadTimeout):
        return True
    return isinstance(error, requests.exceptions.ReadTimeout)


def _responses_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/responses"


def _extract_text_from_response(data: Any) -> str:
    if isinstance(data, dict):
        item_type = _safe_text(data.get("type"))
        if item_type in {"reasoning", "summary", "summary_text"}:
            return ""
        if item_type in {"output_text", "text"}:
            return _safe_text(data.get("text"))

        output_text = _safe_text(data.get("output_text"))
        if output_text:
            return output_text

        text = _safe_text(data.get("text"))
        if text and item_type not in {"reasoning", "summary", "summary_text"}:
            return text

        content = data.get("content")
        if isinstance(content, str):
            return "" if item_type in {"reasoning", "summary", "summary_text"} else _safe_text(content)
        if isinstance(content, list):
            parts = [_extract_text_from_response(item) for item in content]
            return _safe_text("\n".join(part for part in parts if part))

        output = data.get("output")
        if isinstance(output, list):
            parts = [
                _extract_text_from_response(item)
                for item in output
                if not isinstance(item, dict) or _safe_text(item.get("type")) != "reasoning"
            ]
            text = "\n".join(part for part in parts if part)
            if _safe_text(text):
                return _safe_text(text)

        choices = data.get("choices")
        if isinstance(choices, list):
            parts = [_extract_text_from_response(item) for item in choices]
            text = "\n".join(part for part in parts if part)
            if _safe_text(text):
                return _safe_text(text)

        message = data.get("message")
        if isinstance(message, (dict, list, str)):
            return _extract_text_from_response(message)

    if isinstance(data, list):
        parts = [_extract_text_from_response(item) for item in data]
        return _safe_text("\n".join(part for part in parts if part))

    if isinstance(data, str):
        return _safe_text(data)

    return ""


def _status_and_reason(data: Any) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "", ""
    status = _safe_text(data.get("status"))
    reason = ""
    incomplete_details = data.get("incomplete_details")
    if isinstance(incomplete_details, dict):
        reason = _safe_text(incomplete_details.get("reason"))
    return status, reason


def call_doubao(
    prompt: str,
    max_output_tokens: int = DOUBAO_MAX_OUTPUT_TOKENS,
    *,
    allow_incomplete_with_text: bool = False,
    require_text: bool = True,
    print_raw_json: bool = False,
) -> str:
    api_key, model, base_url = _settings()
    request_url = _responses_url(base_url)
    if not api_key or not model or not base_url:
        raise ArkAPIError("AI service is not configured", request_url=request_url)

    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = None
    for attempt in range(DOUBAO_MAX_RETRIES + 1):
        try:
            response = requests.post(request_url, headers=headers, json=payload, timeout=DOUBAO_TIMEOUT)
            break
        except requests.exceptions.ReadTimeout as exc:
            if attempt < DOUBAO_MAX_RETRIES:
                print(f"Doubao API ReadTimeout, retrying once: attempt {attempt + 1}", flush=True)
                continue
            raise ArkAPIError(str(exc), request_url=request_url, original=exc) from exc
        except requests.RequestException as exc:
            raise ArkAPIError(str(exc), request_url=request_url, original=exc) from exc

    if response is None:
        raise ArkAPIError("Doubao API returned no response", request_url=request_url)

    if not response.ok:
        raise ArkAPIError(
            f"Doubao API returned HTTP {response.status_code}",
            status_code=response.status_code,
            response_text=response.text,
            request_url=request_url,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ArkAPIError(
            "Doubao API response is not valid JSON",
            status_code=response.status_code,
            response_text=response.text,
            request_url=request_url,
            original=exc,
        ) from exc

    if print_raw_json:
        print("Doubao raw response JSON:", flush=True)
        print(json.dumps(data, ensure_ascii=False), flush=True)

    content = _extract_text_from_response(data)
    content = _safe_text(content)

    status, reason = _status_and_reason(data)
    print(f"Doubao response status: {status or 'unknown'}", flush=True)
    print(f"Doubao incomplete reason: {reason or ''}", flush=True)
    print(f"Doubao final text length: {len(content)}", flush=True)

    if status == "incomplete" and not (allow_incomplete_with_text and content):
        if require_text:
            raise ArkAPIError(
                f"Doubao response incomplete: {reason or 'unknown'}",
                status_code=response.status_code,
                response_text=json.dumps(data, ensure_ascii=False),
                request_url=request_url,
            )
        return content

    if not content and require_text:
        print("Doubao response has no final answer text", flush=True)
        raise ArkAPIError(
            "Doubao response has no final answer text",
            status_code=response.status_code,
            response_text=json.dumps(data, ensure_ascii=False),
            request_url=request_url,
        )
    return content


def _post_responses(input_text: str, max_tokens: int = DOUBAO_MAX_OUTPUT_TOKENS, *, print_raw_json: bool = False) -> str:
    return call_doubao(
        input_text,
        max_output_tokens=max_tokens,
        allow_incomplete_with_text=False,
        require_text=True,
        print_raw_json=print_raw_json,
    )


def _messages_to_input(messages: list[dict[str, str]]) -> str:
    lines = []
    for message in messages:
        role = _safe_text(message.get("role")) or "user"
        content = _safe_text(message.get("content"))
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _chat(
    messages: list[dict[str, str]],
    max_tokens: int = DOUBAO_MAX_OUTPUT_TOKENS,
    *,
    allow_incomplete_with_text: bool = True,
) -> str:
    return call_doubao(
        _messages_to_input(messages),
        max_output_tokens=max_tokens,
        allow_incomplete_with_text=allow_incomplete_with_text,
        require_text=True,
    )


def test_doubao_connection() -> str:
    log_env_diagnostics()
    try:
        call_doubao(
            "只输出：豆包 API 已成功接入。不要解释，不要祝贺，不要扩展。",
            max_output_tokens=DOUBAO_TEST_MAX_OUTPUT_TOKENS,
            allow_incomplete_with_text=True,
            require_text=False,
            print_raw_json=False,
        )
    except Exception as exc:
        log_ai_exception(exc)
        raise
    return TEST_SUCCESS_MESSAGE


def _mentor_payload(mentor: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": _safe_text(mentor.get("id")),
        "name": _safe_text(mentor.get("name")),
        "title": _safe_text(mentor.get("title")),
        "school": _safe_text(mentor.get("school")),
        "province": _safe_text(mentor.get("province")),
        "college": _safe_text(mentor.get("college")),
        "area": _truncate_text(mentor.get("area") or mentor.get("research_area")),
        "score": mentor.get("score", 0),
    }
    return {key: value for key, value in payload.items() if value not in ("", None)}


def _mentor_advice_payload(mentor: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "name": _safe_text(mentor.get("name")),
        "title": _safe_text(mentor.get("title")),
        "school": _safe_text(mentor.get("school")),
        "province": _safe_text(mentor.get("province")),
        "college": _safe_text(mentor.get("college")),
        "area": _truncate_text(mentor.get("area") or mentor.get("research_area"), ADVICE_AREA_LENGTH),
        "score": mentor.get("score", 0),
    }
    return {key: value for key, value in payload.items() if value not in ("", None)}


def enrich_match_reasons(recommendations: list[dict], expected_direction: str, limit: int = 3) -> list[dict]:
    enriched = [dict(item) for item in recommendations]
    target_count = min(limit, len(enriched))
    if target_count == 0:
        return enriched

    for item in enriched[:target_count]:
        item["match_reason"] = DEFAULT_REASON

    if not is_configured():
        return enriched

    mentors = [_mentor_payload(item) for item in enriched[:target_count]]
    messages = [
        {
            "role": "system",
            "content": "你是研究生择导助手。只基于给定导师信息生成简洁、真实、谨慎的推荐理由，不编造论文、项目、头衔或院校信息。",
        },
        {
            "role": "user",
            "content": (
                "学生期望研究方向：" + _safe_text(expected_direction) + "\n"
                "请为每位导师生成一句不超过60字的推荐理由。"
                "返回严格 JSON 数组，每项包含 id 和 reason。导师信息："
                + json.dumps(mentors, ensure_ascii=False)
            ),
        },
    ]

    try:
        content = _chat(messages, max_tokens=500)
        parsed = json.loads(content)
        reason_by_id = {
            _safe_text(item.get("id")): _safe_text(item.get("reason"))
            for item in parsed
            if isinstance(item, dict)
        }
        for item in enriched[:target_count]:
            reason = reason_by_id.get(_safe_text(item.get("id")))
            item["match_reason"] = reason or DEFAULT_REASON
    except Exception:
        for item in enriched[:target_count]:
            item["match_reason"] = DEFAULT_REASON
    return enriched


def generate_compare_advice(mentors: list[dict]) -> str:
    payload = [_mentor_advice_payload(item) for item in mentors[:3]]
    messages = [
        {
            "role": "system",
            "content": "你是研究生择导助手。只输出最终建议，不输出思考过程或推理过程，不编造导师数据中没有的信息。",
        },
        {
            "role": "user",
            "content": (
                "请从适合学生选择导师的角度，对以下2-3位导师给出200到300字的对比建议。"
                "只输出最终建议，不要解释推理过程，不要输出思考过程。"
                "请包含：各自适合的研究兴趣、选择优先级、联系准备。"
                "导师信息只包含 name、title、school、province、college、area、score："
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]
    return _chat(messages, max_tokens=DOUBAO_MAX_OUTPUT_TOKENS, allow_incomplete_with_text=True)


def generate_favorite_advice(mentors: list[dict]) -> str:
    payload = [_mentor_advice_payload(item) for item in mentors[:3]]
    messages = [
        {
            "role": "system",
            "content": "你是研究生择导助手。只输出最终建议，不输出思考过程或推理过程，不编造导师数据中没有的信息。",
        },
        {
            "role": "user",
            "content": (
                "请从学生择师角度，基于以下2-3位心仪导师给出200到300字建议。"
                "只输出最终建议，不要解释推理过程，不要输出思考过程。"
                "请包含：优先联系顺序、适合的研究方向、联系前准备、需要确认的问题。"
                "导师信息只包含 name、title、school、province、college、area、score："
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]
    return _chat(messages, max_tokens=DOUBAO_MAX_OUTPUT_TOKENS, allow_incomplete_with_text=True)
