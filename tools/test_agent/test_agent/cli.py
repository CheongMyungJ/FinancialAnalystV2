from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyze import analyze_repo
from .models import AgentConstraints, AgentRequest
from .request_io import load_request
from .runner import run_agent
from .server import serve
from .state_store import StateStore


def _find_compile_commands(repo_root: Path, build_dir: Path) -> Path | None:
    # Prefer build dir; CMake may write it there.
    cand = build_dir / "compile_commands.json"
    if cand.exists():
        return cand
    # Some projects place it at root.
    cand2 = repo_root / "compile_commands.json"
    if cand2.exists():
        return cand2
    return None


def cmd_analyze(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    build_dir = Path(args.build_dir).resolve()
    cc = _find_compile_commands(repo_root, build_dir)

    report = analyze_repo(repo_root=repo_root, compile_commands=cc, target=args.target)
    if args.json:
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"compile_commands: {cc.as_posix() if cc else '(none)'}")
        for f in report.findings[: args.top]:
            reasons = ",".join(f.reasons)
            print(f"{f.score:3d}  {f.path}  [{reasons}]")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    build_dir = Path(args.build_dir).resolve()
    store = StateStore(repo_root)
    run_id = store.new_run_id()
    if args.request:
        request = load_request(Path(args.request))
    else:
        request = AgentRequest(
            target=args.target,
            goal=args.goal,
            constraints=AgentConstraints(
                time_budget_sec=args.time_budget_sec,
                max_tests_to_generate=args.budget,
                allow_source_edits=args.allow_source_edits,
            ),
        )

    result = run_agent(
        repo_root=repo_root,
        build_dir=build_dir,
        request=request,
        store=store,
        run_id=run_id,
        config=args.config,
        parallel=args.parallel,
        ctest_timeout_sec=args.ctest_timeout_sec,
    )

    print(f"run_id: {result.get('run_id')}")
    for f in result.get("selected_findings", []):
        reasons = ",".join(f.get("reasons", []))
        print(f"{int(f.get('score', 0)):3d}  {f.get('path')}  [{reasons}]")
    for g in result.get("generated", []):
        print(f"generated: {g.get('path')}  ({g.get('rationale')})")
    triage = result.get("triage") or {}
    if triage:
        print(f"triage: {triage.get('category')}")
    if result.get("need_human"):
        print("need_human: see tools/test_agent/state/<run_id>/human_questions.md")

    return 0 if result.get("ok") else 2


def cmd_serve(args: argparse.Namespace) -> int:
    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="test-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="analyze risk and print findings")
    p_an.add_argument("--repo", default=".", help="repo root")
    p_an.add_argument("--build-dir", default="build", help="CMake build dir")
    p_an.add_argument("--target", default=".", help="target directory within repo")
    p_an.add_argument("--top", type=int, default=30)
    p_an.add_argument("--json", action="store_true")
    p_an.set_defaults(func=cmd_analyze)

    p_run = sub.add_parser("run", help="run agent loop (incremental)")
    p_run.add_argument("--repo", default=".", help="repo root")
    p_run.add_argument("--build-dir", default="build", help="CMake build dir")
    p_run.add_argument("--target", default=".", help="target directory within repo")
    p_run.add_argument("--goal", default="edge_cases", choices=["crash_repro", "edge_cases", "api_contract", "regression", "report_only"])
    p_run.add_argument("--budget", type=int, default=3, help="max tests to generate this run")
    p_run.add_argument("--time-budget-sec", type=int, default=300)
    p_run.add_argument("--allow-source-edits", action="store_true")
    p_run.add_argument("--request", default=None, help="path to JSON request (overrides CLI flags)")
    p_run.add_argument("--config", default=None, help="CMake build config (e.g., Debug/Release for multi-config)")
    p_run.add_argument("--parallel", type=int, default=None, help="build parallelism")
    p_run.add_argument("--ctest-timeout-sec", type=int, default=60)
    p_run.set_defaults(func=cmd_run)

    p_sv = sub.add_parser("serve", help="HTTP server for external agents/systems")
    p_sv.add_argument("--host", default="127.0.0.1")
    p_sv.add_argument("--port", type=int, default=8080)
    p_sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))

