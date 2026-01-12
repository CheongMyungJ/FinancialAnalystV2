from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AgentConstraints, AgentRequest


def load_request(path: Path) -> AgentRequest:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    constraints = data.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}
    req = AgentRequest(
        target=str(data.get("target", ".")),
        goal=str(data.get("goal", "edge_cases")),  # type: ignore[arg-type]
        constraints=AgentConstraints(
            time_budget_sec=int(constraints.get("time_budget_sec", 300)),
            max_tests_to_generate=int(constraints.get("max_tests_to_generate", 3)),
            allow_source_edits=bool(constraints.get("allow_source_edits", False)),
        ),
        metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
    )
    return req

