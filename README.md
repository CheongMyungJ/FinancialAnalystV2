# FinancialAnalystV2 (Stock Ranking Web)

KR/US 주식 유니버스를 멀티팩터로 스코어링하여 랭킹/상세/비교 화면으로 보여주는 웹앱입니다.

## 배포(서버 없이): GitHub Pages + GitHub Actions

- **프론트 배포**: `.github/workflows/pages.yml`
- **데이터 생성(수동/스케줄)**: `.github/workflows/generate-data.yml`
  - 결과 JSON: `web/frontend/public/data/rankings_KR.json`, `rankings_US.json`

자세한 사용법은 `web/README.md`를 참고하세요.

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

