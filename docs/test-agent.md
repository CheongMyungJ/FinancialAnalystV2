# test_agent 운영 가이드

## 목적

`test_agent`는 레거시 C/C++ 코드에 unit test가 없는 상태에서 **조기 위험/버그 탐지**를 목표로, 아래 루프를 반복 실행합니다.

- CMake configure/build/ctest (baseline 확인)
- `compile_commands.json` 기반 위험도 분석
- 보수적인(고신뢰) 계약/엣지/부정/메타모픽 테스트 생성
- 재빌드/재실행 후 실패 triage
- 결과를 `tools/test_agent/state/`에 누적 저장

## 사전 조건(Windows)

- **CMake가 PATH에 있어야 함**: `cmake`, `ctest` 실행 가능
- C++ 컴파일러(MSVC 등)
- Python 3.10+

## CLI 사용

설치:

```powershell
pip install -e .\tools\test_agent
```

실행:

```powershell
test-agent run --repo . --build-dir build --budget 3
```

요청 파일로 실행(권장):

```powershell
test-agent run --repo . --build-dir build --request .\tools\test_agent\examples\request.json
```

리스크 분석만:

```powershell
test-agent analyze --repo . --build-dir build --top 50
```

## 작업 요청(JSON 스키마)

`--request`로 받는 파일은 아래 형태입니다.

```json
{
  "target": ".",
  "goal": "edge_cases",
  "constraints": {
    "time_budget_sec": 300,
    "max_tests_to_generate": 3,
    "allow_source_edits": false
  },
  "metadata": {
    "caller": "ci",
    "ticket": "ABC-123"
  }
}
```

- `goal`
  - `report_only`: 분석/리포트만
  - `edge_cases`: 엣지/계약 기반 테스트 우선
  - `crash_repro`: 크래시 재현/회귀 테스트 우선(향후 확장)
  - `api_contract`, `regression`: 향후 확장용

## 외부 시스템/에이전트 연동(HTTP)

서버 실행:

```powershell
test-agent serve --host 127.0.0.1 --port 8080
```

요청:

- `POST /run`
- 본문 예시:

```json
{
  "repo": ".",
  "build_dir": "build",
  "config": "Debug",
  "parallel": 8,
  "ctest_timeout_sec": 60,
  "request": {
    "target": ".",
    "goal": "edge_cases"
  }
}
```

응답에는 `run_id`, `selected_findings`, `generated`, `triage`가 포함됩니다.

## Human gate(사람 판단 요청) 동작

에이전트가 **컴파일 가능한 테스트를 안전하게 생성할 근거가 부족**하면 해당 실행의 `tools/test_agent/state/<run_id>/human_questions.md`에 질문을 기록합니다.

이 경우 권장 흐름:
- 질문에 답할 수 있는 최소 API(함수 이름/헤더/에러 규약)를 지정
- 다음 실행에서 `request.json`의 `metadata`로 힌트를 제공

초기 버전은 답변 파일을 자동 반영하는 기능이 제한적이며, 우선은 “대상 심볼을 더 구체화”하는 방식으로 해결합니다.

### `metadata` 힌트(사람 답변 전달)

아래 키를 `request.json`의 `metadata`에 넣으면, 생성기가 더 보수적으로 “컴파일되는 테스트”를 만들 수 있습니다.

```json
{
  "metadata": {
    "force_header": "path/to/public_api.h",
    "force_namespace": "my_ns",
    "force_functions": ["Foo", "Bar"]
  }
}
```
