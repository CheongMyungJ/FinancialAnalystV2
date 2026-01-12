from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, repo_root: Path, state_dir: Path | None = None) -> None:
        self.repo_root = repo_root
        self.state_dir = state_dir or repo_root / "tools" / "test_agent" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        d = self.state_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_json(self, run_id: str, name: str, obj: Any) -> Path:
        path = self.run_dir(run_id) / name
        with path.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return path

    def write_dataclass_json(self, run_id: str, name: str, obj: Any) -> Path:
        return self.write_json(run_id, name, asdict(obj))

    def write_text(self, run_id: str, name: str, text: str) -> Path:
        path = self.run_dir(run_id) / name
        path.write_text(text, encoding="utf-8")
        return path

    def new_run_id(self) -> str:
        # friendly + sortable
        return utc_now_iso().replace(":", "").replace(".", "")

    def try_git_commit(self) -> str | None:
        # Best-effort. If git isn't present/initialized, return None.
        head = self.repo_root / ".git" / "HEAD"
        if not head.exists():
            return None

    def known_flaky_path(self) -> Path:
        return self.state_dir / "known_flaky_ctest_names.json"

    def read_known_flaky(self) -> list[str]:
        p = self.known_flaky_path()
        if not p.exists():
            return []
        try:
            data = read_json(p)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            return []
        return []

    def write_known_flaky(self, names: list[str]) -> None:
        # Store sorted unique list
        uniq = sorted(set(names))
        with self.known_flaky_path().open("w", encoding="utf-8") as f:
            json.dump(uniq, f, ensure_ascii=False, indent=2)
        try:
            # Do not shell out; read HEAD ref when possible.
            content = head.read_text(encoding="utf-8").strip()
            if content.startswith("ref:"):
                ref_path = self.repo_root / ".git" / content.split(" ", 1)[1].strip()
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
            return content
        except OSError:
            return None


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_posix_relpath(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel = path
    return rel.as_posix()

