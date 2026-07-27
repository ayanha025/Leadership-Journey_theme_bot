"""theme_engine.py의 순수 로직·콘텐츠 매핑 동작 테스트 (LLM/네트워크 호출 없음)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import theme_engine as te


# ── 제외/계절 필터 ────────────────────────────────────────────────

def test_excluded_title_catches_monday_variants():
    assert te._is_excluded_title("[AI몬데이] 협상의 기술")
    assert te._is_excluded_title("[AI 몬데이] 협상의 기술")  # 띄어쓰기 변형도
    assert not te._is_excluded_title("평범한 리더십 제목")


def test_seasonal_mismatch():
    assert te._is_seasonal_mismatch("연말 결산 리더십", 7) is True   # 7월엔 '연말' 부적합
    assert te._is_seasonal_mismatch("연말 결산 리더십", 12) is False  # 12월엔 적합
    assert te._is_seasonal_mismatch("연초 계획 세우기", 2) is False   # 2월엔 '연초' 적합
    assert te._is_seasonal_mismatch("평범한 제목", 7) is False


def test_parse_direction_groups_splits_on_separators():
    groups = te._parse_direction_groups("성과 관리와 신뢰 구축·소통")
    assert "성과 관리" in groups   # '성과'의 과는 복합어라 분리 안 됨
    assert "신뢰 구축" in groups
    assert "소통" in groups


# ── 콘텐츠 매핑 (실제 contents.csv 사용) ──────────────────────────

def test_get_content_keywords_nonempty():
    kw = te._get_content_keywords()
    assert isinstance(kw, str) and len(kw) > 0


def test_match_contents_returns_requested_count():
    res = te.match_contents("리더십", min_count=5)
    assert len(res) == 5
    assert all("title" in c and "type" in c for c in res)


def test_match_contents_is_deterministic():
    a = te.match_contents("성과", min_count=5)
    b = te.match_contents("성과", min_count=5)
    assert [c["title"] for c in a] == [c["title"] for c in b]


def test_match_contents_excludes_excluded_keywords():
    res = te.match_contents("리더십", min_count=8)
    assert all(not te._is_excluded_title(str(c["title"])) for c in res)


def test_match_contents_excludes_used_titles():
    used = te._get_used_content_titles()
    res = te.match_contents("리더십", min_count=8)
    assert all(str(c["title"]) not in used for c in res)


def test_get_direction_falls_back():
    assert isinstance(te.get_direction(7), str)
    assert te.get_direction(999) == "리더십 역량 개발"  # 없는 월은 기본값
