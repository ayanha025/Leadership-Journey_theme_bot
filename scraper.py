"""
leadership.hunet.co.kr에서 신규 콘텐츠와 신규 테마를 수집해 누적 저장
"""
import json
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# 가변 상태는 STORAGE_DIR(재배포에도 유지되는 볼륨 경로)에 저장한다. app.py·theme_engine.py와 동일 규칙.
STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")
SCRAPED_CONTENTS_PATH = os.getenv("SCRAPED_CONTENTS_PATH") or os.path.join(STORAGE_DIR, "scraped_contents.json")
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH") or os.path.join(STORAGE_DIR, "theme_history.json")
THEME_HISTORY_SEED_PATH = os.getenv("THEME_HISTORY_SEED_PATH", "data/theme_history_seed.json")
CONTENT_HISTORY_SEED_PATH = os.getenv("CONTENT_HISTORY_SEED_PATH", "data/content_history_seed.json")
HUNET_SESSION_COOKIE = os.getenv("HUNET_SESSION_COOKIE", "")

CONTENT_URL = "https://leadership.hunet.co.kr/journey/library?keyword_cd=CK92"
THEME_URL = "https://leadership.hunet.co.kr/journey/library/theme/86"

UI_TEXTS = {
    "리더십저니", "리더십 라이브러리", "리더스 라운지",
    "전체", "아티클", "영상", "테마", "검색", "라이브러리"
}


def _get_session():
    s = requests.Session()
    if HUNET_SESSION_COOKIE:
        s.headers.update({"Cookie": HUNET_SESSION_COOKIE})
    return s


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scrape_new_contents():
    """신규 콘텐츠 제목 수집 후 scraped_contents.json에 신규 항목만 추가"""
    scraped_existing = _load_json(SCRAPED_CONTENTS_PATH, [])
    all_seen = set(scraped_existing) | set(_load_json(CONTENT_HISTORY_SEED_PATH, []))
    warning = None

    try:
        s = _get_session()
        resp = s.get(CONTENT_URL, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        titles = []
        for el in soup.select(".content-title, .item-title, h3, h4")[:20]:
            t = el.get_text(strip=True)
            if t and len(t) > 4 and t not in UI_TEXTS:
                titles.append(t)
            if len(titles) >= 12:
                break

        new_titles = [t for t in titles if t not in all_seen]
        if new_titles:
            updated = scraped_existing + new_titles
            _save_json(SCRAPED_CONTENTS_PATH, updated)
            print(f"신규 콘텐츠 {len(new_titles)}개 저장")
        else:
            print("신규 콘텐츠 없음 (저장 생략)")

    except Exception as e:
        warning = f"콘텐츠 스크래핑 실패: {e}"
        print(warning)

    return warning


def scrape_new_themes():
    """신규 테마명 수집 후 theme_history.json에 신규 항목만 추가"""
    theme_existing = _load_json(THEME_HISTORY_PATH, [])
    all_seen = set(theme_existing) | set(_load_json(THEME_HISTORY_SEED_PATH, []))
    warning = None

    try:
        s = _get_session()
        resp = s.get(THEME_URL, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        page_themes = []
        for h2 in soup.find_all("h2"):
            t = h2.get_text(strip=True)
            if len(t) >= 8 and t not in UI_TEXTS:
                page_themes.append(t)

        new_themes = [t for t in page_themes if t not in all_seen]
        if new_themes:
            updated = theme_existing + new_themes
            _save_json(THEME_HISTORY_PATH, updated)
            print(f"신규 테마 {len(new_themes)}개 저장")
        else:
            print("신규 테마 없음 (저장 생략)")

    except Exception as e:
        warning = f"테마 스크래핑 실패: {e}"
        print(warning)

    return warning


def run_scraping():
    """두 스크래핑 모두 실행, 경고 메시지 목록 반환"""
    warnings = []
    w1 = scrape_new_contents()
    w2 = scrape_new_themes()
    if w1:
        warnings.append(w1)
    if w2:
        warnings.append(w2)
    return warnings
