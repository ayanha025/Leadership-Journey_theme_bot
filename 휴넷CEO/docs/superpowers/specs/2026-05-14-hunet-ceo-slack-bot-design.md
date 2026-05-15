# 휴넷CEO 비즈니스리뷰 소재서치 Slack 봇 — 설계 스펙

**목표:** Slack DM에서 "소재서치" 또는 "시리즈서치" 입력(슬래시 커맨드 포함) 시, Perplexity sonar-pro(웹 검색 내장)를 통해 C레벨 임원 대상 아티클 후보 7건을 DM으로 발송한다. 단발 소재와 시리즈 기획은 별도 트리거로 독립 운영. 재생성·확정 버튼 포함.

**Architecture:** Slack Bolt(Socket Mode) → content_engine.py(OpenRouter/Perplexity API + JSON 파싱) → DM 발송 → 버튼 액션 처리 → storage.py(확정 저장)

**Tech Stack:** Python 3, slack-bolt, requests, python-dotenv, OpenRouter API (perplexity/sonar-pro)

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| `app.py` | Slack Bolt 앱 진입점. 이벤트 리스너, 버튼/액션 핸들러, 세션 관리 |
| `content_engine.py` | OpenRouter API 호출, 날짜 치환, JSON 파싱, 메시지 포맷 |
| `storage.py` | confirmed_articles.json 읽기/쓰기 |
| `data/confirmed_articles.json` | 확정된 소재 누적 저장 |
| `requirements.txt` | 패키지 목록 |
| `.env` | 환경변수 (API 키 등) |

---

## 워크플로우

### 단발 소재 서치

1. 사용자가 DM 또는 채널에서 `소재서치` 입력 또는 `/소재서치` 실행
2. 본인 DM에 로딩 메시지: "AI가 최신 소재를 서치하고 있습니다… 약 20~40초 소요됩니다"
3. `content_engine.py` → Perplexity sonar-pro 호출 → JSON 7건 파싱
4. DM에 결과 메시지 발송:
   - 소재 7건 목록 (번호, 카테고리, 키워드, 제목, 한 줄 설명, 출처)
   - 드롭다운 "확정할 소재 선택 (1~7)" + [확정] 버튼
   - [🔄 재생성] 버튼

### 시리즈 기획 서치

1. 사용자가 DM 또는 채널에서 `시리즈서치` 입력 또는 `/시리즈서치` 실행
2. 본인 DM에 로딩 메시지: "AI가 시리즈 기획안을 서치하고 있습니다… 약 20~40초 소요됩니다"
3. `content_engine.py` → 시리즈 기획 프롬프트로 Perplexity sonar-pro 호출 → JSON 7건 파싱
4. DM에 결과 메시지 발송:
   - 시리즈 7건 목록 (번호, 카테고리, 키워드, 시리즈 제목, 기획 의도, 회차 구성, 출처)
   - 드롭다운 "확정할 시리즈 선택 (1~7)" + [확정] 버튼
   - [🔄 재생성] 버튼

### 재생성

- [🔄 재생성] 클릭 → 세션에 저장된 이전 키워드 목록을 프롬프트에 제외 조건으로 추가 → 새 7건으로 메시지 교체(update)
- 단발/시리즈 각각 독립된 재생성 (단발 재생성이 시리즈 세션에 영향 없음)

### 확정

- 드롭다운에서 소재/시리즈 선택 → [확정] 클릭
- `storage.py` → `confirmed_articles.json`에 해당 소재 추가
- "확정 완료: {키워드}" 메시지 발송

---

## Slack 메시지 포맷 (예시)

```
📋 *이번 소재 후보 7건* (2026-05-14 기준)

*1. [경영] 초격차 전략*
조직의 핵심 역량을 집중하여 경쟁자와의 격차를 벌리는 전략...
🔗 출처: Harvard Business Review

*2. [리더십] 심리적 안전감*
...

━━━━━━━━━━━━━━━━━━━━
확정할 소재: [드롭다운 ▼]  [✅ 확정]
[🔄 재생성]
```

시리즈 기획 메시지 예시 (`시리즈서치` 트리거):
```
📚 *시리즈 기획안 7건* (2026-05-14 기준)

*1. [경영] 초격차 전략 시리즈*
기획 의도: 조직의 핵심 역량을 집중하여...
  1회차: 초격차의 조건
  2회차: 핵심 역량 발굴법
  3회차: 실행 로드맵
  4회차: 리더의 역할
🔗 출처: McKinsey & Company

*2. [리더십] ...*
...

━━━━━━━━━━━━━━━━━━━━
확정할 시리즈: [드롭다운 ▼]  [✅ 확정]
[🔄 재생성]
```

---

## AI 호출 스펙

### 모델
`perplexity/sonar-pro` via OpenRouter API (`https://openrouter.ai/api/v1/chat/completions`)

### 날짜 치환
`content_engine.py`에서 호출 시점에 Asia/Seoul 기준으로 자동 계산:
- `{{기준일}}` → 오늘 날짜 (YYYY-MM-DD)
- `{{시작일}}` → 30일 전
- `{{종료일}}` → 오늘

### 단발 소재 프롬프트

```
당신은 전략경영컨설턴트이자 리더십·트렌드·인문 분야에 정통한 콘텐츠 에디터입니다.
C레벨 임원 대상 프리미엄 콘텐츠 플랫폼 '휴넷CEO 비즈니스리뷰'(https://ceo.hunet.co.kr/membership/business-review)에 실릴 아티클 주제 아이디어 7건 이상 제안하세요.

## 목적
- 기업 임원의 전략적 사고와 실행을 자극하는 고품질 콘텐츠의 소재 발굴
- 경영진에 인사이트를 줄 수 있는 최신 이슈 중심
- 단순 정보 전달이 아닌, 사유(Thinking Intervention)와 실행 아이디어를 유도할 수 있어야 합니다.
- 휴넷CEO 비즈니스리뷰에 올라오지 않은 소재여야 합니다. 중복은 안됩니다.

## 탐색 기간/시간대
- 기준일: {{기준일}} (Asia/Seoul)
- 수집 기간: {{시작일}} ~ {{종료일}}

## 소스(우선순위)
1. CEO 및 C레벨 전문 콘텐츠 플랫폼: Harvard Business Review (HBR), MIT Sloan Management Review, Strategy+Business, Thinkers50, INSEAD Knowledge
2. 국내 경영 전문 매체 및 연구소: 동아비즈니스리뷰(DBR), 한경비즈니스, LG경제연구원, 포스코경영연구원(POSRI), SERICEO, 매일경제 MBAtimes, KT DIGIECO, 산업연구원(KIET)
3. 글로벌 전략·컨설팅 기관: McKinsey & Company, BCG, Bain, Deloitte Insights, PwC, EY
4. 혁신·트렌드 리서치 기관: World Economic Forum (WEF), Gartner, Forrester, CB Insights, Nikkei Asia, IMF, OECD
5. 국내외 일간지: 조선일보, 중앙일보, 동아일보, 한겨레, 매일경제, 한국경제, 연합뉴스, BBC

※ 블로그, 커뮤니티, 요약형 콘텐츠 제외. 원출처 고급 리포트 또는 아티클만 사용.

## 선별·평가 규칙 (내부 기준, 총점 3.5점 이상만 출력)
① 임팩트: C레벨 리더의 의사결정·전략에 실질적 영향을 줄 수 있는가?
② 시의성: 지금 이 시점에서 중요한 이슈인가?
③ 차별성: 통찰을 줄 수 있는 새로운 관점이 있는가?
④ 실행 가능성: 조직 운영·전략 실행에 적용 가능한 시사점이 있는가?
⑤ 지속성/확장성: 중장기적으로도 이어질 주제인가?

{{제외_키워드}}

## 출력 규칙 (반드시 준수)
반드시 JSON 배열만 출력하세요. 설명문·머리말·꼬리말 일절 금지. 첫 글자는 반드시 [.

[
  {
    "keyword": "핵심 키워드",
    "category": "경영|리더십|인문|트렌드|혁신 중 하나",
    "title": "아티클 제목",
    "description": "키워드를 소개하는 글 300자 내외",
    "implications": ["경영자를 위한 시사점 20자 내외 1", "시사점2", "시사점3", "시사점4", "시사점5"],
    "source": "출처명",
    "sourceUrl": "원문 URL (불확실 시 빈 문자열)",
    "sourceDate": "YYYY-MM"
  }
]
```

### 시리즈 기획 프롬프트

단발 소재 프롬프트와 동일한 소스/선별 기준 적용. 출력 구조만 다름:

```json
[
  {
    "keyword": "키워드",
    "category": "경영|리더십|인문|트렌드|혁신 중 하나",
    "seriesTitle": "시리즈 제목",
    "description": "기획 의도 300자 내외",
    "episodes": [
      {"title": "1회차 부제", "desc": "한 줄 요약"},
      {"title": "2회차 부제", "desc": "한 줄 요약"},
      {"title": "3회차 부제", "desc": "한 줄 요약"},
      {"title": "4회차 부제", "desc": "한 줄 요약"}
    ],
    "source": "출처명",
    "sourceUrl": "",
    "sourceDate": "YYYY-MM"
  }
]
```

### 중복 방지
세션(메모리)에 user_id 기준으로 이전 키워드 목록 보관. 재생성 시 `{{제외_키워드}}` 자리에 아래 텍스트 삽입:

```
이미 제안한 키워드 목록 (반드시 제외): {이전_키워드_목록}
```

---

## 환경변수 (.env)

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=perplexity/sonar-pro
TARGET_USER_ID=U0B2065SZ8B
CONFIRMED_ARTICLES_PATH=data/confirmed_articles.json
```

---

## 세션 구조 (인메모리)

```python
sessions = {
    "USER_ID": {
        "articles": [...],             # 현재 단발 소재 7건
        "articles_used_keywords": [...],  # 단발 이전 키워드 누적 (재생성 중복 방지)
        "articles_last_ts": "...",     # 단발 메시지 타임스탬프 (update용)
        "articles_last_channel": "...",
        "series": [...],               # 현재 시리즈 7건
        "series_used_keywords": [...], # 시리즈 이전 키워드 누적
        "series_last_ts": "...",       # 시리즈 메시지 타임스탬프 (update용)
        "series_last_channel": "...",
    }
}
```

---

## confirmed_articles.json 구조

```json
[
  {
    "confirmed_at": "2026-05-14T10:30:00+09:00",
    "type": "article",
    "keyword": "초격차 전략",
    "category": "경영",
    "title": "아티클 제목",
    "description": "...",
    "source": "HBR",
    "sourceUrl": "https://...",
    "sourceDate": "2026-05"
  }
]
```

---

## 에러 처리

- API 호출 실패 → DM에 "소재 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요." 발송
- JSON 파싱 실패 → 동일 에러 메시지 발송
- 출처 URL이 없는 경우 → "출처: {source명} (링크 미확인)" 표시
