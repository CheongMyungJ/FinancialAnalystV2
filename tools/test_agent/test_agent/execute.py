from __future__ import annotations

from pathlib import Path

from .models import RunResult
from .subprocess_util import run_cmd


def cmake_configure(repo_root: Path, build_dir: Path, config: str | None = None) -> RunResult:
    build_dir.mkdir(parents=True, exist_ok=True)
    args = [
        "cmake",
        "-S",
        str(repo_root),
        "-B",
        str(build_dir),
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DENABLE_TESTS=ON",
    ]
    # For multi-config generators, config is applied at build/test time; configure doesn't use it.
    return run_cmd(args=args, cwd=repo_root, phase="configure")


def cmake_build(build_dir: Path, config: str | None = None, parallel: int | None = None) -> RunResult:
    args = ["cmake", "--build", str(build_dir)]
    if config:
        args += ["--config", config]
    if parallel:
        args += ["--parallel", str(parallel)]
    return run_cmd(args=args, cwd=build_dir, phase="build")


def ctest_run(build_dir: Path, config: str | None = None, timeout_sec: int | None = None, exclude_regex: str | None = None) -> RunResult:
    args = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
    if config:
        args += ["-C", config]
    if timeout_sec:
        args += ["--timeout", str(timeout_sec)]
    if exclude_regex:
        args += ["-E", exclude_regex]
    return run_cmd(args=args, cwd=build_dir, phase="test")

