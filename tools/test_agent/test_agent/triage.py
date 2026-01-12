from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import GeneratedTest, RunResult


@dataclass(frozen=True)
class TriageOutcome:
    category: str
    failed_tests: list[str]
    disabled_generated: list[str]
    notes: list[str]


def _extract_failed_tests(ctest_output: str) -> list[str]:
    # CTest formats failures like:
    # The following tests FAILED:
    #  1 - sample_tests (Failed)
    failed: list[str] = []
    m = re.search(r"The following tests FAILED:\s*(?P<body>[\s\S]+)$", ctest_output)
    if not m:
        return failed
    body = m.group("body")
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        # "1 - name (Failed)"
        m2 = re.match(r"^\d+\s*-\s*(?P<name>.+?)\s*\(", line)
        if m2:
            failed.append(m2.group("name").strip())
    return failed


def extract_failed_tests(ctest_output: str) -> list[str]:
    return _extract_failed_tests(ctest_output)


def _maybe_disable_uncompilable_generated_tests(
    repo_root: Path, build_stderr: str, generated: list[GeneratedTest]
) -> list[str]:
    """
    If build failed and the error mentions a generated test file, disable it by renaming
    `<name>.cpp` -> `<name>.cpp.disabled`.
    This keeps the build green on the next iteration (safe policy).
    """
    disabled: list[str] = []
    for g in generated:
        rel = g.path.replace("/", "\\")
        if rel in build_stderr or g.path in build_stderr:
            p = (repo_root / g.path).resolve()
            if p.exists() and p.suffix == ".cpp":
                new_p = p.with_name(p.name + ".disabled")
                try:
                    p.rename(new_p)
                    disabled.append(g.path)
                except OSError:
                    pass
    return disabled


def triage_results(
    repo_root: Path,
    baseline: RunResult | None,
    build_after_gen: RunResult,
    test_after_gen: RunResult | None,
    generated: list[GeneratedTest],
) -> TriageOutcome:
    notes: list[str] = []
    failed_tests: list[str] = []
    disabled_generated: list[str] = []

    if baseline and not baseline.ok:
        return TriageOutcome(category="preexisting_test_failures", failed_tests=[], disabled_generated=[], notes=["baseline tests failed"])

    if not build_after_gen.ok:
        disabled_generated = _maybe_disable_uncompilable_generated_tests(repo_root, build_after_gen.stderr + "\n" + build_after_gen.stdout, generated)
        if disabled_generated:
            notes.append("disabled uncompilable generated tests (safe policy)")
            return TriageOutcome(category="generated_build_failure_disabled", failed_tests=[], disabled_generated=disabled_generated, notes=notes)
        return TriageOutcome(category="build_failure", failed_tests=[], disabled_generated=[], notes=["build failed (not clearly from generated tests)"])

    if test_after_gen and not test_after_gen.ok:
        failed_tests = _extract_failed_tests(test_after_gen.stdout + "\n" + test_after_gen.stderr)
        if failed_tests:
            notes.append("tests failed; likely indicates real bug or incorrect contract assumption")
        else:
            notes.append("ctest failed but failed test list not parsed")
        return TriageOutcome(category="test_failure", failed_tests=failed_tests, disabled_generated=[], notes=notes)

    return TriageOutcome(category="ok", failed_tests=[], disabled_generated=[], notes=notes)

