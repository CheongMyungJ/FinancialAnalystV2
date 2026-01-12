from __future__ import annotations

import subprocess
from pathlib import Path

from .models import RunResult


def run_cmd(
    args: list[str],
    cwd: Path,
    phase: str,
    timeout_sec: int | None = None,
) -> RunResult:
    try:
        p = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return RunResult(
            ok=(p.returncode == 0),
            phase=phase,  # type: ignore[arg-type]
            exit_code=p.returncode,
            stdout=p.stdout or "",
            stderr=p.stderr or "",
        )
    except subprocess.TimeoutExpired as e:
        return RunResult(
            ok=False,
            phase=phase,  # type: ignore[arg-type]
            exit_code=124,
            stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
            stderr="TIMEOUT",
        )

