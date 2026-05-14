import json
import pytest
from unittest.mock import patch, MagicMock
import content_engine


# ── Phase 1: 날짜 & 프롬프트 ─────────────────────────────────

def test_build_dates_format():
    today_str, start_str, end_str = content_engine.build_dates()
    assert len(today_str) == 10 and today_str[4] == "-" and today_str[7] == "-"
    assert start_str < today_str


def test_build_article_prompt_contains_dates():
    today_str, start_str, _ = content_engine.build_dates()
    prompt = content_engine.build_article_prompt([])
    assert today_str in prompt
    assert start_str in prompt


def test_build_article_prompt_excludes_keywords():
    prompt = content_engine.build_article_prompt(["초격차", "심리적 안전감"])
    assert "초격차" in prompt
    assert "반드시 제외" in prompt


def test_build_article_prompt_no_exclude_when_empty():
    assert "반드시 제외" not in content_engine.build_article_prompt([])


def test_build_series_prompt_has_series_schema():
    prompt = content_engine.build_series_prompt([])
    assert "seriesTitle" in prompt
    assert "episodes" in prompt


def test_build_series_prompt_excludes_keywords():
    prompt = content_engine.build_series_prompt(["테스트키워드"])
    assert "테스트키워드" in prompt
    assert "반드시 제외" in prompt


# ── Phase 2: API 호출 & 파싱 ──────────────────────────────────

def _mock_response(content: str):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock


def test_call_openrouter_returns_content():
    with patch("requests.post", return_value=_mock_response('[{"keyword":"테스트"}]')):
        result = content_engine.call_openrouter("prompt", "fake-key", "perplexity/sonar-pro")
    assert result == '[{"keyword":"테스트"}]'


def test_call_openrouter_raises_on_error():
    mock = MagicMock()
    mock.status_code = 401
    mock.text = "Unauthorized"
    with patch("requests.post", return_value=mock):
        with pytest.raises(RuntimeError, match="OpenRouter API 오류"):
            content_engine.call_openrouter("prompt", "bad-key", "perplexity/sonar-pro")


def test_parse_articles_valid():
    raw = json.dumps([{
        "keyword": "초격차", "category": "경영", "title": "초격차 전략",
        "description": "설명", "implications": ["시사점1"],
        "source": "HBR", "sourceUrl": "https://hbr.org", "sourceDate": "2026-05"
    }])
    result = content_engine.parse_articles(raw)
    assert result[0]["keyword"] == "초격차"


def test_parse_articles_strips_markdown_fence():
    raw = '```json\n[{"keyword":"테스트","category":"경영","title":"T","description":"D","implications":[],"source":"S","sourceUrl":"","sourceDate":"2026-05"}]\n```'
    assert content_engine.parse_articles(raw)[0]["keyword"] == "테스트"


def test_parse_articles_raises_on_invalid():
    with pytest.raises(ValueError, match="JSON 파싱 실패"):
        content_engine.parse_articles("이건 JSON이 아닙니다")


def test_parse_series_valid():
    raw = json.dumps([{
        "keyword": "초격차", "category": "경영", "seriesTitle": "초격차 시리즈",
        "description": "기획 의도",
        "episodes": [{"title": "1회차", "desc": "설명"}, {"title": "2회차", "desc": "설명"}],
        "source": "McKinsey", "sourceUrl": "", "sourceDate": "2026-05"
    }])
    result = content_engine.parse_series(raw)
    assert result[0]["seriesTitle"] == "초격차 시리즈"
    assert len(result[0]["episodes"]) == 2


# ── Phase 3: Slack 블록 포맷 ──────────────────────────────────

_ARTICLES = [{"keyword": f"키워드{i}", "category": "경영", "title": f"제목{i}",
               "description": "설명", "implications": [],
               "source": "HBR", "sourceUrl": "https://hbr.org", "sourceDate": "2026-05"}
             for i in range(7)]

_SERIES = [{"keyword": f"키워드{i}", "category": "경영", "seriesTitle": f"시리즈{i}",
             "description": "기획 의도",
             "episodes": [{"title": f"{j}회차", "desc": "설명"} for j in range(1, 5)],
             "source": "McKinsey", "sourceUrl": "", "sourceDate": "2026-05"}
           for i in range(7)]


def test_format_article_blocks_has_actions():
    blocks = content_engine.format_article_blocks(_ARTICLES, "2026-05-14")
    actions = next(b for b in blocks if b["type"] == "actions")
    ids = [e.get("action_id") for e in actions["elements"]]
    assert "regenerate_article" in ids
    assert "confirm_article" in ids
    assert "select_article" in ids


def test_format_article_blocks_dropdown_has_7_options():
    blocks = content_engine.format_article_blocks(_ARTICLES, "2026-05-14")
    actions = next(b for b in blocks if b["type"] == "actions")
    dropdown = next(e for e in actions["elements"] if e["type"] == "static_select")
    assert len(dropdown["options"]) == 7


def test_format_series_blocks_has_actions():
    blocks = content_engine.format_series_blocks(_SERIES, "2026-05-14")
    actions = next(b for b in blocks if b["type"] == "actions")
    ids = [e.get("action_id") for e in actions["elements"]]
    assert "regenerate_series" in ids
    assert "confirm_series" in ids
    assert "select_series" in ids


def test_format_series_blocks_dropdown_has_7_options():
    blocks = content_engine.format_series_blocks(_SERIES, "2026-05-14")
    actions = next(b for b in blocks if b["type"] == "actions")
    dropdown = next(e for e in actions["elements"] if e["type"] == "static_select")
    assert len(dropdown["options"]) == 7
