# Stock Ranking Web (KR/US)

## 로컬 실행(개발)

### Backend

```powershell
cd .\web\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

### Frontend

```powershell
cd .\web\frontend
npm install
npm run dev -- --port 5173
```

브라우저: `http://localhost:5173`

## Docker(간단 구성)

```powershell
cd .\web
docker compose up --build
```

## 프로덕션 배포 (GitHub Actions + 도메인/HTTPS)

이 프로젝트는 `web/docker-compose.prod.yml` + Caddy(자동 Let's Encrypt) 조합으로 운영 배포를 구성합니다.

### 1) 서버 준비물
- Docker + Docker Compose(플러그인) 설치
- 방화벽/보안그룹에서 **80, 443 포트 오픈**
- 도메인 DNS에서 `A 레코드`로 서버 IP를 연결 (예: `stock.example.com -> 1.2.3.4`)

### 2) 서버에 최초 배포 디렉토리 준비
예: `/opt/stock-ranking`

서버에서 다음 중 하나를 준비해야 합니다.
- **공개 레포**: GitHub Actions가 서버에서 `git clone` 가능
- **비공개 레포**: 서버에 deploy key 또는 Git 자격 증명 설정

### 3) .env 관리 (서버에 생성)
운영용 `.env`는 레포에 커밋하지 않고, **GitHub Actions Secrets의 `ENV_PROD`** 값을 서버에 써서 관리합니다.

템플릿: `web/env.example`

### 4) GitHub Actions Secrets 설정
레포 Settings → Secrets and variables → Actions → New repository secret:
- `SSH_HOST`: 배포 서버 호스트/IP
- `SSH_USER`: SSH 유저
- `SSH_KEY`: SSH private key (PEM)
- `SSH_PORT`: 예: `22`
- `DEPLOY_PATH`: 예: `/opt/stock-ranking`
- `REPO_URL`: 예: `https://github.com/<org>/<repo>.git`
- `ENV_PROD`: 운영 환경변수(.env 내용 전체, 멀티라인)

### 5) 자동 배포 트리거
`main` 브랜치에 push 되면 `.github/workflows/deploy.yml` 이 실행되어:
- 서버에서 repo sync
- `web/.env` 생성/갱신
- `docker compose -f web/docker-compose.prod.yml up -d --build` 실행

### 운영용 ENV_PROD 예시
`web/env.example`를 참고해서 GitHub Secret `ENV_PROD`에 그대로(멀티라인) 넣으면 됩니다.

## 서버 없이 배포 (GitHub Pages + GitHub Actions 데이터 생성)

서버(API)를 띄우지 않고도, GitHub Actions가 주기적으로(또는 수동으로) 데이터를 생성해서 레포에 커밋하고,
GitHub Pages 프론트가 `web/frontend/public/data/*.json`을 읽어 표시하는 구성도 가능합니다.

- **프론트 배포**: `.github/workflows/pages.yml`
- **데이터 생성(수동 실행)**: `.github/workflows/generate-data.yml` (workflow_dispatch)
  - 실행 결과는 `web/frontend/public/data/rankings_KR.json`, `rankings_US.json`로 커밋됩니다.
  - 관리자 화면(정적 모드)에서 GitHub Actions 실행 페이지로 이동하는 버튼을 제공합니다.


## 관리자
- URL: `/admin/login`
- 기본 계정(개발용): `admin / admin`

## 배치 재계산
- 관리자 로그인 후 `/admin/factors`에서 **배치 재계산(ALL)** 클릭

## 환경변수(요약)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET`
- `DART_API_KEY` (KR 재무), `ALPHAVANTAGE_API_KEY` (US 재무)
- `ENABLE_SCHEDULER`, `ENABLE_NEWS`, `ENABLE_FUNDAMENTALS`
- `UNIVERSE_LIMIT_KR`, `UNIVERSE_LIMIT_US`

