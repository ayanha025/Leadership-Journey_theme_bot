# 휴넷CEO 비즈니스리뷰 Slack 봇 구현 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slack DM에서 `소재서치` / `시리즈서치` 입력 시 Perplexity sonar-pro(웹 검색 내장)로 C레벨 임원 대상 아티클 후보 7건을 생성하고, 재생성·확정 버튼으로 관리하는 Slack Bolt 봇을 구현한다.

**Architecture:** Slack Bolt(Socket Mode) → `content_engine.py`(날짜 치환 + OpenRouter API 호출 + JSON 파싱 + Slack 블록 포맷) → `app.py`(이벤트·버튼 핸들러 + 세션 관리) → `storage.py`(확정 소재 저장)

**Tech Stack:** Python 3.10+, slack-bolt, requests, python-dotenv, pytest

**Spec:** `docs/superpowers/specs/2026-05-14-hunet-ceo-slack-bot-design.md`

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| `requirements.txt` | 패키지 목록 |
| `.env.example` | 환경변수 템플릿 |
| `storage.py` | `confirmed_articles.json` 읽기/쓰기 |
| `content_engine.py` | 프롬프트 구성, API 호출, JSON 파싱, Slack 블록 생성 |
| `app.py` | Slack Bolt 앱, 이벤트/버튼 핸들러, 세션 관리 |
| `data/confirmed_articles.json` | 확정 소재 누적 저장 |
| `tests/__init__.py` | 테스트 패키지 초기화 |
| `tests/test_storage.py` | storage.py 단위 테스트 |
| `tests/test_content_engine.py` | content_engine.py 단위 테스트 |

---

## Task 1: 프로젝트 환경 설정

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `data/confirmed_articles.json`
- Create: `tests/__init__.py`

- [ ] **Step 1: requirements.txt 작성**

```
slack-bolt>=1.18.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=7.0.0
```

- [ ] **Step 2: .env.example 작성**

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=perplexity/sonar-pro
TARGET_USER_ID=U0B2065SZ8B
CONFIRMED_ARTICLES_PATH=data/confirmed_articles.json
```

- [ ] **Step 3: data/ 디렉토리 및 tests/ 초기화**

```bash
mkdir -p data tests
echo "[]" > data/confirmed_articles.json
touch tests/__init__.py
```

- [ ] **Step 4: 가상환경 생성 및 패키지 설치**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 5: .env 파일 생성**

```bash
cp .env.example .env
# .env 파일에 실제 API 키는 나중에 입력
```

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt .env.example data/confirmed_articles.json tests/__init__.py
git commit -m "feat: 휴넷CEO slack bot project setup"
```

---

## Task 2: storage.py — 확정 소재 저장

**Files:**
- Create: `storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_storage.py`:
```python
import os
import pytest
from storage import load_confirmed, append_confirmed


@pytest.fixture
def json_path(tmp_path):
    p = tmp_path / "confirmed.json"
    p.write_text("[]")
    return str(p)


def test_load_confirmed_empty(json_path):
    assert load_confirmed(json_path) == []


def test_append_and_load(json_path):
    append_confirmed({"keyword": "초격차", "category": "경영", "type": "article"}, json_path)
    result = load_confirmed(json_path)
    assert len(result) == 1
    assert result[0]["keyword"] == "초격차"
    assert "confirmed_at" in result[0]


def test_append_multiple(json_path):
    append_confirmed({"keyword": "A"}, json_path)
    append_confirmed({"keyword": "B"}, json_path)
    assert len(load_confirmed(json_path)) == 2


def test_load_creates_file_if_missing(tmp_path):
    path = str(tmp_path / "new.json")
    assert load_confirmed(path) == []
    assert os.path.exists(path)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_storage.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: storage.py 구현**

```python
import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def load_confirmed(path: str) -> list:
    if not os.path.exists(path):
        _write(path, [])
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def append_confirmed(item: dict, path: str) -> None:
    data = load_confirmed(path)
    data.append({**item, "confirmed_at": datetime.now(KST).isoformat()})
    _write(path, data)


def _write(path: str, data: list) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_storage.py -v
```
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add storage.py tests/test_storage.py
git commit -m "feat: add storage.py for confirmed articles persistence"
```

---

## Task 3: content_engine.py — 날짜 치환 & 프롬프트 구성

**Files:**
- Create: `content_engine.py`
- Create: `tests/test_content_engine.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_content_engine.py`:
```python
import json
import pytest
from unittest.mock import patch, MagicMock
import content_engine


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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_content_engine.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'content_engine'`

- [ ] **Step 3: content_engine.py 프롬프트 함수 구현**

```python
import json
import os
import re
import requests
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

_COMMON_SOURCES = """## 소스(우선순위)
1. CEO 및 C레벨 전문 콘텐츠 플랫폼: Harvard Business Review (HBR), MIT Sloan Management Review, Strategy+Business, Thinkers50, INSEAD Knowledge
2. 국내 경영 전문 매체 및 연구소: 동아비즈니스리뷰(DBR), 한경비즈니스, LG경제연구원, 포스코경영연구원(POSRI), SERICEO, 매일경제 MBAtimes, KT DIGIECO, 산업연구원(KIET)
3. 글로벌 전략·컨설팅 기관: McKinsey & Company, BCG, Bain, Deloitte Insights, PwC, EY
4. 혁신·트렌드 리서치 기관: World Economic Forum (WEF), Gartner, Forrester, CB Insights, Nikkei Asia, IMF, OECD
5. 국내외 일간지: 조선일보, 중앙일보, 동아일보, 한겨레, 매일경제, 한국경제, 연합뉴스, BBC

※ 블로그, 커뮤니티, 요약형 콘텐츠 제외. 원출처 고급 리포트 또는 아티클만 사용."""

_COMMON_CRITERIA = """## 선별·평가 규칙 (내부 기준, 총점 3.5점 이상만 출력)
① 임팩트: C레벨 리더의 의사결정·전략에 실질적 영향을 줄 수 있는가?
② 시의성: 지금 이 시점에서 중요한 이슈인가?
③ 차별성: 통찰을 줄 수 있는 새로운 관점이 있는가?
④ 실행 가능성: 조직 운영·전략 실행에 적용 가능한 시사점이 있는가?
⑤ 지속성/확장성: 중장기적으로도 이어질 주제인가?"""

_ARTICLE_PROMPT_TEMPLATE = """당신은 전략경영컨설턴트이자 리더십·트렌드·인문 분야에 정통한 콘텐츠 에디터입니다.
C레벨 임원 대상 프리미엄 콘텐츠 플랫폼 '휴넷CEO 비즈니스리뷰'(https://ceo.hunet.co.kr/membership/business-review)에 실릴 아티클 주제 아이디어 7건 이상 제안하세요.

## 목적
- 기업 임원의 전략적 사고와 실행을 자극하는 고품질 콘텐츠의 소재 발굴
- 경영진에 인사이트를 줄 수 있는 최신 이슈 중심
- 단순 정보 전달이 아닌, 사유(Thinking Intervention)와 실행 아이디어를 유도할 수 있어야 합니다.
- 휴넷CEO 비즈니스리뷰에 올라오지 않은 소재여야 합니다. 중복은 안됩니다.

## 탐색 기간/시간대
- 기준일: {{today}} (Asia/Seoul)
- 수집 기간: {{start}} ~ {{end}}

{sources}

{criteria}

{{exclude_block}}

## 출력 규칙 (반드시 준수)
반드시 JSON 배열만 출력하세요. 설명문·머리말·꼬리말 일절 금지. 첫 글자는 반드시 [.

[
  {{
    "keyword": "핵심 키워드",
    "category": "경영|리더십|인문|트렌드|혁신 중 하나",
    "title": "아티클 제목",
    "description": "키워드를 소개하는 글 300자 내외",
    "implications": ["경영자를 위한 시사점 20자 내외 1", "시사점2", "시사점3", "시사점4", "시사점5"],
    "source": "출처명",
    "sourceUrl": "원문 URL (불확실 시 빈 문자열)",
    "sourceDate": "YYYY-MM"
  }}
]"""

_SERIES_PROMPT_TEMPLATE = """당신은 전략경영컨설턴트이자 리더십·트렌드·인문 분야에 정통한 콘텐츠 에디터입니다.
C레벨 임원 대상 프리미엄 콘텐츠 플랫폼 '휴넷CEO 비즈니스리뷰'(https://ceo.hunet.co.kr/membership/business-review)에 실릴 시리즈 아티클 기획안 7건 이상 제안하세요.

## 목적
- 기업 임원의 전략적 사고와 실행을 자극하는 고품질 시리즈 기획 발굴
- 경영진에 인사이트를 줄 수 있는 최신 이슈 기반 연속 기획
- 단순 정보 전달이 아닌, 사유(Thinking Intervention)와 실행 아이디어를 유도할 수 있어야 합니다.
- 휴넷CEO 비즈니스리뷰에 올라오지 않은 소재여야 합니다. 중복은 안됩니다.

## 탐색 기간/시간대
- 기준일: {{today}} (Asia/Seoul)
- 수집 기간: {{start}} ~ {{end}}

{sources}

{criteria}

{{exclude_block}}

## 출력 규칙 (반드시 준수)
반드시 JSON 배열만 출력하세요. 설명문·머리말·꼬리말 일절 금지. 첫 글자는 반드시 [.

[
  {{
    "keyword": "키워드",
    "category": "경영|리더십|인문|트렌드|혁신 중 하나",
    "seriesTitle": "시리즈 제목",
    "description": "기획 의도 300자 내외",
    "episodes": [
      {{"title": "1회차 부제", "desc": "한 줄 요약"}},
      {{"title": "2회차 부제", "desc": "한 줄 요약"}},
      {{"title": "3회차 부제", "desc": "한 줄 요약"}},
      {{"title": "4회차 부제", "desc": "한 줄 요약"}}
    ],
    "source": "출처명",
    "sourceUrl": "",
    "sourceDate": "YYYY-MM"
  }}
]"""


def build_dates() -> tuple[str, str, str]:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    return today, start, today


def _exclude_block(used_keywords: list[str]) -> str:
    if not used_keywords:
        return ""
    return f"이미 제안한 키워드 목록 (반드시 제외): {', '.join(used_keywords)}"


def build_article_prompt(used_keywords: list[str]) -> str:
    today, start, end = build_dates()
    return _ARTICLE_PROMPT_TEMPLATE.format(
        sources=_COMMON_SOURCES, criteria=_COMMON_CRITERIA
    ).replace("{{today}}", today).replace("{{start}}", start).replace("{{end}}", end).replace(
        "{{exclude_block}}", _exclude_block(used_keywords)
    )


def build_series_prompt(used_keywords: list[str]) -> str:
    today, start, end = build_dates()
    return _SERIES_PROMPT_TEMPLATE.format(
        sources=_COMMON_SOURCES, criteria=_COMMON_CRITERIA
    ).replace("{{today}}", today).replace("{{start}}", start).replace("{{end}}", end).replace(
        "{{exclude_block}}", _exclude_block(used_keywords)
    )
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_content_engine.py -v
```
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add content_engine.py tests/test_content_engine.py
git commit -m "feat: add content_engine prompt builders with date substitution"
```

---

## Task 4: content_engine.py — API 호출 & JSON 파싱

**Files:**
- Modify: `content_engine.py` (하단에 추가)
- Modify: `tests/test_content_engine.py` (하단에 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_content_engine.py` 하단에 추가:
```python
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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_content_engine.py -v -k "openrouter or parse"
```
Expected: FAIL — `AttributeError: module 'content_engine' has no attribute 'call_openrouter'`

- [ ] **Step 3: content_engine.py에 API 호출 & 파싱 함수 추가**

`content_engine.py` 하단에 추가:
```python
def call_openrouter(prompt: str, api_key: str, model: str) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter API 오류: {resp.status_code} {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 파싱 실패: 배열 없음. raw={raw[:200]}")
    return raw[start : end + 1]


def parse_articles(raw: str) -> list[dict]:
    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"JSON 파싱 실패: {e}")


def parse_series(raw: str) -> list[dict]:
    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"JSON 파싱 실패: {e}")
```

- [ ] **Step 4: 전체 테스트 실행 — 통과 확인**

```bash
pytest tests/test_content_engine.py -v
```
Expected: 13 passed

- [ ] **Step 5: 커밋**

```bash
git add content_engine.py tests/test_content_engine.py
git commit -m "feat: add OpenRouter API call and JSON parsing"
```

---

## Task 5: content_engine.py — Slack 블록 포맷

**Files:**
- Modify: `content_engine.py` (하단에 추가)
- Modify: `tests/test_content_engine.py` (하단에 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_content_engine.py` 하단에 추가:
```python
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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_content_engine.py -v -k "format"
```
Expected: FAIL — `AttributeError: module 'content_engine' has no attribute 'format_article_blocks'`

- [ ] **Step 3: format_article_blocks & format_series_blocks 구현**

`content_engine.py` 하단에 추가:
```python
def format_article_blocks(articles: list[dict], date_str: str) -> list:
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"📋 *이번 소재 후보 {len(articles)}건* ({date_str} 기준)"}},
        {"type": "divider"},
    ]
    for i, a in enumerate(articles, 1):
        src = f"<{a['sourceUrl']}|{a['source']}>" if a.get("sourceUrl") else f"{a['source']} (링크 미확인)"
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{i}. [{a['category']}] {a['title']}*\n{a['description'][:200]}\n🔗 출처: {src}"}})
    blocks += [
        {"type": "divider"},
        {"type": "actions", "elements": [
            {"type": "static_select", "action_id": "select_article",
             "placeholder": {"type": "plain_text", "text": "확정할 소재 선택 (1~7)"},
             "options": [{"text": {"type": "plain_text", "text": f"{i}. {a['keyword']}", "emoji": True},
                          "value": str(i - 1)} for i, a in enumerate(articles, 1)]},
            {"type": "button", "action_id": "confirm_article",
             "text": {"type": "plain_text", "text": "✅ 확정"}, "style": "primary"},
            {"type": "button", "action_id": "regenerate_article",
             "text": {"type": "plain_text", "text": "🔄 재생성"}},
        ]},
    ]
    return blocks


def format_series_blocks(series: list[dict], date_str: str) -> list:
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"📚 *시리즈 기획안 {len(series)}건* ({date_str} 기준)"}},
        {"type": "divider"},
    ]
    for i, s in enumerate(series, 1):
        eps = "\n".join(f"  {ep['title']}: {ep['desc']}" for ep in s.get("episodes", []))
        src = f"<{s['sourceUrl']}|{s['source']}>" if s.get("sourceUrl") else f"{s['source']} (링크 미확인)"
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{i}. [{s['category']}] {s['seriesTitle']}*\n기획 의도: {s['description'][:100]}\n{eps}\n🔗 출처: {src}"}})
    blocks += [
        {"type": "divider"},
        {"type": "actions", "elements": [
            {"type": "static_select", "action_id": "select_series",
             "placeholder": {"type": "plain_text", "text": "확정할 시리즈 선택 (1~7)"},
             "options": [{"text": {"type": "plain_text", "text": f"{i}. {s['keyword']}", "emoji": True},
                          "value": str(i - 1)} for i, s in enumerate(series, 1)]},
            {"type": "button", "action_id": "confirm_series",
             "text": {"type": "plain_text", "text": "✅ 확정"}, "style": "primary"},
            {"type": "button", "action_id": "regenerate_series",
             "text": {"type": "plain_text", "text": "🔄 재생성"}},
        ]},
    ]
    return blocks
```

- [ ] **Step 4: 전체 테스트 실행 — 통과 확인**

```bash
pytest tests/ -v
```
Expected: 전체 passed

- [ ] **Step 5: 커밋**

```bash
git add content_engine.py tests/test_content_engine.py
git commit -m "feat: add Slack block formatters for articles and series"
```

---

## Task 6: app.py — 세션, 트리거, 검색 핵심 로직

**Files:**
- Create: `app.py`

- [ ] **Step 1: app.py 작성**

```python
import logging
import os
import threading

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import content_engine
import storage

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
TARGET_USER_ID = os.environ["TARGET_USER_ID"]
CONFIRMED_PATH = os.getenv("CONFIRMED_ARTICLES_PATH", "data/confirmed_articles.json")
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "perplexity/sonar-pro")

sessions: dict[str, dict] = {}


def _get_session(user_id: str) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {
            "articles": [], "articles_used_keywords": [],
            "articles_last_ts": None, "articles_last_channel": None,
            "series": [], "series_used_keywords": [],
            "series_last_ts": None, "series_last_channel": None,
        }
    return sessions[user_id]


def _open_dm(client, user_id: str) -> str:
    return client.conversations_open(users=user_id)["channel"]["id"]


def _run_article_search(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = _open_dm(client, user_id)
    loading = client.chat_postMessage(
        channel=dm,
        text="AI가 최신 소재를 서치하고 있습니다… 약 20~40초 소요됩니다 :hourglass_flowing_sand:",
    )
    try:
        prompt = content_engine.build_article_prompt(sess["articles_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        articles = content_engine.parse_articles(raw)
    except Exception as e:
        logger.error("소재 서치 오류: %s", e)
        client.chat_update(channel=dm, ts=loading["ts"],
                           text="소재 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_article_blocks(articles, today)
    result = client.chat_update(channel=dm, ts=loading["ts"],
                                text=f"소재 후보 {len(articles)}건", blocks=blocks)
    sess["articles"] = articles
    sess["articles_used_keywords"].extend(a["keyword"] for a in articles)
    sess["articles_last_ts"] = result["ts"]
    sess["articles_last_channel"] = dm


def _run_series_search(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = _open_dm(client, user_id)
    loading = client.chat_postMessage(
        channel=dm,
        text="AI가 시리즈 기획안을 서치하고 있습니다… 약 20~40초 소요됩니다 :hourglass_flowing_sand:",
    )
    try:
        prompt = content_engine.build_series_prompt(sess["series_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        series = content_engine.parse_series(raw)
    except Exception as e:
        logger.error("시리즈 서치 오류: %s", e)
        client.chat_update(channel=dm, ts=loading["ts"],
                           text="시리즈 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_series_blocks(series, today)
    result = client.chat_update(channel=dm, ts=loading["ts"],
                                text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    sess["series"] = series
    sess["series_used_keywords"].extend(s["keyword"] for s in series)
    sess["series_last_ts"] = result["ts"]
    sess["series_last_channel"] = dm


@app.message("소재서치")
def handle_article_search(message, client):
    if message.get("user") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_article_search, args=(client, TARGET_USER_ID)).start()


@app.message("시리즈서치")
def handle_series_search(message, client):
    if message.get("user") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_series_search, args=(client, TARGET_USER_ID)).start()


@app.command("/소재서치")
def slash_article_search(ack, command, client):
    ack()
    if command.get("user_id") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_article_search, args=(client, TARGET_USER_ID)).start()


@app.command("/시리즈서치")
def slash_series_search(ack, command, client):
    ack()
    if command.get("user_id") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_series_search, args=(client, TARGET_USER_ID)).start()
```

- [ ] **Step 2: 커밋**

```bash
git add app.py
git commit -m "feat: add app.py with session management and search triggers"
```

---

## Task 7: app.py — 재생성 & 확정 핸들러

**Files:**
- Modify: `app.py` (하단에 추가)

- [ ] **Step 1: 핸들러 함수 추가**

`app.py` 하단 (`if __name__ == "__main__":` 앞)에 추가:
```python
def _get_selected_index(state_values: dict, action_id: str) -> int | None:
    for block in state_values.values():
        if action_id in block:
            selected = block[action_id].get("selected_option")
            if selected:
                return int(selected["value"])
    return None


def _do_regenerate_article(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = sess["articles_last_channel"] or _open_dm(client, user_id)
    ts = sess["articles_last_ts"]
    if ts:
        client.chat_update(channel=dm, ts=ts, blocks=[],
                           text="AI가 새 소재를 서치하고 있습니다… :hourglass_flowing_sand:")
    try:
        prompt = content_engine.build_article_prompt(sess["articles_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        articles = content_engine.parse_articles(raw)
    except Exception as e:
        logger.error("소재 재생성 오류: %s", e)
        client.chat_postMessage(channel=dm,
                                text="소재 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_article_blocks(articles, today)
    if ts:
        result = client.chat_update(channel=dm, ts=ts,
                                    text=f"소재 후보 {len(articles)}건", blocks=blocks)
    else:
        result = client.chat_postMessage(channel=dm,
                                         text=f"소재 후보 {len(articles)}건", blocks=blocks)
    sess["articles"] = articles
    sess["articles_used_keywords"].extend(a["keyword"] for a in articles)
    sess["articles_last_ts"] = result["ts"]
    sess["articles_last_channel"] = dm


def _do_regenerate_series(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = sess["series_last_channel"] or _open_dm(client, user_id)
    ts = sess["series_last_ts"]
    if ts:
        client.chat_update(channel=dm, ts=ts, blocks=[],
                           text="AI가 새 시리즈 기획안을 서치하고 있습니다… :hourglass_flowing_sand:")
    try:
        prompt = content_engine.build_series_prompt(sess["series_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        series = content_engine.parse_series(raw)
    except Exception as e:
        logger.error("시리즈 재생성 오류: %s", e)
        client.chat_postMessage(channel=dm,
                                text="시리즈 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_series_blocks(series, today)
    if ts:
        result = client.chat_update(channel=dm, ts=ts,
                                    text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    else:
        result = client.chat_postMessage(channel=dm,
                                         text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    sess["series"] = series
    sess["series_used_keywords"].extend(s["keyword"] for s in series)
    sess["series_last_ts"] = result["ts"]
    sess["series_last_channel"] = dm


@app.action("regenerate_article")
def handle_regenerate_article(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    threading.Thread(target=_do_regenerate_article, args=(client, TARGET_USER_ID)).start()


@app.action("regenerate_series")
def handle_regenerate_series(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    threading.Thread(target=_do_regenerate_series, args=(client, TARGET_USER_ID)).start()


@app.action("select_article")
def handle_select_article(ack):
    ack()


@app.action("select_series")
def handle_select_series(ack):
    ack()


@app.action("confirm_article")
def handle_confirm_article(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    sess = _get_session(TARGET_USER_ID)
    if not sess["articles"]:
        return
    idx = _get_selected_index(body.get("state", {}).get("values", {}), "select_article")
    if idx is None:
        client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                                text="확정할 소재를 먼저 선택해주세요.")
        return
    item = {**sess["articles"][idx], "type": "article"}
    storage.append_confirmed(item, CONFIRMED_PATH)
    client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                            text=f"✅ 확정 완료: *{item['keyword']}* — {item['title']}")


@app.action("confirm_series")
def handle_confirm_series(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    sess = _get_session(TARGET_USER_ID)
    if not sess["series"]:
        return
    idx = _get_selected_index(body.get("state", {}).get("values", {}), "select_series")
    if idx is None:
        client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                                text="확정할 시리즈를 먼저 선택해주세요.")
        return
    item = {**sess["series"][idx], "type": "series"}
    storage.append_confirmed(item, CONFIRMED_PATH)
    client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                            text=f"✅ 확정 완료: *{item['keyword']}* — {item['seriesTitle']}")
```

- [ ] **Step 2: 진입점 추가**

`app.py` 최하단에 추가:
```python
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
```

- [ ] **Step 3: 커밋**

```bash
git add app.py
git commit -m "feat: add regenerate and confirm action handlers"
```

---

## Task 8: Slack 앱 설정 & 수동 통합 테스트

- [ ] **Step 1: Slack 앱 설정 확인 (api.slack.com)**

앱 설정 페이지에서 아래 항목 확인:
- **Socket Mode** → ON, App-Level Token 발급
- **Event Subscriptions** → `message.im`, `message.channels` 구독
- **Slash Commands** → `/소재서치`, `/시리즈서치` 각각 등록
- **Interactivity & Shortcuts** → ON
- **OAuth Scopes** → `chat:write`, `im:history`, `im:write`, `channels:history`, `commands`

- [ ] **Step 2: .env에 실제 키 입력**

```
SLACK_BOT_TOKEN=xoxb-실제토큰
SLACK_APP_TOKEN=xapp-실제토큰
OPENROUTER_API_KEY=실제키
```

- [ ] **Step 3: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 전체 passed

- [ ] **Step 4: 봇 실행**

```bash
source venv/bin/activate
python app.py
```
Expected: `⚡️ Bolt app is running!`

- [ ] **Step 5: 소재서치 수동 테스트**

1. Slack 봇 DM에 `소재서치` 입력
2. 로딩 메시지 → 소재 7건 결과 확인
3. [🔄 재생성] 클릭 → 이전 키워드 제외된 새 7건으로 교체 확인
4. 드롭다운에서 소재 선택 → [✅ 확정] → "확정 완료" 메시지 확인
5. `data/confirmed_articles.json` 파일 열어 저장 확인

- [ ] **Step 6: 시리즈서치 수동 테스트**

1. `시리즈서치` 입력
2. 시리즈 7건 결과 (회차 구성 포함) 확인
3. [🔄 재생성] → 새 시리즈 7건으로 교체 확인 (단발 세션과 독립)
4. 시리즈 선택 → [✅ 확정] → 저장 확인

- [ ] **Step 7: 슬래시 커맨드 테스트**

1. `/소재서치` 입력 → 소재 7건 DM 수신 확인
2. `/시리즈서치` 입력 → 시리즈 7건 DM 수신 확인

- [ ] **Step 8: 최종 커밋**

```bash
git add .
git commit -m "feat: complete 휴넷CEO 비즈니스리뷰 slack bot"
```
