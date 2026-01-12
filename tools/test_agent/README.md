# test_agent

로컬/CI에서 반복 실행하며 아래를 수행하는 최소 구현입니다.
- `compile_commands.json` 기반 위험도 분석 및 리포트 생성
- (초기 버전) 위험 파일에 대해 “크래시/경계값” 중심의 gtest 스켈레톤 생성
- `ctest` 실행 및 실패 triage
- 실행 결과를 `tools/test_agent/state/`에 누적 저장

## 설치

```powershell
pip install -e .\tools\test_agent
```

## 실행

```powershell
test-agent run --repo . --build-dir build --budget 3
```

