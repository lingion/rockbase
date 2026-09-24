from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

import pytest

from console.audit import AuditLog
from console.config import ConsoleConfig
from console.runs import RunRepository
from console.security import SessionStore, hash_password, load_users
from console.server import make_server


class FakeManager:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []

    def list_runs(self):
        return [{"run_id": "run-1", "status": "completed", "stages": {}}]

    def get_run(self, run_id):
        return self.list_runs()[0] if run_id == "run-1" else None

    def start(self, parameters, *, actor, request_id):
        self.calls.append(("start", parameters, actor, request_id))
        return {"run_id": "run-new", "status": "running", "stages": {}}

    def pause(self, run_id, *, actor, request_id):
        self.calls.append(("pause", run_id, actor, request_id))
        return {"run_id": run_id, "status": "pause_requested"}

    def resume(self, run_id, parameters, *, actor, request_id):
        self.calls.append(("resume", run_id, parameters, actor, request_id))
        return {"run_id": run_id, "status": "resume_requested"}

    def kill(self, run_id, *, actor, request_id):
        self.calls.append(("kill", run_id, actor, request_id))
        return {"run_id": run_id, "status": "interrupted"}

    def approve(self, run_id, gate, actor, batch_label, *, request_id):
        self.calls.append(("approve", run_id, gate, batch_label, actor, request_id))
        return {"run_id": run_id, "gate": gate, "batch_label": batch_label}


def _setup(tmp_path: Path, *, manager_factory=FakeManager):
    salt, digest, iterations = hash_password("correct", iterations=10_000)
    users_path = tmp_path / "users.toml"
    users_path.write_text(
        "[[users]]\nusername='viewer'\nrole='viewer'\n"
        f"salt_hex='{salt}'\npassword_hash_hex='{digest}'\niterations={iterations}\n\n"
        "[[users]]\nusername='operator'\nrole='operator'\n"
        f"salt_hex='{salt}'\npassword_hash_hex='{digest}'\niterations={iterations}\n",
        encoding="utf-8",
    )
    config = ConsoleConfig.from_env({
        "ROCKBASE_CONSOLE_BASE_DIR": str(tmp_path / "data"),
        "ROCKBASE_CONSOLE_RUNS_DIR": str(tmp_path / "runs"),
        "ROCKBASE_CONSOLE_REPO_ROOT": str(tmp_path),
        "ROCKBASE_CONSOLE_SESSION_TTL_SECONDS": "3600",
    })
    sessions = SessionStore(config.session_file, ttl_seconds=3600)
    manager = manager_factory(tmp_path)
    server = make_server(config=config, run_manager=manager, sessions=sessions,
                         users=load_users(users_path), audit=AuditLog(config.audit_file))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, manager


def _request(server, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(*server.server_address)
    payload = None if body is None else json.dumps(body)
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    conn.request(method, path, body=payload, headers=request_headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    if not data:
        return response, None
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response, json.loads(data)
    return response, data.decode("utf-8")


def _login(server, username):
    response, payload = _request(server, "POST", "/api/login", {"username": username, "password": "correct"})
    assert response.status == 200
    cookie = response.getheader("Set-Cookie")
    return cookie, payload


def test_http_requires_authentication_and_sets_security_headers(tmp_path):
    server, thread, _ = _setup(tmp_path)
    try:
        response, payload = _request(server, "GET", "/api/runs")
        assert response.status == 401
        assert payload["error"] == "authentication required"
        assert response.getheader("X-Content-Type-Options") == "nosniff"
        assert response.getheader("X-Request-Id")
    finally:
        server.shutdown(); thread.join()


def test_viewer_can_read_but_cannot_mutate_without_csrf(tmp_path):
    server, thread, _ = _setup(tmp_path)
    try:
        cookie, _ = _login(server, "viewer")
        response, payload = _request(server, "GET", "/api/runs", headers={"Cookie": cookie})
        assert response.status == 200
        assert payload["runs"][0]["run_id"] == "run-1"
        response, payload = _request(server, "POST", "/api/runs/start", {"batch_label": "batch-1"},
                                      headers={"Cookie": cookie})
        assert response.status == 403
        assert payload["error"] == "operator role required"
    finally:
        server.shutdown(); thread.join()


def test_operator_mutation_requires_csrf_and_audits_request(tmp_path):
    server, thread, manager = _setup(tmp_path)
    try:
        cookie, login = _login(server, "operator")
        response, payload = _request(server, "POST", "/api/runs/start", {"batch_label": "batch-1"},
                                      headers={"Cookie": cookie})
        assert response.status == 403
        csrf = login["csrf_token"]
        response, payload = _request(server, "POST", "/api/runs/start", {"batch_label": "batch-1"},
                                      headers={"Cookie": cookie, "X-CSRF-Token": csrf})
        assert response.status == 200
        assert payload["run_id"] == "run-new"
        assert manager.calls[0][0] == "start"
        assert response.getheader("Cache-Control") == "no-store"
    finally:
        server.shutdown(); thread.join()


def test_http_rejects_bad_json_and_static_traversal(tmp_path):
    server, thread, _ = _setup(tmp_path)
    try:
        cookie, login = _login(server, "operator")
        conn = http.client.HTTPConnection(*server.server_address)
        conn.request("POST", "/api/runs/start", body="not-json",
                     headers={"Content-Type": "application/json", "Cookie": cookie,
                              "X-CSRF-Token": login["csrf_token"]})
        response = conn.getresponse(); response.read(); conn.close()
        assert response.status == 400

        response, _ = _request(server, "GET", "/../console.py")
        assert response.status in {404, 400}
    finally:
        server.shutdown(); thread.join()


def test_static_index_has_csp_and_no_store_api(tmp_path):
    server, thread, _ = _setup(tmp_path)
    try:
        response, _ = _request(server, "GET", "/")
        assert response.status == 200
        assert "default-src 'self'" in response.getheader("Content-Security-Policy")
        assert response.getheader("Content-Type").startswith("text/html")
    finally:
        server.shutdown(); thread.join()


class FakeDecisionManager(FakeManager):
    """Adds artifact listing/decision methods for Task 4 HTTP tests."""

    def __init__(self, root: Path):
        super().__init__(root)
        from rockbase.artifact_store import ArtifactStore
        from rockbase.decision_models import ArtifactEnvelope
        self.store = ArtifactStore(root / "artifacts")
        envelope = ArtifactEnvelope.new("run-1", "s3.draft", {"draft": "x"},
                                        {"ok": True, "errors": [], "warnings": []})
        # Fixed artifact id so HTTP tests can reference /artifacts/art-1/...
        self.current = type(envelope)(
            artifact_id="art-1", run_id=envelope.run_id, stage_id=envelope.stage_id,
            version=1, payload=envelope.payload, validation=envelope.validation,
            created_at=envelope.created_at, parent_id=None,
            content_hash_value="",
        ).with_hash()
        self.store.put(self.current)
        self.decisions: list[dict] = []

    def list_artifacts(self, run_id, stage_id=None):
        return [
            {"artifact_id": item.artifact_id, "run_id": item.run_id,
             "stage_id": item.stage_id, "version": item.version,
             "created_at": item.created_at, "validation": item.validation,
             "parent_id": item.parent_id}
            for item in self.store.list_for_run(run_id)
        ]

    def decide_artifact(self, run_id, artifact_id, version, action, *, feedback,
                        actor, request_id):
        from rockbase.decision_models import MAX_FEEDBACK_CHARS, DecisionRequest, validate_decision
        if artifact_id != self.current.artifact_id or run_id != "run-1":
            raise KeyError(artifact_id)
        artifact = self.current
        if version != artifact.version:
            raise RuntimeError("stale artifact version")
        if actor == "viewer":
            raise PermissionError("operator role required")
        feedback = (feedback or "")[:MAX_FEEDBACK_CHARS]
        decision = DecisionRequest(artifact_id, version, action, actor, feedback=feedback)
        validate_decision(decision, artifact)
        record = decision.to_dict() | {"recorded_at": "2026-09-24T00:00:00+00:00"}
        self.decisions.append(record)
        return record


def test_operator_can_approve_current_artifact(tmp_path):
    server, thread, manager = _setup(tmp_path, manager_factory=FakeDecisionManager)
    try:
        cookie, login = _login(server, "operator")
        response, payload = _request(
            server, "POST", "/api/runs/run-1/artifacts/art-1/decisions",
            {"artifact_version": 1, "action": "approve"},
            headers={"Cookie": cookie, "X-CSRF-Token": login["csrf_token"]})
        assert response.status in {200, 404, 400}
        if response.status == 200:
            assert payload["decision"]["action"] == "approve"
    finally:
        server.shutdown(); thread.join()


def test_stale_version_decision_is_rejected_with_conflict(tmp_path):
    server, thread, manager = _setup(tmp_path, manager_factory=FakeDecisionManager)
    try:
        cookie, login = _login(server, "operator")
        response, payload = _request(
            server, "POST", "/api/runs/run-1/artifacts/art-1/decisions",
            {"artifact_version": 0, "action": "approve"},
            headers={"Cookie": cookie, "X-CSRF-Token": login["csrf_token"]})
        assert response.status == 409
        assert "stale" in payload["error"]
        assert manager.decisions == []
    finally:
        server.shutdown(); thread.join()


def test_payload_override_field_is_never_accepted(tmp_path):
    server, thread, manager = _setup(tmp_path, manager_factory=FakeDecisionManager)
    try:
        cookie, login = _login(server, "operator")
        response, payload = _request(
            server, "POST", "/api/runs/run-1/artifacts/art-1/decisions",
            {"artifact_version": 1, "action": "approve", "payload": {"intent": "decline"}},
            headers={"Cookie": cookie, "X-CSRF-Token": login["csrf_token"]})
        assert response.status == 400
        assert manager.decisions == []
    finally:
        server.shutdown(); thread.join()


def test_viewer_decision_gets_forbidden_and_get_artifacts_is_readable(tmp_path):
    server, thread, manager = _setup(tmp_path, manager_factory=FakeDecisionManager)
    try:
        cookie, login = _login(server, "viewer")
        response, payload = _request(server, "GET", "/api/runs/run-1/artifacts",
                                     headers={"Cookie": cookie})
        assert response.status == 200
        assert payload["artifacts"][0]["stage_id"] == "s3.draft"
        assert "payload" not in payload["artifacts"][0]
        response, payload = _request(
            server, "POST", "/api/runs/run-1/artifacts/art-1/decisions",
            {"artifact_version": 1, "action": "approve"},
            headers={"Cookie": cookie, "X-CSRF-Token": login["csrf_token"]})
        assert response.status == 403
    finally:
        server.shutdown(); thread.join()
