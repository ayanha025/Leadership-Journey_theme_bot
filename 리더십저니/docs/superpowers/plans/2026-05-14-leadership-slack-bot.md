# 리더십저니 테마 자동화 Slack 봇 구현 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slack DM에서 "테마발송" 입력 시 해당 월 기획 방향 기반으로 테마 키워드 1개 + 4가지 스타일 제목 20개 + 추천 콘텐츠 5개 이상을 자동 생성해 발송한다.

**Architecture:** Slack Bolt(Socket Mode) 앱이 메시지/커맨드 이벤트를 수신 → scraper.py로 신규 콘텐츠/테마를 수집 저장 → theme_engine.py가 OpenRouter API를 호출해 기획안 생성 → 콘텐츠 키워드 매칭 후 DM 발송. 재생성 버튼으로 반복 가능, 확정 버튼으로 theme_history.json에 저장.

**Tech Stack:** Python 3, slack-bolt, requests, BeautifulSoup4, pandas, OpenRouter API

**Spec:** `docs/superpowers/specs/2026-05-14-leadership-slack-bot-design.md`

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| `app.py` | Slack Bolt 앱 진입점. 이벤트 리스너, 버튼 핸들러, 세션 관리 |
| `theme_engine.py` | OpenRouter API 호출, 응답 파싱, 콘텐츠 키워드 매칭, 월별 방향 로드 |
| `scraper.py` | hunet.co.kr 스크래핑, 중복 제거 후 JSON 저장 |
| `init_theme_history.py` | XLS에서 기발행 86개 테마 추출 → theme_history.json 초기화 (1회) |
| `prepare_data.py` | 기존 코드 유지 (XLS → contents.csv) |
| `data/monthly_direction.json` | 12개월 기획 방향 (수동 작성) |
| `data/theme_history.json` | 기발행 + 확정 테마 금지목록 |
| `data/scraped_contents.json` | 웹 수집 신규 콘텐츠 누적본 |
| `.env` | 환경변수 |
| `requirements.txt` | 패키지 목록 |

---

## Task 1: 프로젝트 환경 설정

**Files:**
- Create: `/Users/hunet/Desktop/slack bot/requirements.txt`
- Create: `/Users/hunet/Desktop/slack bot/.env.example`
- Create: `/Users/hunet/Desktop/slack bot/data/monthly_direction.json`

- [ ] **Step 1: requirements.txt 작성**

```
slack-bolt>=1.18.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
python-dotenv>=1.0.0
openpyxl>=3.1.0
xlrd>=2.0.1
```

- [ ] **Step 2: .env.example 작성**

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet
TARGET_USER_ID=U0B2065SZ8B
CONTENT_CSV_PATH=data/contents.csv
SCRAPED_CONTENTS_PATH=data/scraped_contents.json
THEME_HISTORY_PATH=data/theme_history.json
MONTHLY_DIRECTION_PATH=data/monthly_direction.json
HUNET_SESSION_COOKIE=...
```

- [ ] **Step 3: monthly_direction.json 초기 데이터 작성**

```json
{
  "1": "새해 목표 설정과 리더십 비전 수립",
  "2": "관계 회복과 팀 신뢰 구축",
  "3": "변화 적응과 성장 마인드셋",
  "4": "성과 관리와 피드백 문화",
  "5": "리더 정체성 · 심리적 안전감 · 실무 역량 심화",  // 실제 5월 기획 방향 (사용자 확인값)
  "6": "중간 점검과 동기부여",
  "7": "여름 리더십 - 번아웃 예방",
  "8": "조직 문화와 팀 결속",
  "9": "하반기 전략과 실행력",
  "10": "갈등 해결과 의사결정",
  "11": "연말 성과 회고와 인정",
  "12": "한 해 마무리와 리더십 성찰"
}
```

- [ ] **Step 4: 패키지 설치 확인**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
pip install -r requirements.txt
```

Expected: 모든 패키지 설치 완료 또는 already satisfied

- [ ] **Step 5: 커밋**

```bash
git init
git add requirements.txt .env.example data/monthly_direction.json
git commit -m "feat: project setup and initial data files"
```

---

## Task 2: init_theme_history.py — 기발행 테마 초기화

**Files:**
- Create: `/Users/hunet/Desktop/slack bot/init_theme_history.py`

XLS의 volume 컬럼(예: "No.42 심리적 안전감")에서 테마명만 추출해 theme_history.json을 생성한다.

- [ ] **Step 1: init_theme_history.py 작성**

```python
"""
XLS 아티클 파일에서 기발행 테마명을 추출해 theme_history.json 초기화
실행: python init_theme_history.py --xls data/아티클.xls
"""
import argparse
import json
import re
import os
from bs4 import BeautifulSoup


UI_TEXTS = {
    "리더십저니", "리더십 라이브러리", "리더스 라운지",
    "전체", "아티클", "영상", "테마", "검색"
}


def extract_theme_names(xls_path):
    with open(xls_path, "r", encoding="utf-8") as f:
        content = f.read()
    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    themes = []
    seen = set()
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) > 8:
            volume_text = cells[8].get_text(strip=True)
            # "No.42 심리적 안전감" 형태에서 테마명 추출
            match = re.search(r'No\.\d+\s+(.+)', volume_text)
            if match:
                name = match.group(1).strip()
                if name and len(name) >= 4 and name not in UI_TEXTS and name not in seen:
                    themes.append(name)
                    seen.add(name)
    return themes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xls", required=True, help="아티클 XLS 파일 경로")
    parser.add_argument("--output", default="data/theme_history.json")
    args = parser.parse_args()

    themes = extract_theme_names(args.xls)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(themes, f, ensure_ascii=False, indent=2)

    print(f"완료: {len(themes)}개 테마 -> {args.output}")
    for t in themes[:5]:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행 및 확인**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
python init_theme_history.py --xls "리더십저니 아티클 리스트260507151019.xls"
```

Expected: `완료: 86개 테마 -> data/theme_history.json` (수량은 실제 XLS에 따라 다를 수 있음)

- [ ] **Step 3: 생성된 JSON 내용 확인**

```bash
python -c "import json; d=json.load(open('data/theme_history.json')); print(len(d), '개'); print(d[:3])"
```

Expected: 리스트 형태로 테마명 출력

- [ ] **Step 4: 커밋**

```bash
git add init_theme_history.py
git commit -m "feat: add init_theme_history.py to extract 86 existing themes from XLS"
```

---

## Task 3: scraper.py — 신규 콘텐츠·테마 수집

**Files:**
- Create: `/Users/hunet/Desktop/slack bot/scraper.py`

- [ ] **Step 1: scraper.py 작성**

```python
"""
leadership.hunet.co.kr에서 신규 콘텐츠와 신규 테마를 수집해 누적 저장
"""
import json
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SCRAPED_CONTENTS_PATH = os.getenv("SCRAPED_CONTENTS_PATH", "data/scraped_contents.json")
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH", "data/theme_history.json")
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
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scrape_new_contents():
    """신규 콘텐츠 제목 수집 후 scraped_contents.json에 신규 항목만 추가"""
    existing = set(_load_json(SCRAPED_CONTENTS_PATH, []))
    warning = None

    try:
        s = _get_session()
        resp = s.get(CONTENT_URL, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 상단 12개 콘텐츠 제목 수집 (사이트 구조에 따라 selector 조정 필요)
        titles = []
        for el in soup.select(".content-title, .item-title, h3, h4")[:20]:
            t = el.get_text(strip=True)
            if t and len(t) > 4 and t not in UI_TEXTS:
                titles.append(t)
            if len(titles) >= 12:
                break

        new_titles = [t for t in titles if t not in existing]
        if new_titles:
            updated = list(existing) + new_titles
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
    existing = set(_load_json(THEME_HISTORY_PATH, []))
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

        new_themes = [t for t in page_themes if t not in existing]
        if new_themes:
            updated = list(existing) + new_themes
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
```

- [ ] **Step 2: 단독 실행 테스트**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
python -c "from scraper import run_scraping; run_scraping()"
```

Expected: 스크래핑 결과 출력 (쿠키 미설정 시 실패 메시지 + 계속 진행)

- [ ] **Step 3: 커밋**

```bash
git add scraper.py
git commit -m "feat: add scraper.py for incremental content and theme collection"
```

---

## Task 4: theme_engine.py — 테마 생성 및 콘텐츠 매칭

**Files:**
- Create: `/Users/hunet/Desktop/slack bot/theme_engine.py`

- [ ] **Step 1: theme_engine.py 작성**

```python
"""
OpenRouter API로 테마 키워드 + 제목 20개 생성, 콘텐츠 풀에서 관련 항목 선별
"""
import json
import os
import re
from datetime import datetime
from collections import Counter

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-5-sonnet")
CONTENT_CSV_PATH = os.getenv("CONTENT_CSV_PATH", "data/contents.csv")
SCRAPED_CONTENTS_PATH = os.getenv("SCRAPED_CONTENTS_PATH", "data/scraped_contents.json")
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH", "data/theme_history.json")
MONTHLY_DIRECTION_PATH = os.getenv("MONTHLY_DIRECTION_PATH", "data/monthly_direction.json")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """당신은 리더십 교육 콘텐츠 큐레이터입니다.
주어진 월별 기획 방향에서 핵심 키워드 하나를 선정하고,
그 키워드를 주제로 4가지 스타일별 5개씩 총 20개 제목을 생성합니다.

규칙:
- keyword: 월별 기획 방향에서 선정한 핵심 주제 키워드 (10자 이내)
- 각 스타일별 5개, 총 20개 제목 생성
- 각 제목은 20자 이내
- 금지 목록의 키워드와 주제가 중복되지 않도록 할 것
- 반드시 아래 JSON 형식만 출력 (설명 없이)

스타일 정의:
- youtube: 직관적이고 클릭을 유도하는 제목 (예: 팀원 마음이 닫히는 순간)
- educational: 학습 목적이 명확한 제목 (예: 심리적 안전감 구축 실천법)
- meme: 가볍고 재미있는 밈/유행어 스타일 (예: 팀원 신뢰 레벨 MAX 찍기)
- aggro: 불편하지만 공감되는 어그로성 제목 (예: 그 결정이 팀을 망치고 있습니다)

출력 형식:
{
  "keyword": "선정된 핵심 키워드",
  "youtube": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "educational": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "meme": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "aggro": ["제목1", "제목2", "제목3", "제목4", "제목5"]
}"""


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _get_monthly_direction():
    month = str(datetime.now().month)
    directions = _load_json(MONTHLY_DIRECTION_PATH, {})
    return month, directions.get(month, "리더십 역량 개발")


def _get_forbidden_list(extra_keywords=None):
    history = _load_json(THEME_HISTORY_PATH, [])
    if extra_keywords:
        history = history + extra_keywords
    return history


def _get_content_keywords():
    """contents.csv에서 tags/cat 상위 빈도 키워드 50개 추출"""
    if not os.path.exists(CONTENT_CSV_PATH):
        return ""
    df = pd.read_csv(CONTENT_CSV_PATH)
    words = []
    for col in ["tags", "cat"]:
        if col in df.columns:
            for val in df[col].dropna():
                words.extend(str(val).split())
    top = [w for w, _ in Counter(words).most_common(50) if len(w) >= 2]
    return " ".join(top)


def _call_openrouter(user_prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_response(text):
    """JSON 블록 추출 및 키 검증"""
    clean = re.sub(r"```json|```", "", text).strip()
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if not match:
        raise ValueError("JSON 블록을 찾을 수 없습니다")
    result = json.loads(match.group(0))
    required = {"keyword", "youtube", "educational", "meme", "aggro"}
    if not required.issubset(result.keys()):
        raise ValueError(f"필수 키 누락: {required - result.keys()}")
    for key in ["youtube", "educational", "meme", "aggro"]:
        if not isinstance(result[key], list) or len(result[key]) < 5:
            raise ValueError(f"{key} 항목이 5개 미만입니다")
    return result


def generate_theme(extra_forbidden=None):
    """
    OpenRouter API를 호출해 테마 기획안 생성
    Returns: {"keyword": str, "youtube": [...], "educational": [...], "meme": [...], "aggro": [...]}
    """
    month, direction = _get_monthly_direction()
    forbidden = _get_forbidden_list(extra_forbidden)
    keywords_sample = _get_content_keywords()

    user_prompt = (
        f"이번 달({month}월) 기획 방향: {direction}\n\n"
        f"금지 키워드/주제 목록 ({len(forbidden)}개):\n"
        + "\n".join(f"- {t}" for t in forbidden)
        + f"\n\n콘텐츠 풀 주요 키워드:\n{keywords_sample}\n\n"
        "위 조건에 맞는 테마 기획안을 JSON으로 생성하세요."
    )

    for attempt in range(2):
        try:
            raw = _call_openrouter(user_prompt)
            return _parse_response(raw)
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"테마 생성 실패 (2회 시도): {e}")


def match_contents(keyword, min_count=5):
    """
    keyword 토큰과 contents.csv의 tags+cat+title 겹침으로 점수 계산,
    아티클/영상 혼합 min_count개 이상 반환
    """
    df = pd.read_csv(CONTENT_CSV_PATH)

    # 스크래핑된 신규 콘텐츠 제목도 포함 (title만 있음)
    scraped = _load_json(SCRAPED_CONTENTS_PATH, [])
    if scraped:
        extras = pd.DataFrame({"type": ["신규"] * len(scraped), "title": scraped,
                                "cat": [""] * len(scraped), "tags": [""] * len(scraped)})
        df = pd.concat([df, extras], ignore_index=True)

    tokens = set(keyword.split())

    def score(row):
        text = " ".join([
            str(row.get("tags", "") or ""),
            str(row.get("cat", "") or ""),
            str(row.get("title", "") or ""),
        ])
        return sum(1 for t in tokens if t in text)

    df["_score"] = df.apply(score, axis=1)
    df = df[df["_score"] > 0].sort_values("_score", ascending=False)

    # 토큰 완화: 5개 미만이면 조건 낮춤
    if len(df) < min_count:
        df_all = pd.read_csv(CONTENT_CSV_PATH)
        df_all["_score"] = df_all.apply(score, axis=1)
        # 토큰을 1개씩 줄여가며 재시도
        for drop_count in range(1, len(tokens)):
            reduced_tokens = set(list(tokens)[drop_count:])
            def score_reduced(row, rt=reduced_tokens):
                text = " ".join([str(row.get("tags", "") or ""),
                                  str(row.get("cat", "") or ""),
                                  str(row.get("title", "") or "")])
                return sum(1 for t in rt if t in text)
            df_all["_score"] = df_all.apply(score_reduced, axis=1)
            df = df_all[df_all["_score"] > 0].sort_values("_score", ascending=False)
            if len(df) >= min_count:
                break

    # 아티클/영상 혼합 선별
    articles = df[df["type"] == "아티클"].head(min_count)
    videos = df[df["type"] == "영상"].head(min_count)

    result = []
    ai, vi = 0, 0
    while len(result) < min_count and (ai < len(articles) or vi < len(videos)):
        if ai < len(articles):
            result.append(articles.iloc[ai].to_dict())
            ai += 1
        if vi < len(videos) and len(result) < min_count:
            result.append(videos.iloc[vi].to_dict())
            vi += 1

    return result[:max(min_count, len(result))]
```

- [ ] **Step 2: 단독 테스트 (API 키 필요)**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
python -c "
from theme_engine import generate_theme, match_contents
result = generate_theme()
print('keyword:', result['keyword'])
print('youtube:', result['youtube'][:2])
contents = match_contents(result['keyword'])
print('contents:', len(contents), '개')
"
```

Expected: keyword, 제목 샘플, 콘텐츠 수 출력

- [ ] **Step 3: 커밋**

```bash
git add theme_engine.py
git commit -m "feat: add theme_engine.py with OpenRouter API and content matching"
```

---

## Task 5: app.py — Slack Bolt 메인 앱

**Files:**
- Create: `/Users/hunet/Desktop/slack bot/app.py`

- [ ] **Step 1: app.py 작성**

```python
"""
리더십저니 테마 자동화 Slack Bolt 앱
"""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from scraper import run_scraping
from theme_engine import generate_theme, match_contents, get_direction

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
TARGET_USER_ID = os.environ["TARGET_USER_ID"]
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH", "data/theme_history.json")

# 프로세스 메모리 세션
session = {
    "suggested_keywords": [],
    "current": {"keyword": None, "titles": {}, "contents": []},
    "last_ts": None,        # 마지막 발송 메시지 ts (재생성 시 업데이트용)
    "last_channel": None,
}


# ── 유틸 ────────────────────────────────────────────────────────────────────

CIRCLE_NUMS = ["①", "②", "③", "④", "⑤"]

def _build_message_text(month, direction, keyword, titles, contents):
    lines = [
        f":date: *{month}월 기획 방향*",
        direction,
        "",
        "─────────────────────────",
        ":clapper: *1. 유튜브 스타일*",
    ]
    for i, t in enumerate(titles.get("youtube", [])[:5]):
        lines.append(f"{CIRCLE_NUMS[i]} {t}")

    lines += ["", "─────────────────────────", ":books: *2. 교육적 스타일*"]
    for i, t in enumerate(titles.get("educational", [])[:5]):
        lines.append(f"{CIRCLE_NUMS[i]} {t}")

    lines += ["", "─────────────────────────", ":fire: *3. 밈/유행어 스타일*"]
    for i, t in enumerate(titles.get("meme", [])[:5]):
        lines.append(f"{CIRCLE_NUMS[i]} {t}")

    lines += ["", "─────────────────────────", ":zap: *4. 어그로 스타일*"]
    for i, t in enumerate(titles.get("aggro", [])[:5]):
        lines.append(f"{CIRCLE_NUMS[i]} {t}")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━━━", ":books: *추천 콘텐츠 (아티클 · 영상)*"]
    for c in contents:
        icon = ":page_facing_up:" if c.get("type") == "아티클" else ":clapper:"
        lines.append(f"{icon} {c.get('title', '')}")

    return "\n".join(lines)


def _build_blocks(text):
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 테마 재생성"},
                    "action_id": "regenerate_theme",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 이 테마로 확정"},
                    "action_id": "confirm_theme",
                },
            ],
        },
    ]


def _get_dm_channel():
    result = app.client.conversations_open(users=TARGET_USER_ID)
    return result["channel"]["id"]


def _save_confirmed_theme(keyword):
    import json
    path = THEME_HISTORY_PATH
    data = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    if keyword not in data:
        data.append(keyword)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _run_and_send(say_fn=None, client=None, channel=None, update_ts=None):
    """테마 생성 후 DM 발송 또는 메시지 업데이트"""
    # 스크래핑
    scrape_warnings = run_scraping()

    # 테마 생성
    result = generate_theme(extra_forbidden=session["suggested_keywords"])
    keyword = result["keyword"]
    titles = {k: result[k] for k in ["youtube", "educational", "meme", "aggro"]}
    contents = match_contents(keyword)

    # 세션 업데이트
    session["current"] = {"keyword": keyword, "titles": titles, "contents": contents}

    # 메시지 구성
    month = datetime.now().month
    direction = get_direction(month)
    text = _build_message_text(month, direction, keyword, titles, contents)
    blocks = _build_blocks(text)

    dm_channel = channel or _get_dm_channel()

    if update_ts:
        # 재생성: 기존 메시지 업데이트
        app.client.chat_update(channel=dm_channel, ts=update_ts, text=text, blocks=blocks)
        session["last_ts"] = update_ts
    else:
        # 최초 발송
        resp = app.client.chat_postMessage(channel=dm_channel, text=text, blocks=blocks)
        session["last_ts"] = resp["ts"]
        session["last_channel"] = dm_channel

    # 스크래핑 경고 별도 발송
    if scrape_warnings:
        app.client.chat_postMessage(
            channel=dm_channel,
            text=":warning: " + " | ".join(scrape_warnings)
        )


# ── 이벤트 핸들러 ────────────────────────────────────────────────────────────

@app.message("테마발송")
def handle_message_trigger(message, say):
    try:
        _run_and_send(channel=message["channel"])
    except Exception as e:
        say(f":x: 테마 생성 중 오류가 발생했습니다: {e}")


@app.command("/테마발송")
def handle_slash_command(ack, command):
    ack()
    try:
        _run_and_send()
    except Exception as e:
        app.client.chat_postMessage(
            channel=_get_dm_channel(),
            text=f":x: 테마 생성 중 오류가 발생했습니다: {e}"
        )


@app.message("테마재생성")
def handle_regenerate_message(message, say):
    _do_regenerate(channel=message["channel"])


@app.action("regenerate_theme")
def handle_regenerate_button(ack, body):
    ack()
    _do_regenerate(
        channel=session.get("last_channel") or body["channel"]["id"],
        update_ts=session.get("last_ts"),
    )


def _do_regenerate(channel=None, update_ts=None):
    # 현재 키워드를 금지 목록에 추가
    current_kw = session["current"].get("keyword")
    if current_kw and current_kw not in session["suggested_keywords"]:
        session["suggested_keywords"].append(current_kw)

    try:
        _run_and_send(channel=channel, update_ts=update_ts)
    except Exception as e:
        dm = channel or _get_dm_channel()
        app.client.chat_postMessage(channel=dm, text=f":x: 재생성 오류: {e}")


@app.action("confirm_theme")
def handle_confirm(ack, body):
    ack()
    keyword = session["current"].get("keyword")
    if keyword:
        _save_confirmed_theme(keyword)

    channel = session.get("last_channel") or body["channel"]["id"]
    ts = session.get("last_ts")

    confirm_text = f":white_check_mark: 확정되었습니다.\n선정 키워드: *{keyword}*"

    if ts:
        # 버튼 제거 후 확정 메시지로 교체
        app.client.chat_update(
            channel=channel, ts=ts,
            text=confirm_text, blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": confirm_text}}
            ]
        )
    else:
        app.client.chat_postMessage(channel=channel, text=confirm_text)

    # 세션 초기화
    session["suggested_keywords"] = []
    session["current"] = {"keyword": None, "titles": {}, "contents": []}
    session["last_ts"] = None
    session["last_channel"] = None


# ── 실행 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("리더십저니 Slack 앱 시작")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
```

- [ ] **Step 2: theme_engine.py에 get_direction 공개 함수 추가**

Task 4에서 작성한 `theme_engine.py` 하단에 아래 함수를 추가한다. `app.py`가 이미 `from theme_engine import generate_theme, match_contents, get_direction`으로 import하므로 이 함수가 없으면 Step 3에서 앱이 시작되지 않는다.

```python
def get_direction(month):
    """월 번호(int)를 받아 기획 방향 문자열 반환"""
    directions = _load_json(MONTHLY_DIRECTION_PATH, {})
    return directions.get(str(month), "리더십 역량 개발")
```

- [ ] **Step 3: 앱 실행 테스트**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
python app.py
```

Expected:
```
INFO - 리더십저니 Slack 앱 시작
Bolt app is running!
```

- [ ] **Step 4: Slack에서 "테마발송" 메시지 전송 후 DM 수신 확인**

확인 항목:
- 월 기획 방향 헤더 표시
- 4가지 스타일 각 5개 제목 표시
- 추천 콘텐츠 5개 이상 표시
- [테마 재생성] [이 테마로 확정] 버튼 표시

- [ ] **Step 5: 커밋**

```bash
git add app.py
git commit -m "feat: add main Slack Bolt app with theme generation and regeneration"
```

---

## Task 6: 데이터 초기화 실행

- [ ] **Step 1: data/ 디렉토리 생성 확인 후 XLS → contents.csv 생성**

```bash
cd "/Users/hunet/Desktop/slack bot"
source venv/bin/activate
mkdir -p data
python prepare_data.py \
  --article "리더십저니 아티클 리스트260507151019.xls" \
  --video "리더십저니 영상 리스트260507151817.xls" \
  --output data/contents.csv
```

Expected: `완료: 1502개 콘텐츠 -> data/contents.csv`

- [ ] **Step 2: theme_history.json 초기화**

```bash
python init_theme_history.py \
  --xls "리더십저니 아티클 리스트260507151019.xls" \
  --output data/theme_history.json
```

Expected: `완료: N개 테마 -> data/theme_history.json`

- [ ] **Step 3: .env 파일 설정**

`slack bot test/.env`에서 토큰 값을 복사해 `/Users/hunet/Desktop/slack bot/.env` 작성:

```
SLACK_BOT_TOKEN=<slack bot test/.env에서 복사>
SLACK_APP_TOKEN=<slack bot test/.env에서 복사>
OPENROUTER_API_KEY=<OpenRouter 발급>
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet
TARGET_USER_ID=U0B2065SZ8B
CONTENT_CSV_PATH=data/contents.csv
SCRAPED_CONTENTS_PATH=data/scraped_contents.json
THEME_HISTORY_PATH=data/theme_history.json
MONTHLY_DIRECTION_PATH=data/monthly_direction.json
HUNET_SESSION_COOKIE=<브라우저 개발자도구에서 복사>
```

- [ ] **Step 4: 전체 통합 실행**

```bash
python app.py
```

Slack에서 봇과 DM → `테마발송` 입력 → 결과 확인

---

## Task 7: 버그 수정 및 셀렉터 조정

스크래핑 결과가 빈 경우 또는 제목이 잘못 추출되는 경우 대응.

- [ ] **Step 1: 실제 hunet 페이지 HTML 구조 확인**

```bash
python -c "
import requests, os
from dotenv import load_dotenv
load_dotenv()
cookie = os.getenv('HUNET_SESSION_COOKIE', '')
s = requests.Session()
if cookie:
    s.headers.update({'Cookie': cookie})
resp = s.get('https://leadership.hunet.co.kr/journey/library?keyword_cd=CK92', timeout=10)
print(resp.status_code)
print(resp.text[:3000])
"
```

- [ ] **Step 2: HTML 구조에 맞게 scraper.py 셀렉터 수정**

`scraper.py`의 `soup.select(...)` 부분을 실제 태그/클래스에 맞게 수정.

- [ ] **Step 3: 재테스트**

```bash
python -c "from scraper import run_scraping; run_scraping()"
```

Expected: 실제 콘텐츠 제목 수집 확인

- [ ] **Step 4: 커밋**

```bash
git add scraper.py
git commit -m "fix: adjust scraper selectors to match actual hunet page structure"
```

---

## 체크리스트 요약

- [ ] Task 1: 환경 설정 완료
- [ ] Task 2: init_theme_history.py 실행 완료
- [ ] Task 3: scraper.py 동작 확인
- [ ] Task 4: theme_engine.py OpenRouter 호출 성공
- [ ] Task 5: app.py Slack 발송 성공
- [ ] Task 6: 데이터 초기화 완료, 통합 테스트 통과
- [ ] Task 7: 스크래핑 셀렉터 실 페이지 검증 완료
