from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Goal = Literal["crash_repro", "edge_cases", "api_contract", "regression", "report_only"]


@dataclass(frozen=True)
class AgentConstraints:
    time_budget_sec: int = 300
    max_tests_to_generate: int = 3
    allow_source_edits: bool = False


@dataclass(frozen=True)
class AgentRequest:
    target: str = "."  # directory / module / symbol (initially directory)
    goal: Goal = "edge_cases"
    constraints: AgentConstraints = field(default_factory=AgentConstraints)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskFinding:
    path: str
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class AnalyzeReport:
    repo_root: str
    compile_commands: str | None
    findings: list[RiskFinding]


@dataclass(frozen=True)
class GeneratedTest:
    path: str
    target_hint: str
    rationale: str


@dataclass(frozen=True)
class RunResult:
    ok: bool
    phase: Literal["configure", "build", "test"]
    exit_code: int
    stdout: str
    stderr: str

