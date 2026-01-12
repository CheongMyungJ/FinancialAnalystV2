from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .analyze import analyze_repo
from .execute import cmake_build, cmake_configure, ctest_run
from .generate import generate_tests_for_findings
from .models import AgentRequest
from .state_store import StateStore
from .triage import extract_failed_tests, triage_results


def run_agent(
    *,
    repo_root: Path,
    build_dir: Path,
    request: AgentRequest,
    store: StateStore,
    run_id: str,
    config: str | None,
    parallel: int | None,
    ctest_timeout_sec: int,
) -> dict[str, Any]:
    git_commit = store.try_git_commit()
    store.write_dataclass_json(run_id, "request.json", request)
    store.write_json(run_id, "context.json", {"git_commit": git_commit})

    # 0) Configure/build/test baseline (safe policy)
    cfg = cmake_configure(repo_root=repo_root, build_dir=build_dir, config=config)
    store.write_dataclass_json(run_id, "configure.json", cfg)
    if not cfg.ok:
        return {"run_id": run_id, "ok": False, "phase": "configure"}

    base_build = cmake_build(build_dir=build_dir, config=config, parallel=parallel)
    store.write_dataclass_json(run_id, "baseline_build.json", base_build)
    if not base_build.ok:
        return {"run_id": run_id, "ok": False, "phase": "build_baseline"}

    known_flaky = store.read_known_flaky()
    exclude = "|".join([re.escape(x) for x in known_flaky]) if known_flaky else None
    baseline_test = ctest_run(build_dir=build_dir, config=config, timeout_sec=ctest_timeout_sec, exclude_regex=exclude)
    store.write_dataclass_json(run_id, "baseline_test.json", baseline_test)
    if not baseline_test.ok:
        return {"run_id": run_id, "ok": False, "phase": "test_baseline"}

    # 1) Analyze risk (prefer compile_commands from build dir)
    cc = (build_dir / "compile_commands.json") if (build_dir / "compile_commands.json").exists() else None
    report = analyze_repo(repo_root=repo_root, compile_commands=cc, target=request.target)
    store.write_dataclass_json(run_id, "analyze_report.json", report)

    top = report.findings[: request.constraints.max_tests_to_generate]
    store.write_json(run_id, "selected_findings.json", {"selected": [f.__dict__ for f in top]})

    generated = []
    questions: list[dict[str, str]] = []
    if request.goal != "report_only":
        generated, questions = generate_tests_for_findings(
            repo_root=repo_root,
            findings=top,
            max_tests=request.constraints.max_tests_to_generate,
            hints=request.metadata,
        )
        store.write_json(run_id, "generated_tests.json", {"generated": [g.__dict__ for g in generated]})
        if questions:
            store.write_json(run_id, "human_questions.json", {"questions": questions})
            md_lines = ["# Human questions", ""]
            for q in questions:
                md_lines.append(f"- ({q.get('id')}) `{q.get('path')}`: {q.get('message')}")
            store.write_text(run_id, "human_questions.md", "\n".join(md_lines) + "\n")

    # 2) Build & test after generation
    after_build = cmake_build(build_dir=build_dir, config=config, parallel=parallel)
    store.write_dataclass_json(run_id, "after_build.json", after_build)

    after_test = None
    if after_build.ok:
        after_test = ctest_run(build_dir=build_dir, config=config, timeout_sec=ctest_timeout_sec, exclude_regex=exclude)
        store.write_dataclass_json(run_id, "after_test.json", after_test)
        if not after_test.ok:
            failed = extract_failed_tests(after_test.stdout + "\n" + after_test.stderr)
            rerun = ctest_run(build_dir=build_dir, config=config, timeout_sec=ctest_timeout_sec, exclude_regex=exclude)
            store.write_dataclass_json(run_id, "after_test_rerun.json", rerun)
            if rerun.ok and failed:
                store.write_json(run_id, "flaky_detected.json", {"flaky": failed})
                store.write_known_flaky(known_flaky + failed)
                after_test = rerun

    outcome = triage_results(
        repo_root=repo_root,
        baseline=baseline_test,
        build_after_gen=after_build,
        test_after_gen=after_test,
        generated=generated,
    )
    store.write_json(run_id, "triage.json", outcome.__dict__)

    ok = outcome.category in {"ok", "generated_build_failure_disabled"}
    return {
        "run_id": run_id,
        "ok": ok,
        "triage": outcome.__dict__,
        "selected_findings": [f.__dict__ for f in top],
        "generated": [g.__dict__ for g in generated],
        "need_human": bool(questions) and not generated,
    }

