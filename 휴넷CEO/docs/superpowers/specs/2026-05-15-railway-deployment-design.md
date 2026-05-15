# HunetCEO-Bot Railway 배포 설계

**날짜**: 2026-05-15  
**목표**: 로컬 컴퓨터가 꺼져 있어도 슬랙 봇이 24/7 작동하도록 Railway 클라우드에 배포

---

## 아키텍처

```
로컬 컴퓨터
  └─ git push
        │
        ▼
GitHub (private repo)
  └─ push 이벤트 → Railway 자동 배포 트리거
        │
        ▼
Railway Worker Service (24/7)
  ├─ python app.py (SocketModeHandler 상시 실행)
  ├─ Volume /data (confirmed_articles.json 영구 저장)
  └─ 환경변수 (API 키 등 민감 정보)
```

## 컴포넌트

### 1. GitHub Private Repository
- 소스 코드 저장소
- `.env`, `venv/`, `data/`, `__pycache__/` 는 `.gitignore`로 제외
- Railway와 연동하여 push 시 자동 배포 트리거

### 2. Railway Worker Service
- Python 앱을 장기 실행 프로세스(worker)로 실행
- `Procfile`로 실행 명령 지정: `worker: python app.py`
- 재시작 정책: 크래시 시 자동 재시작

### 3. Railway Volume (영구 스토리지)
- 마운트 경로: `/data`
- 용도: `confirmed_articles.json` 저장 (재배포 후에도 데이터 보존)
- 무료 플랜: 1GB 제공

### 4. 환경변수 (Railway 대시보드에서 설정)
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=perplexity/sonar-pro
CONFIRMED_ARTICLES_PATH=/data/confirmed_articles.json
```

## 코드 변경 사항

### 추가 파일
- `Procfile` — Railway 실행 명령 정의
- `.gitignore` — 민감 파일 및 불필요한 파일 제외

### 변경 파일
- `requirements.txt` — 현재 그대로 사용 가능 (변경 없음)

### 변경 없는 파일
- `app.py`, `content_engine.py`, `storage.py`, `scraper.py` — 코드 변경 없음
- `CONFIRMED_ARTICLES_PATH` 환경변수로 경로 지정하므로 storage.py 코드 수정 불필요

## 배포 흐름

1. **로컬 준비**: `Procfile`, `.gitignore` 파일 생성
2. **GitHub 설정**: private repo 생성 → 코드 push
3. **Railway 설정**:
   a. railway.app 가입 (GitHub 계정으로 로그인)
   b. New Project → Deploy from GitHub repo 선택
   c. Volume 추가 → `/data` 마운트
   d. 환경변수 입력
4. **배포 확인**: Railway 로그에서 봇 정상 실행 확인

## 비용

- Railway 무료 플랜(Hobby): 월 $5 크레딧 제공 → 소규모 봇 운영 가능
- 트래픽이 적은 봇은 무료 범위 내에서 운영 가능
- Volume 1GB 무료 포함

## 데이터 보존 전략

Railway는 재배포 시 컨테이너 파일시스템이 초기화됩니다. Volume을 `/data`에 마운트하면 재배포 후에도 `confirmed_articles.json`이 유지됩니다. 환경변수 `CONFIRMED_ARTICLES_PATH=/data/confirmed_articles.json`으로 storage.py가 올바른 경로를 사용하도록 합니다.

## 성공 기준

- 로컬 컴퓨터를 꺼도 슬랙 봇이 응답함
- GitHub push 시 Railway가 자동으로 재배포함
- 재배포 후에도 확정 소재 데이터가 유지됨
