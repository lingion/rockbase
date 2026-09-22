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
