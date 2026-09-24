from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from console.audit import AuditLog
from console.runs import ApprovalStore, RunRepository


UTC = timezone.utc


def test_audit_append_and_tail_is_chronological_and_bounded(tmp_path: Path):
    log = AuditLog(tmp_path / "audit.jsonl")

    log.append("login", request_id="req-1", actor="alice", details={"result": "ok"})
    log.append("start", request_id="req-2", actor="alice", run_id="run-1", details={"ignored": "x"})

    events = log.tail(2)
    assert [event["event"] for event in events] == ["login", "start"]
    assert [event["request_id"] for event in events] == ["req-1", "req-2"]
    assert events[1]["run_id"] == "run-1"
    assert "ignored" not in json.dumps(events)
    assert log.tail(0) == []
    assert len(log.tail(9999)) == 2


def test_audit_rejects_secret_like_and_unbounded_details(tmp_path: Path):
    log = AuditLog(tmp_path / "audit.jsonl")

    log.append(
        "start",
        request_id="req",
        actor="alice",
        details={"api_key": "secret", "command": "python --token secret", "note": "x" * 10000},
    )

    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "secret" not in raw
    assert "api_key" not in raw
    assert "command" not in raw
    assert len(raw) < 2000


def test_run_repository_lists_valid_states_and_ignores_bad_files(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "run-good.json").write_text(
        json.dumps({"version": 1, "run_id": "run-good", "status": "completed", "stages": {}}),
        encoding="utf-8",
    )
    (runs / "broken.json").write_text("{not json", encoding="utf-8")
    (runs / "notes.txt").write_text("not a state", encoding="utf-8")

    result = RunRepository(runs).list_runs()

    assert [item["run_id"] for item in result] == ["run-good"]
    assert result[0]["status"] == "completed"
    assert RunRepository(runs).get_run("run-good")["run_id"] == "run-good"
    assert RunRepository(runs).get_run("broken") is None


def test_run_repository_rejects_traversal_and_symlink_escape(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"version": 1, "stages": {}}), encoding="utf-8")
    (runs / "link.json").symlink_to(outside)

    repository = RunRepository(runs)

    assert repository.get_run("../outside") is None
    assert repository.get_run("link") is None
    assert repository.list_runs() == []


def test_run_repository_ignores_oversized_and_malformed_state(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "large.json").write_text("{" + "x" * (2 * 1024 * 1024), encoding="utf-8")
    (runs / "wrong.json").write_text(json.dumps({"stages": []}), encoding="utf-8")

    repository = RunRepository(runs, max_state_bytes=1024)

    assert repository.list_runs() == []


def test_approval_store_accepts_only_send_and_sync_and_expires(tmp_path: Path):
    store = ApprovalStore(tmp_path / "approvals")
    now = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

    approval = store.approve("run-1", "send", "alice", "batch-2026-09-21", now)

    assert approval["gate"] == "send"
    assert approval["actor"] == "alice"
    assert store.validate("run-1", "send", now + timedelta(hours=23, minutes=59))
    assert not store.validate("run-1", "send", now + timedelta(hours=24))
    assert not store.validate("run-1", "sync", now)

    with pytest.raises(ValueError):
        store.approve("run-1", "delete", "alice", "batch", now)


def test_approval_store_validates_ids_and_batch_labels(tmp_path: Path):
    store = ApprovalStore(tmp_path / "approvals")
    now = datetime.now(UTC)

    with pytest.raises(ValueError):
        store.approve("../escape", "send", "alice", "batch", now)
    with pytest.raises(ValueError):
        store.approve("run-1", "send", "alice", "", now)
    with pytest.raises(ValueError):
        store.approve("run-1", "send", "alice", "bad label with spaces", now)


class TestArtifactDecisions:
    """Task 4: RunManager artifact listing and decision recording."""

    @staticmethod
    def _manager(tmp_path: Path):
        from console.runs import RunManager, RunRepository
        from rockbase.artifact_store import ArtifactStore
        from rockbase.decision_models import ArtifactEnvelope

        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "run-1.json").write_text(
            json.dumps({"version": 1, "run_id": "run-1", "status": "awaiting_approval",
                        "decision_status": "awaiting_approval", "stages": {}}),
            encoding="utf-8",
        )
        artifacts = ArtifactStore(tmp_path / "artifacts")
        artifacts.put(ArtifactEnvelope.new("run-1", "s3.draft", {"draft": "hello"},
                                           {"ok": True, "errors": [], "warnings": []}))
        manager = RunManager(
            repo_root=tmp_path, runs=RunRepository(runs_dir),
            approvals=ApprovalStore(tmp_path / "approvals"),
            audit=AuditLog(tmp_path / "audit.jsonl"), runner=["true"],
            artifact_store=artifacts,
        )
        return manager

    def test_list_artifacts_returns_envelopes_without_payload_bodies(self, tmp_path):
        manager = self._manager(tmp_path)
        items = manager.list_artifacts("run-1")
        assert len(items) == 1
        item = items[0]
        assert item["artifact_id"].startswith("art-")
        assert item["run_id"] == "run-1"
        assert item["stage_id"] == "s3.draft"
        assert item["version"] == 1
        assert item["validation"]["ok"] is True
        assert "payload" not in item
        assert manager.list_artifacts("missing") == []

    def test_operator_can_approve_current_artifact(self, tmp_path):
        manager = self._manager(tmp_path)
        artifact = manager.list_artifacts("run-1")[0]
        record = manager.decide_artifact(
            "run-1", artifact["artifact_id"], artifact["version"], "approve",
            feedback=None, actor="operator", request_id="req-1")
        assert record["action"] == "approve"
        assert record["artifact_id"] == artifact["artifact_id"]
        assert record["actor"] == "operator"
        events = AuditLog(tmp_path / "audit.jsonl").tail(10)
        assert any(event["event"] == "decide_artifact" and event.get("run_id") == "run-1"
                   for event in events)

    def test_stale_version_is_rejected_with_409_semantics(self, tmp_path):
        manager = self._manager(tmp_path)
        artifact = manager.list_artifacts("run-1")[0]
        with pytest.raises(RuntimeError):
            manager.decide_artifact(
                "run-1", artifact["artifact_id"], artifact["version"] + 5, "approve",
                feedback=None, actor="operator", request_id="req-2")

    def test_reject_with_feedback_stores_bounded_feedback(self, tmp_path):
        from rockbase.decision_models import MAX_FEEDBACK_CHARS
        manager = self._manager(tmp_path)
        artifact = manager.list_artifacts("run-1")[0]
        record = manager.decide_artifact(
            "run-1", artifact["artifact_id"], artifact["version"], "reject_with_feedback",
            feedback="x" * 5000, actor="operator", request_id="req-3")
        assert record["action"] == "reject_with_feedback"
        assert len(record["feedback"]) == MAX_FEEDBACK_CHARS

    def test_viewer_actor_cannot_decide(self, tmp_path):
        manager = self._manager(tmp_path)
        artifact = manager.list_artifacts("run-1")[0]
        with pytest.raises(PermissionError):
            manager.decide_artifact(
                "run-1", artifact["artifact_id"], artifact["version"], "approve",
                feedback=None, actor="viewer", request_id="req-4")

    def test_duplicate_decision_is_idempotent(self, tmp_path):
        manager = self._manager(tmp_path)
        artifact = manager.list_artifacts("run-1")[0]
        first = manager.decide_artifact(
            "run-1", artifact["artifact_id"], artifact["version"], "approve",
            feedback=None, actor="operator", request_id="req-5")
        again = manager.decide_artifact(
            "run-1", artifact["artifact_id"], artifact["version"], "approve",
            feedback=None, actor="operator", request_id="req-6")
        assert first["recorded_at"] == again["recorded_at"]
