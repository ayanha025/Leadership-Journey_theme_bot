import json
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
    "sourceUrl": "웹 검색으로 확인한 실제 원문 URL (반드시 실존하는 URL, 빈 문자열 금지)",
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
    "sourceUrl": "웹 검색으로 확인한 실제 원문 URL (반드시 실존하는 URL, 빈 문자열 금지)",
    "sourceDate": "YYYY-MM"
  }}
]"""


def build_dates() -> tuple:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    return today, start, today


def _exclude_block(used_keywords: list, existing_titles: list = None) -> str:
    parts = []
    if used_keywords:
        parts.append(f"이미 제안한 키워드 목록 (반드시 제외): {', '.join(used_keywords)}")
    if existing_titles:
        titles_str = "\n".join(f"- {t}" for t in existing_titles)
        parts.append(f"이미 발행된 아티클 제목 목록 (동일하거나 매우 유사한 소재는 반드시 제외):\n{titles_str}")
    return "\n\n".join(parts)


def build_article_prompt(used_keywords: list, existing_titles: list = None) -> str:
    today, start, end = build_dates()
    return _ARTICLE_PROMPT_TEMPLATE.format(
        sources=_COMMON_SOURCES, criteria=_COMMON_CRITERIA
    ).replace("{today}", today).replace("{start}", start).replace("{end}", end).replace(
        "{exclude_block}", _exclude_block(used_keywords, existing_titles)
    )


def build_series_prompt(used_keywords: list, existing_titles: list = None) -> str:
    today, start, end = build_dates()
    return _SERIES_PROMPT_TEMPLATE.format(
        sources=_COMMON_SOURCES, criteria=_COMMON_CRITERIA
    ).replace("{today}", today).replace("{start}", start).replace("{end}", end).replace(
        "{exclude_block}", _exclude_block(used_keywords, existing_titles)
    )


def call_openrouter(prompt: str, api_key: str, model: str) -> tuple:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter API 오류: {resp.status_code} {resp.text}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    return content, citations


def _extract_json(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 파싱 실패: 배열 없음. raw={raw[:200]}")
    return raw[start : end + 1]


def parse_articles(raw: str) -> list:
    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"JSON 파싱 실패: {e}")


def parse_series(raw: str) -> list:
    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"JSON 파싱 실패: {e}")


def format_article_blocks(articles: list, date_str: str, citations: list = None) -> list:
    if not articles:
        return [{"type": "section", "text": {"type": "mrkdwn",
                 "text": "⚠️ 소재를 찾지 못했습니다. 🔄 재생성을 눌러주세요."}},
                {"type": "actions", "elements": [
                    {"type": "button", "action_id": "regenerate_article",
                     "text": {"type": "plain_text", "text": "🔄 재생성"}}]}]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"📋 *이번 소재 후보 {len(articles)}건* ({date_str} 기준)"}},
        {"type": "divider"},
    ]
    for i, a in enumerate(articles, 1):
        src = f"<{a['sourceUrl']}|{a['source']}>" if a.get("sourceUrl") else f"{a['source']} (링크 미확인)"
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{i}. [{a['category']}] {a['title']}*\n{a['description'][:200]}\n🔗 출처: {src}"}})
    if citations:
        links = "\n".join(f"• <{url}|{url}>" for url in citations[:8])
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"🔗 *참고 기사 링크*\n{links}"}})
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


def format_series_blocks(series: list, date_str: str, citations: list = None) -> list:
    if not series:
        return [{"type": "section", "text": {"type": "mrkdwn",
                 "text": "⚠️ 시리즈 기획안을 찾지 못했습니다. 🔄 재생성을 눌러주세요."}},
                {"type": "actions", "elements": [
                    {"type": "button", "action_id": "regenerate_series",
                     "text": {"type": "plain_text", "text": "🔄 재생성"}}]}]
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
    if citations:
        links = "\n".join(f"• <{url}|{url}>" for url in citations[:8])
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"🔗 *참고 기사 링크*\n{links}"}})
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
