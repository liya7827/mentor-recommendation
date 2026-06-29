from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
FAVORITES = ROOT / "favorites.html"
APP_JS = ROOT / "js" / "app.js"
FAVORITES_JS = ROOT / "js" / "favorites.js"


def read_frontend():
    return (
        INDEX.read_text(encoding="utf-8"),
        FAVORITES.read_text(encoding="utf-8"),
        APP_JS.read_text(encoding="utf-8"),
        FAVORITES_JS.read_text(encoding="utf-8"),
    )


def test_search_page_uses_three_input_fields_and_two_regions():
    index, _, js, _ = read_frontend()

    assert 'id="provinceInput"' in index
    assert '<option value="南京">南京</option>' in index
    assert '<option value="云南">云南</option>' in index
    assert "北京" not in index
    assert "上海" not in index
    assert "广东" not in index
    assert "学校层次" not in index
    assert "985" not in index
    assert "211" not in index
    assert "tierInput" not in index
    assert "tier:" not in js
    assert "expected_direction" in js


def test_favorites_are_moved_to_independent_page():
    index, favorites, js, favorites_js = read_frontend()

    assert 'href="favorites.html"' in index
    assert "favoriteMentorsContainer" not in index
    assert "btnFavoriteAdvice" not in index
    assert "心仪导师" in favorites
    assert "favoriteMentorsContainer" in favorites
    assert "暂未添加心仪导师，请先从推荐结果中选择。" in favorites_js
    assert "removeFavorite" in favorites_js


def test_favorites_use_local_storage_and_dedupe():
    _, _, js, favorites_js = read_frontend()
    combined = js + favorites_js

    assert 'FAVORITES_KEY = "favoriteMentors"' in combined
    assert "localStorage.getItem(FAVORITES_KEY)" in combined
    assert "localStorage.setItem(FAVORITES_KEY" in combined
    assert "dedupeMentors" in combined
    assert "seen.has(key)" in combined


def test_favorites_page_selects_two_or_three_for_ai_advice():
    _, _, _, favorites_js = read_frontend()

    assert "selectedIds.size >= 3" in favorites_js
    assert "请选择 2-3 位心仪导师生成 AI 择师建议" in favorites_js
    assert "AI_FAVORITES_URL" in favorites_js
    assert "toAiMentorPayload" in favorites_js
    assert "mentors.slice(0, 3).map(toAiMentorPayload)" in favorites_js


def test_compare_stays_on_search_page_and_is_limited_to_three():
    index, _, js, _ = read_frontend()

    assert "btnShowCompare" in index
    assert "btnCompareAdvice" in index
    assert "compareAdviceBox" in index
    assert 'data-action="toggle-compare"' in js
    assert "compareList.length >= 3" in js
    assert "最多只能同时对比 3 位导师" in js
    assert "AI_COMPARE_URL" in js


def test_ai_controls_and_failure_message_are_present():
    index, favorites, js, favorites_js = read_frontend()
    combined = index + favorites + js + favorites_js

    assert "AI 推荐理由" in js
    assert "生成 AI 对比建议" in index
    assert "生成 AI 择师建议" in favorites
    assert "AI 服务暂时不可用，请稍后重试" in combined
    assert "AI 生成时间较长，请稍后重试或减少对比导师数量。" in combined
    assert "AI 正在生成，请稍候..." in combined
    assert "spinner-border" in combined


def test_ai_requests_send_compact_fields_only():
    _, _, js, favorites_js = read_frontend()
    combined = js + favorites_js
    payload_sections = "\n".join(part.split("};", 1)[0] for part in combined.split("function toAiMentorPayload")[1:])

    assert "toAiMentorPayload" in combined
    assert "name: safeText(mentor.name)" in payload_sections
    assert "title: safeText(mentor.title)" in payload_sections
    assert "school: safeText(mentor.school)" in payload_sections
    assert "province: safeText(mentor.province)" in payload_sections
    assert "college: safeText(mentor.college)" in payload_sections
    assert "area: safeText(mentor.area).slice(0, 180)" in payload_sections
    assert "email:" not in payload_sections
    assert "homepage_url:" not in payload_sections


def test_frontend_does_not_expose_api_key():
    combined = "".join(read_frontend())

    assert "ARK_API_KEY" not in combined
    assert "ARK_MODEL" not in combined
    assert "ARK_BASE_URL" not in combined
    assert "doubao" not in combined.lower()


def test_frontend_removed_unused_fields_and_mock_data():
    combined = "".join(read_frontend())

    assert "major" not in combined
    assert "pub" not in combined
    assert "tier" not in combined
    assert "Mock" not in combined
    assert "setTimeout" not in combined
