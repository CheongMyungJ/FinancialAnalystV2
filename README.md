# TestAgent (CMake + GoogleTest + 생성형 테스트 에이전트)

이 레포는 **레거시 C/C++ 코드에 unit test가 전무한 상황**에서, 잠재 버그/위험을 조기에 찾기 위해 **반복 실행형(unit test 생성/실행/triage) AI agent**를 붙이는 템플릿입니다.

## 빠른 시작(데모)

사전 조건:
- **CMake가 PATH에 있어야 함**: `cmake`, `ctest`
- C++ 컴파일러(MSVC 등)
- Python 3.10+

### 1) 빌드/테스트(데모 코드)

```powershell
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build -j
ctest --test-dir build --output-on-failure
```

### 2) test_agent 설치 및 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .\tools\test_agent

# 위험 리포트 + (가능한 경우) 생성된 테스트 추가 + 실행/triage
python -m test_agent run --repo . --build-dir build --budget 3
```

산출물:
- `tools/test_agent/state/` 아래에 실행 히스토리/리포트가 저장됩니다.
- 생성 테스트는 기본적으로 `tests/generated/` 아래에 생성됩니다.

## 레거시 프로젝트에 붙이는 방법(요약)

- 이미 CMake 프로젝트가 있다면 이 레포의 `tests/`와 `tools/test_agent/`만 가져와서 통합할 수 있습니다.
- 자세한 내용은 `docs/test-agent.md` 참고.

