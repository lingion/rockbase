"""Loopback-first stdlib HTTP server for the Rockbase operations console."""
from __future__ import annotations

import json
import mimetypes
import secrets
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .audit import AuditLog
from .config import ConsoleConfig
from .security import SessionStore, User, require_role, verify_password

_MAX_BODY = 64 * 1024
_STATIC_DIR = Path(__file__).with_name("static")


def make_server(*, config: ConsoleConfig, run_manager: Any, sessions: SessionStore,
                users: dict[str, User], audit: AuditLog) -> ThreadingHTTPServer:
    class ConsoleHandler(BaseHTTPRequestHandler):
        server_version = "RockbaseConsole/1"

        def _request_id(self) -> str:
            return secrets.token_hex(8)

        def _session(self):
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get("rockbase_console_sid")
            return sessions.get(morsel.value) if morsel else None

        def _send_json(self, status: int, payload: dict[str, Any], *, request_id: str) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Request-Id", request_id)
            self.end_headers()
            self.wfile.write(raw)

        def _error(self, status: int, message: str, request_id: str) -> None:
            self._send_json(status, {"error": message}, request_id=request_id)

        def _read_json(self, request_id: str) -> dict[str, Any] | None:
            if self.headers.get_content_type() != "application/json":
                self._error(415, "content type must be application/json", request_id)
                return None
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._error(400, "invalid content length", request_id)
                return None
            if length > _MAX_BODY:
                self._error(413, "request body too large", request_id)
                return None
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._error(400, "invalid JSON", request_id)
                return None
            if not isinstance(payload, dict):
                self._error(400, "JSON object required", request_id)
                return None
            return payload

        def _require_session(self, request_id: str):
            session = self._session()
            if session is None:
                self._error(401, "authentication required", request_id)
            return session

        def _require_operator(self, request_id: str):
            session = self._require_session(request_id)
            if session is None:
                return None
            if not require_role(session, "operator"):
                self._error(403, "operator role required", request_id)
                return None
            csrf = self.headers.get("X-CSRF-Token", "")
            if not sessions.csrf_valid(session, csrf):
                self._error(403, "invalid CSRF token", request_id)
                return None
            return session

        def _audit(self, event: str, session, request_id: str, run_id: str | None = None,
                   details: dict[str, Any] | None = None) -> None:
            audit.append(event, request_id=request_id, actor=session.username,
                         run_id=run_id, details=details)

        def do_GET(self) -> None:
            request_id = self._request_id()
            path = urlsplit(self.path).path
            if path == "/api/me":
                session = self._require_session(request_id)
                if session is not None:
                    self._send_json(200, {"username": session.username, "role": session.role,
                                          "csrf_token": session.csrf_token}, request_id=request_id)
                return
            if path == "/api/runs":
                session = self._require_session(request_id)
                if session is not None:
                    self._send_json(200, {"runs": run_manager.list_runs()}, request_id=request_id)
                return
            if path.startswith("/api/runs/"):
                session = self._require_session(request_id)
                if session is None:
                    return
                run_id = unquote(path.removeprefix("/api/runs/")).strip("/")
                if "/" in run_id or not run_id:
                    self._error(400, "invalid run id", request_id); return
                result = run_manager.get_run(run_id)
                if result is None:
                    self._error(404, "run not found", request_id); return
                self._send_json(200, result, request_id=request_id)
                return
            if path == "/api/health":
                self._send_json(200, {"status": "ok"}, request_id=request_id)
                return
            if path == "/api/audit":
                session = self._require_session(request_id)
                if session is not None:
                    self._send_json(200, {"events": audit.tail(100)}, request_id=request_id)
                return
            self._serve_static(path, request_id)

        def _serve_static(self, path: str, request_id: str) -> None:
            relative = "index.html" if path in {"", "/"} else path.removeprefix("/")
            if "\\" in relative or ".." in Path(relative).parts:
                self._error(404, "not found", request_id); return
            target = (_STATIC_DIR / relative)
            try:
                target = target.resolve()
                if _STATIC_DIR.resolve() not in target.parents and target != _STATIC_DIR.resolve():
                    raise ValueError
                raw = target.read_bytes()
            except (OSError, ValueError):
                self._error(404, "not found", request_id); return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'")
            self.send_header("X-Request-Id", request_id)
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            request_id = self._request_id()
            path = urlsplit(self.path).path
            if path == "/api/login":
                payload = self._read_json(request_id)
                if payload is None: return
                if set(payload) != {"username", "password"}:
                    self._error(400, "unknown or missing fields", request_id); return
                user = users.get(payload["username"])
                if user is None or not isinstance(payload["password"], str) or not verify_password(user, payload["password"]):
                    self._error(401, "invalid credentials", request_id); return
                session = sessions.create(user.username, role=user.role)
                audit.append("login", request_id=request_id, actor=user.username)
                self.send_response(200)
                body = json.dumps({"username": user.username, "role": user.role,
                                   "csrf_token": session.csrf_token}).encode()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Request-Id", request_id)
                self.send_header("Set-Cookie", sessions.cookie_for(session))
                self.end_headers(); self.wfile.write(body); return
            if path == "/api/logout":
                session = self._require_operator(request_id)
                if session is not None:
                    sessions.revoke(session.session_id)
                    self._audit("logout", session, request_id)
                    self._send_json(200, {"ok": True}, request_id=request_id)
                return
            session = self._require_operator(request_id)
            if session is None: return
            payload = self._read_json(request_id)
            if payload is None: return
            try:
                if path == "/api/runs/start":
                    result = run_manager.start(payload, actor=session.username, request_id=request_id)
                    self._audit("start", session, request_id, result.get("run_id")); self._send_json(200, result, request_id=request_id); return
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "runs"]:
                    run_id, action = parts[2], parts[3]
                    if not run_id or "/" in run_id: raise ValueError("invalid run id")
                    if action == "pause": result = run_manager.pause(run_id, actor=session.username, request_id=request_id)
                    elif action == "resume": result = run_manager.resume(run_id, payload or None, actor=session.username, request_id=request_id)
                    elif action == "kill": result = run_manager.kill(run_id, actor=session.username, request_id=request_id)
                    elif action == "approve":
                        if set(payload) != {"gate", "batch_label"}: raise ValueError("invalid approval fields")
                        result = run_manager.approve(run_id, payload["gate"], session.username, payload["batch_label"], request_id=request_id)
                    else: raise ValueError("unknown route")
                    self._audit(action, session, request_id, run_id); self._send_json(200, result, request_id=request_id); return
                raise ValueError("unknown route")
            except PermissionError as exc:
                self._error(403, str(exc), request_id)
            except (KeyError, RuntimeError) as exc:
                self._error(409, str(exc), request_id)
            except ValueError as exc:
                self._error(400, str(exc), request_id)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((config.host, 0), ConsoleHandler)
    return server


def main() -> int:
    config = ConsoleConfig.from_env()
    from .runs import ApprovalStore, RunManager, RunRepository
    from .security import load_users
    manager = RunManager(repo_root=config.repo_root, runs=RunRepository(config.runs_dir),
                         approvals=ApprovalStore(config.approval_dir),
                         audit=AuditLog(config.audit_file),
                         runner=["python3", "-m", "scripts.run_full_pipeline"])
    server = make_server(config=config, run_manager=manager,
                         sessions=SessionStore(config.session_file,
                                               ttl_seconds=config.session_ttl_seconds,
                                               cookie_secure=config.cookie_secure),
                         users=load_users(config.users_file), audit=manager.audit)
    server.server_address = (config.host, config.port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
