"""theme_engine.py의 순수 로직·콘텐츠 매핑 동작 테스트 (LLM/네트워크 호출 없음)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

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


# ── 신규 수집분 매핑 (작은 고정 풀로 결정적 검증) ────────────────

def _use_fixed_pool(monkeypatch, scraped):
    """contents.csv·월별 방향을 고정 값으로 바꿔 매핑 결과를 결정적으로 만든다.

    기존 풀만으로 min_count가 채워지도록 넉넉히 둔다. 풀이 min_count보다 작으면
    match_contents 말미의 '부족하면 채움' 경로가 신규분을 주워버려서, 정작
    본 후보 선별에서 신규가 탈락하는 문제를 테스트가 놓친다.
    점수는 제목에서만 나오도록 cat·tags는 비워 둔다.
    """
    pool = pd.DataFrame({
        "type": ["아티클"] * 4 + ["영상"] * 4,
        "title": [
            "조직 이야기 하나", "조직 이야기 둘", "팀 이야기 하나", "팀 이야기 둘",
            "조직 영상 하나", "조직 영상 둘", "팀 영상 하나", "팀 영상 둘",
        ],
        "cat": [""] * 8,
        "tags": [""] * 8,
    })
    monkeypatch.setattr(te, "_load_contents_df", lambda: pool.copy())
    monkeypatch.setattr(te, "_get_monthly_direction", lambda: ("8", "조직 문화와 팀 결속"))
    orig_load = te._load_json
    monkeypatch.setattr(
        te, "_load_json",
        lambda path, default: scraped if path == te.SCRAPED_CONTENTS_PATH else orig_load(path, default),
    )


# 방향 "조직 문화와 팀 결속" → 그룹 토큰 {조직,문화} / {팀,결속}.
# 신규 제목은 두 토큰을 모두 담아 점수 2, 기존 풀은 1이 되게 해서
# 순위상 신규가 반드시 앞서도록 만든다.
_SCRAPED_TOP = ["신규 조직 문화 정리", "신규 팀 결속 정리"]


def test_match_contents_includes_scraped_new_contents(monkeypatch):
    """매일 수집한 신규 콘텐츠도 아티클/영상과 동일하게 추천 후보에 오른다"""
    _use_fixed_pool(monkeypatch, _SCRAPED_TOP)

    res = te.match_contents("조직문화", min_count=4)

    titles = [c["title"] for c in res]
    assert set(_SCRAPED_TOP) <= set(titles), f"신규 수집분이 누락됨: {titles}"


def test_match_contents_applies_excluded_filter_to_scraped(monkeypatch):
    """신규 수집분에도 제외 키워드 필터가 그대로 적용된다"""
    scraped = ["[AI몬데이] 신규 조직 문화 정리", "신규 팀 결속 정리"]
    _use_fixed_pool(monkeypatch, scraped)

    res = te.match_contents("조직문화", min_count=4)

    titles = [c["title"] for c in res]
    assert "[AI몬데이] 신규 조직 문화 정리" not in titles
    assert "신규 팀 결속 정리" in titles


def test_match_contents_scores_title_only(monkeypatch):
    """태그·카테고리는 채점에서 무시하고 제목만으로 관련성을 판단한다"""
    pool = pd.DataFrame({
        "type": ["아티클", "영상"],
        # 첫 항목은 태그만 방향과 일치하고 제목은 무관 — 제목만 보면 0점이라 탈락해야 한다
        "title": ["봄맞이 등산 후기", "조직 문화 이야기"],
        "cat": ["조직", ""],
        "tags": ["#조직문화#팀결속", ""],
    })
    monkeypatch.setattr(te, "_load_contents_df", lambda: pool.copy())
    monkeypatch.setattr(te, "_get_monthly_direction", lambda: ("8", "조직 문화와 팀 결속"))
    orig_load = te._load_json
    monkeypatch.setattr(
        te, "_load_json",
        lambda path, default: [] if path == te.SCRAPED_CONTENTS_PATH else orig_load(path, default),
    )

    res = te.match_contents("조직문화", min_count=1)

    assert [c["title"] for c in res] == ["조직 문화 이야기"]


def test_match_contents_ranks_newest_first_on_tie(monkeypatch):
    """점수가 같으면 더 최신인 수집분이 기존 카탈로그보다 앞선다"""
    # 신규·기존 모두 토큰 1개씩만 담아 동점(1점)을 만든다
    _use_fixed_pool(monkeypatch, ["예전 수집 조직 소식", "최근 수집 조직 소식"])

    res = te.match_contents("조직문화", min_count=2)

    titles = [c["title"] for c in res]
    assert "최근 수집 조직 소식" in titles, f"동점인데 신규가 밀림: {titles}"


def test_match_contents_keeps_catalog_type_for_duplicates(monkeypatch):
    """카탈로그에 이미 있는 제목이 수집분에도 있으면 원래 타입(아티클/영상)을 유지한다"""
    # 스크래퍼는 contents.csv와 대조하지 않아 목록 페이지의 기존 콘텐츠도 다시 담는다
    _use_fixed_pool(monkeypatch, ["조직 이야기 하나"])

    res = te.match_contents("조직문화", min_count=5)

    dup = [c for c in res if c["title"] == "조직 이야기 하나"]
    assert len(dup) == 1, "중복 제목이 두 슬롯을 차지하면 안 됨"
    assert dup[0]["type"] == "아티클", f"카탈로그 타입을 잃음: {dup[0]['type']}"


def test_match_contents_without_scraped_still_fills(monkeypatch):
    """수집분이 하나도 없으면 슬롯 없이 기존 풀로만 min_count를 채운다"""
    _use_fixed_pool(monkeypatch, [])

    res = te.match_contents("조직문화", min_count=5)

    assert len(res) == 5
    assert all(c["type"] in ("아티클", "영상") for c in res)


def test_get_direction_falls_back():
    assert isinstance(te.get_direction(7), str)
    assert te.get_direction(999) == "리더십 역량 개발"  # 없는 월은 기본값
