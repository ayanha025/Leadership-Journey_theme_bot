# 리더십저니 테마 자동화 Slack 봇 설계 문서

> 작성일: 2026-05-14
> 기반: 기존 `slack bot` 제작 프로젝트

---

## 1. 프로젝트 목적

휴넷 리더십저니 서비스의 테마 기획 반복 업무 자동화.
담당자가 Slack에서 명령어를 입력하면 다음 3가지를 한 번에 DM으로 수신한다:
1. 해당 월 기획 방향 기반으로 AI가 선정한 **테마 키워드 1개**
2. 그 키워드 주제로 4가지 스타일 x 5개 = **제목 20개**
3. 주제와 연관된 **아티클·영상 혼합 5개 이상**

[테마 재생성] 버튼으로 다른 키워드 기반의 새 기획안을 받거나, [이 테마로 확정] 버튼으로 확정한다.

---

## 2. 보유 데이터 현황

| 데이터 | 수량 | 위치 |
|---|---|---|
| 기발행 테마 | 86개 | XLS -> init_theme_history.py로 theme_history.json 초기화 |
| 아티클 | 514개 | XLS -> contents.csv |
| 영상 | 988개 | XLS -> contents.csv |
| 콘텐츠 총합 | 1,502개 | data/contents.csv |
| 월별 기획 방향 | 12개월 | data/monthly_direction.json |

---

## 3. 기술 스택

| 항목 | 내용 |
|---|---|
| 언어 | Python 3 |
| Slack 프레임워크 | slack-bolt (Socket Mode) |
| AI API | OpenRouter API |
| 웹 크롤링 | requests + BeautifulSoup4 |
| 데이터 처리 | pandas |
| 스케줄러 | 없음 (수동 트리거만) |

---

## 4. 파일 구조

```
/Users/hunet/Desktop/slack bot/
├── app.py                    # Slack Bolt 메인 앱
├── theme_engine.py           # 테마 생성 핵심 로직
├── scraper.py                # hunet.co.kr 스크래핑 + 중복 제거 저장
├── init_theme_history.py     # XLS에서 기발행 86개 테마 추출 (1회 실행)
├── prepare_data.py           # XLS -> CSV 변환 (기존 유지)
├── requirements.txt
├── .env
└── data/
    ├── contents.csv              # 기존 콘텐츠 풀 (1,502개)
    ├── scraped_contents.json     # 웹 수집 신규 콘텐츠 누적본
    ├── theme_history.json        # 기발행 + 신규 테마 금지목록 누적본
    └── monthly_direction.json    # 12개월 기획 방향
```

---

## 5. 데이터 스키마

### contents.csv (기존 prepare_data.py 출력)

| 컬럼 | 설명 | 예시 |
|---|---|---|
| type | 콘텐츠 유형 | 아티클 / 영상 |
| cat | 카테고리 | 조직, 관계, 성과 |
| title | 제목 | 심리적 안전감 만들기 |
| author | 저자/채널명 | 홍길동 |
| pub_date | 발행일 | 2024-03-15 |
| tags | 해시태그 (공백 구분) | 리더십 팀빌딩 소통 |
| volume | 테마 회차 (아티클만) | No.42 |

### scraped_contents.json

웹에서 수집한 신규 콘텐츠 제목 목록만 저장:

```json
["제목A", "제목B", "제목C"]
```

중복 판단 기준: 제목 문자열 strip() 후 완전 일치 비교

### theme_history.json

테마명 문자열 목록:

```json
["리더의 공감 능력", "팀워크의 힘", "성과를 만드는 대화법"]
```

- 초기화: init_theme_history.py가 XLS volume 컬럼에서 테마명 파싱 후 생성
- 이후: 신규 스크래핑 테마 및 확정 테마가 append 저장

### monthly_direction.json

월 번호(1~12)를 키로 사용:

```json
{
  "1": "새해 목표 설정과 리더십 비전 수립",
  "2": "관계 회복과 팀 신뢰 구축",
  "3": "변화 적응과 성장 마인드셋",
  "4": "성과 관리와 피드백 문화",
  "5": "소통과 심리적 안전감",
  "6": "중간 점검과 동기부여",
  "7": "여름 리더십 - 번아웃 예방",
  "8": "조직 문화와 팀 결속",
  "9": "하반기 전략과 실행력",
  "10": "갈등 해결과 의사결정",
  "11": "연말 성과 회고와 인정",
  "12": "한 해 마무리와 리더십 성찰"
}
```

(실제 값은 담당자가 monthly_direction.json 직접 수정)

---

## 6. 워크플로우

### 테마발송 트리거

두 가지 방식 모두 동일하게 동작:
- Slack DM에서 `테마발송` 텍스트 입력 (message.im 이벤트)
- `/테마발송` 슬래시 커맨드

```
[Slack: "테마발송" 또는 "/테마발송"]
         |
  scraper.py
  ├── 신규 콘텐츠 조회: /journey/library?keyword_cd=CK92 (상단 12개)
  │   └── scraped_contents.json 기존 제목 집합과 비교 -> 신규만 append
  └── 신규 테마 조회: /journey/library/theme/86 (h2 태그 추출, 8자 이상)
      └── theme_history.json 기존 목록과 비교 -> 신규만 append
         |
  theme_engine.py - OpenRouter API 1회 호출
  ├── 입력: 월별 기획 방향 + 금지 테마 목록 + 콘텐츠 풀 키워드
  └── 출력 JSON:
      {
        "keyword": "선정된 테마 키워드",
        "youtube": ["제목1", ..., "제목5"],
        "educational": ["제목1", ..., "제목5"],
        "meme": ["제목1", ..., "제목5"],
        "aggro": ["제목1", ..., "제목5"]
      }
         |
  콘텐츠 매칭:
  - keyword 토큰과 contents.csv의 tags + cat + title 겹침 수로 점수 계산
  - 점수 내림차순, 아티클/영상 혼합 최소 5개 선별
  - 5개 미만 시: 토큰 1개씩 제거 후 재선별
         |
  Slack DM -> conversations.open(TARGET_USER_ID) -> channel_id
  기획안 전체 일괄 발송 (섹션 2 산출물 형식)
  하단 버튼: [테마 재생성 (regenerate_theme)] [이 테마로 확정 (confirm_theme)]
  세션 저장: session["current"] = {keyword, titles, contents}
```

### 테마재생성 트리거

```
["테마재생성" 텍스트 입력 또는 regenerate_theme 버튼 클릭]
         |
  session["suggested_keywords"]에 현재 keyword 추가 (이전 추천 키워드 누적)
  임시 금지 목록 = theme_history.json + suggested_keywords
  OpenRouter API 재호출 -> 새 keyword + 새 제목 20개
  새 keyword 기반 콘텐츠 재선별
  Slack DM 업데이트 (기존 메시지 교체)
```

### 테마 확정

```
[confirm_theme 버튼 클릭]
         |
  session["current"]["keyword"] -> theme_history.json에 append 저장
  확정 완료 메시지 발송 ("확정되었습니다. 선정 키워드: {keyword}")
  session 초기화
```


---

## 7. 세션 상태 관리

```python
# app.py 전역 변수
session = {
    "suggested_keywords": [],   # 현재 대화에서 추천된 키워드 누적 (재생성 시 금지용)
    "current": {                # 현재 화면에 표시 중인 기획안
        "keyword": None,
        "titles": {},           # {"youtube": [...], "educational": [...], ...}
        "contents": []
    }
}
```

프로세스 재시작 시 초기화됨 (허용 가능, 드문 케이스).

---

## 8. 스크래핑 상세

### 신규 콘텐츠 수집

- URL: `https://leadership.hunet.co.kr/journey/library?keyword_cd=CK92`
- 인증: `requests.Session()`에 `Cookie: {HUNET_SESSION_COOKIE}` 헤더 주입
- 상단 12개 콘텐츠 제목 수집 (사이트 페이지 고정 표시 수)
- 쿠키 만료/인증 실패 시: 스크래핑 건너뛰고 기존 데이터로 계속 진행 + Slack 경고

### 신규 테마 수집

- URL: `https://leadership.hunet.co.kr/journey/library/theme/86`
- `<h2>` 태그 텍스트 추출, 8자 이상 + UI 텍스트 필터링
- 신규 항목만 theme_history.json에 append

---

## 9. OpenRouter API 호출 스펙

### 엔드포인트 및 인증

```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer {OPENROUTER_API_KEY}
Content-Type: application/json
```

### 요청 형식

```python
{
  "model": OPENROUTER_MODEL,
  "messages": [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_prompt}
  ]
}
```

### 시스템 프롬프트 (SYSTEM_PROMPT)

```
당신은 리더십 교육 콘텐츠 큐레이터입니다.
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
}
```

### 유저 프롬프트 구성

```
이번 달({월}월) 기획 방향: {monthly_direction}

금지 키워드/주제 목록 ({N}개):
{theme_history 전체 목록 + suggested_keywords}

콘텐츠 풀 주요 키워드:
{contents.csv tags/cat 상위 빈도 키워드 50개}

위 조건에 맞는 테마 기획안을 JSON으로 생성하세요.
```

### 응답 파싱 안전장치

1. 응답 텍스트에서 `{...}` 블록 정규식 추출
2. 5개 키 (`keyword`, `youtube`, `educational`, `meme`, `aggro`) 존재 검증
3. 각 스타일 키의 값이 5개 리스트인지 검증
4. 실패 시 1회 재시도, 재시도 실패 시 Slack에 오류 메시지

---

## 10. 테마명 생성 규칙

- 20자 이내, 짧고 기억하기 쉽게
- 4가지 스타일 x 5개 = 총 20개 제안
- 금지 목록: 기발행 전체 테마 + 현재 세션의 이전 추천 20개

| 스타일 | key | 특징 | 예시 |
|---|---|---|---|
| 유튜브 | youtube | 직관적·클릭 유도 | 팀원 마음이 닫히는 순간 |
| 교육적 | educational | 학습 목적 명확 | 심리적 안전감 구축 실천법 |
| 밈/유행어 | meme | 가볍고 재미있게 | 팀원 신뢰 레벨 MAX 찍기 |
| 어그로 | aggro | 불편하지만 공감 | 그 결정이 팀을 망치고 있습니다 |

---

## 11. Slack 메시지 산출물 형식

### 기획안 메시지 (전체 일괄 발송)

```
:date: {월}월 기획 방향
{monthly_direction}

─────────────────────────
:clapper: 1. 유튜브 스타일
① 제목1
② 제목2
③ 제목3
④ 제목4
⑤ 제목5

─────────────────────────
:books: 2. 교육적 스타일
① 제목1
...

─────────────────────────
:fire: 3. 밈/유행어 스타일
① 제목1
...

─────────────────────────
:zap: 4. 어그로 스타일
① 제목1
...

━━━━━━━━━━━━━━━━━━━━━━━
:books: 추천 콘텐츠 (아티클 · 영상)
:page_facing_up: {아티클 제목}
:clapper: {영상 제목}
... (최소 5개 이상)
```

하단 버튼 액션:
- `regenerate_theme`: 테마 재생성
- `confirm_theme`: 이 테마로 확정

---

## 12. 환경변수 (.env)

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

---

## 13. 초기화 절차 (최초 1회)

1. XLS 파일로 contents.csv 생성:
   `python prepare_data.py --article data/아티클.xls --video data/영상.xls`

2. 기발행 86개 테마 추출:
   `python init_theme_history.py --xls data/아티클.xls`
   (XLS volume 컬럼에서 테마 제목 파싱 -> data/theme_history.json 생성)

3. monthly_direction.json 수동 작성 (위 섹션 5의 스키마 참고)

4. .env 설정 후 앱 실행:
   `python app.py`

---

## 14. 기존 버그 수정 반영

| 버그 | 수정 내용 |
|---|---|
| 테마명 비어있는 문제 | JSON 파싱 시 {...} 블록 정규식 추출 + 키 검증 |
| 콘텐츠 제목 깨짐 | 분량·카테고리·태그 텍스트 필터링 |
| 신규 테마 오감지 | 8자 미만 및 UI 텍스트 제외 |

---

## 15. Slack 앱 설정 (기존 완료)

| 항목 | 내용 |
|---|---|
| 워크스페이스 | white-vg62200 |
| App ID | A0B2KEKNCG1 |
| Socket Mode | 활성화 |
| Slash Commands | /테마발송 등록 완료 |
| Event Subscriptions | message.im, message.channels |
| 발송 대상 | U0B2065SZ8B (conversations.open으로 DM 채널 ID 획득 후 발송) |
