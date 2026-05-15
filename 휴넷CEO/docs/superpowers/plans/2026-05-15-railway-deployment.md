# Railway 배포 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HunetCEO-Bot을 Railway 클라우드에 배포하여 로컬 컴퓨터 없이도 24/7 작동하게 한다.

**Architecture:** 로컬 코드를 GitHub private repo에 push하면 Railway가 자동으로 감지해 재배포한다. Socket Mode로 슬랙과 상시 WebSocket 연결을 유지하며, 확정 소재 데이터는 Railway Volume(/data)에 영구 저장한다.

**Tech Stack:** Python 3, slack-bolt, Railway (Worker Service + Volume), GitHub

---

## 파일 구조

| 파일 | 역할 | 작업 |
|------|------|------|
| `Procfile` | Railway 실행 명령 정의 | 신규 생성 |
| `.gitignore` | 민감 파일·불필요 파일 제외 | 신규 생성 |
| `requirements.txt` | Python 의존성 | 변경 없음 |
| `app.py`, `content_engine.py`, `storage.py`, `scraper.py` | 봇 코어 로직 | 변경 없음 |

---

## Task 1: 배포용 파일 준비

**Files:**
- Create: `Procfile`
- Create: `.gitignore`

- [ ] **Step 1: Procfile 생성**

아래 내용으로 프로젝트 루트에 `Procfile` 파일을 생성한다 (확장자 없음):

```
worker: python app.py
```

- [ ] **Step 2: .gitignore 생성**

아래 내용으로 프로젝트 루트에 `.gitignore` 파일을 생성한다:

```
# 환경변수 (절대 커밋 금지)
.env

# Python
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/

# 로컬 데이터 (Railway Volume에서 관리)
data/confirmed_articles.json

# macOS
.DS_Store
```

- [ ] **Step 3: 파일 확인**

```bash
ls -la
cat Procfile
cat .gitignore
```

Expected output:
```
Procfile 파일 존재
worker: python app.py
```

- [ ] **Step 4: Commit**

```bash
git add Procfile .gitignore
git commit -m "feat: add Procfile and .gitignore for Railway deployment"
```

---

## Task 2: GitHub Private Repository 생성 및 Push

**Prerequisites:** GitHub 계정 필요 (없으면 github.com 에서 무료 가입)

- [ ] **Step 1: GitHub에서 새 repository 생성**

1. https://github.com/new 접속
2. Repository name: `hunet-ceo-slack-bot`
3. **Private** 선택 (중요: API 키 보호)
4. "Initialize this repository" 체크 해제 (이미 로컬에 코드 있음)
5. "Create repository" 클릭

- [ ] **Step 2: 로컬 git에 GitHub remote 추가**

GitHub에서 복사한 repo URL로 실행 (형식: `https://github.com/YOUR_USERNAME/hunet-ceo-slack-bot.git`):

```bash
git remote add origin https://github.com/YOUR_USERNAME/hunet-ceo-slack-bot.git
```

- [ ] **Step 3: 현재 브랜치 이름 확인**

```bash
git branch
```

Expected: `* main` 또는 `* master`

- [ ] **Step 4: GitHub에 push**

브랜치가 `main`인 경우:
```bash
git push -u origin main
```

브랜치가 `master`인 경우:
```bash
git push -u origin master
```

- [ ] **Step 5: Push 확인**

브라우저에서 `https://github.com/YOUR_USERNAME/hunet-ceo-slack-bot` 접속 → 파일 목록이 보이면 성공.

`.env` 파일이 없는지 확인 (민감 정보 보호).

---

## Task 3: Railway 프로젝트 설정

**Prerequisites:** Task 2 완료 (GitHub repo에 코드 있어야 함)

- [ ] **Step 1: Railway 가입**

1. https://railway.app 접속
2. "Login with GitHub" 클릭 → GitHub 계정으로 로그인

- [ ] **Step 2: 새 프로젝트 생성**

1. Railway 대시보드에서 "New Project" 클릭
2. "Deploy from GitHub repo" 선택
3. GitHub 권한 허용 → `hunet-ceo-slack-bot` repo 선택
4. Railway가 자동으로 Python을 감지하고 배포 시작

- [ ] **Step 3: Service 타입 확인**

Railway 대시보드 → 생성된 서비스 클릭 → Settings 탭:
- Service Type이 자동으로 `Worker`로 설정되어 있는지 확인
- 만약 `Web`으로 되어 있으면 `Worker`로 변경

- [ ] **Step 4: Volume 추가 (데이터 영구 보존)**

1. Railway 대시보드 → 프로젝트 화면에서 "New" 클릭 → "Volume" 선택
2. Volume 이름: `bot-data`
3. Mount Path: `/data`
4. "Create" 클릭
5. 생성된 Volume을 봇 서비스에 연결 (같은 프로젝트 내에서 자동 연결)

- [ ] **Step 5: 환경변수 설정**

Railway 대시보드 → 봇 서비스 클릭 → "Variables" 탭 → "New Variable"로 하나씩 추가:

```
SLACK_BOT_TOKEN      = xoxb-로 시작하는 값 (.env 파일 참고)
SLACK_APP_TOKEN      = xapp-로 시작하는 값 (.env 파일 참고)
OPENROUTER_API_KEY   = .env 파일 참고
OPENROUTER_MODEL     = perplexity/sonar-pro
CONFIRMED_ARTICLES_PATH = /data/confirmed_articles.json
```

`.env` 파일을 열어서 실제 값을 복사해서 붙여넣기.

- [ ] **Step 6: 재배포 트리거**

환경변수 저장 후 Railway가 자동으로 재배포함. 또는 수동으로:
Settings 탭 → "Redeploy" 클릭

---

## Task 4: 배포 확인

- [ ] **Step 1: Railway 로그 확인**

Railway 대시보드 → 봇 서비스 → "Deployments" 탭 → 최신 배포 클릭 → "View Logs":

정상 실행 시 아래와 같은 로그가 보여야 함:
```
⚡️ Bolt app is running!
```

오류 로그가 보이면 환경변수 값을 다시 확인.

- [ ] **Step 2: 슬랙에서 봇 응답 테스트**

1. Slack에서 HunetCEO-Bot에게 DM 전송
2. 봇이 정상 응답하는지 확인

- [ ] **Step 3: 컴퓨터 꺼도 작동하는지 확인 (선택)**

로컬에서 실행 중인 앱이 있으면 종료:
```bash
# 로컬에서 실행 중인 python app.py 프로세스 종료 (Ctrl+C)
```

이후 슬랙에서 봇에게 메시지 보내기 → 봇이 여전히 응답하면 Railway 배포 성공.

- [ ] **Step 4: 자동 재배포 확인 (선택)**

코드 수정 후 push하면 Railway가 자동으로 재배포하는지 확인:

```bash
# 아무 파일에 빈 줄 추가 후 push
git add .
git commit -m "test: verify auto-deploy"
git push
```

Railway 대시보드에서 새 배포가 자동으로 시작되는지 확인.

---

## 트러블슈팅

### 봇이 응답 없음
- Railway 로그에서 에러 확인
- 환경변수 값이 올바른지 재확인 (특히 `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`)
- Slack App 설정에서 Socket Mode가 활성화되어 있는지 확인

### "No module named" 오류
- `requirements.txt`에 누락된 패키지 추가 후 push

### Volume 데이터 초기화됨
- Railway Volume이 서비스에 올바르게 마운트되었는지 확인 (Mount Path: `/data`)
- 환경변수 `CONFIRMED_ARTICLES_PATH=/data/confirmed_articles.json` 설정 확인
