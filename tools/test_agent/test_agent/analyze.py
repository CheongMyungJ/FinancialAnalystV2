from __future__ import annotations

import re
from pathlib import Path

from .models import AnalyzeReport, RiskFinding
from .state_store import ensure_posix_relpath, read_json


RISK_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("raw_new_delete", re.compile(r"\b(new|delete)\b"), 2),
    ("malloc_free", re.compile(r"\b(malloc|calloc|realloc|free)\b"), 3),
    ("memcpy_like", re.compile(r"\b(memcpy|memmove|strcpy|strncpy|sprintf|vsprintf)\b"), 4),
    ("strlen_like", re.compile(r"\b(strlen|strnlen)\b"), 2),
    ("reinterpret_cast", re.compile(r"\breinterpret_cast\b"), 3),
    ("c_style_cast", re.compile(r"\([^()]+\)\s*\w"), 1),
    ("pointer_arith", re.compile(r"\w+\s*[\+\-]\s*\w+"), 1),
    ("mutex_thread", re.compile(r"\b(std::thread|CreateThread|pthread_|std::mutex)\b"), 2),
    ("printf_format", re.compile(r"%[0-9\\.]*[sduxXf]"), 1),
]


def _score_file_text(text: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for name, pat, weight in RISK_PATTERNS:
        m = pat.search(text)
        if m:
            score += weight
            reasons.append(f"{name}")
    # crude complexity proxy
    branches = len(re.findall(r"\b(if|else if|for|while|switch|case)\b", text))
    if branches >= 50:
        score += 5
        reasons.append("high_branch_count>=50")
    elif branches >= 20:
        score += 2
        reasons.append("branch_count>=20")
    return score, reasons


def list_translation_units_from_compile_commands(path: Path) -> list[Path]:
    data = read_json(path)
    tus: list[Path] = []
    for entry in data:
        f = entry.get("file")
        if not f:
            continue
        tus.append(Path(f))
    # de-dup while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in tus:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def analyze_repo(repo_root: Path, compile_commands: Path | None, target: str = ".") -> AnalyzeReport:
    target_path = (repo_root / target).resolve()

    files: list[Path] = []
    if compile_commands and compile_commands.exists():
        files = list_translation_units_from_compile_commands(compile_commands)
    else:
        # fallback: scan common source extensions in target
        exts = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx"}
        files = [p for p in target_path.rglob("*") if p.suffix.lower() in exts]

    findings: list[RiskFinding] = []
    for f in files:
        try:
            if not f.exists():
                continue
            # keep analysis bounded to target subtree when possible
            if target_path in f.resolve().parents or f.resolve() == target_path:
                pass
            else:
                # for compile_commands with absolute paths outside repo, skip
                if repo_root.resolve() not in f.resolve().parents:
                    continue
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score, reasons = _score_file_text(text)
        if score <= 0:
            continue
        findings.append(
            RiskFinding(
                path=ensure_posix_relpath(f, repo_root),
                score=score,
                reasons=reasons,
            )
        )

    findings.sort(key=lambda x: (-x.score, x.path))
    return AnalyzeReport(
        repo_root=repo_root.as_posix(),
        compile_commands=compile_commands.as_posix() if compile_commands else None,
        findings=findings,
    )

