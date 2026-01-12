from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .models import AgentConstraints, AgentRequest
from .request_io import load_request
from .runner import run_agent
from .state_store import StateStore


class _Handler(BaseHTTPRequestHandler):
    server_version = "test_agent/0.1"

    def _send(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/run", "/run/"):
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, {"error": "invalid json"})
            return

        # Minimal schema: { repo, build_dir, request, config, parallel, ctest_timeout_sec }
        try:
            repo_root = Path(str(data.get("repo", "."))).resolve()
            build_dir = Path(str(data.get("build_dir", "build"))).resolve()
            req_obj = data.get("request") or {}
            if not isinstance(req_obj, dict):
                raise ValueError("request must be object")
            req_path = req_obj.get("_path")
            if req_path:
                request = load_request(Path(str(req_path)))
            else:
                # inline request (same shape as request file)
                constraints = req_obj.get("constraints") or {}
                if not isinstance(constraints, dict):
                    constraints = {}
                request = AgentRequest(
                    target=str(req_obj.get("target", ".")),
                    goal=str(req_obj.get("goal", "edge_cases")),  # type: ignore[arg-type]
                    constraints=AgentConstraints(
                        time_budget_sec=int(constraints.get("time_budget_sec", 300)),
                        max_tests_to_generate=int(constraints.get("max_tests_to_generate", 3)),
                        allow_source_edits=bool(constraints.get("allow_source_edits", False)),
                    ),
                    metadata=dict(req_obj.get("metadata", {})) if isinstance(req_obj.get("metadata", {}), dict) else {},
                )
            config = data.get("config")
            parallel = data.get("parallel")
            ctest_timeout_sec = int(data.get("ctest_timeout_sec", 60))
        except Exception as e:
            self._send(400, {"error": str(e)})
            return

        store = StateStore(repo_root)
        run_id = store.new_run_id()
        result = run_agent(
            repo_root=repo_root,
            build_dir=build_dir,
            request=request,
            store=store,
            run_id=run_id,
            config=str(config) if config else None,
            parallel=int(parallel) if parallel else None,
            ctest_timeout_sec=ctest_timeout_sec,
        )
        self._send(200, result)


def serve(host: str, port: int) -> None:
    httpd = HTTPServer((host, port), _Handler)
    httpd.serve_forever()

