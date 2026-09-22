from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from console.audit import AuditLog
from console.runs import ApprovalStore, RunManager, RunRepository
from scripts.rockbase_health import inspect_state


def _manager(tmp_path: Path) -> RunManager:
    return RunManager(
        repo_root=tmp_path,
        runs=RunRepository(tmp_path / "runs"),
        approvals=ApprovalStore(tmp_path / "approvals"),
        audit=AuditLog(tmp_path / "audit.jsonl"),
        runner=[sys.executable, "-c", "import time; time.sleep(30)"],
    )


def test_start_rejects_unknown_parameters_and_duplicate_active_run(tmp_path):
    manager = _manager(tmp_path)

    with pytest.raises(ValueError):
        manager.start({"shell": "rm -rf /"}, actor="alice", request_id="req-1")

    first = manager.start({"batch_label": "batch-1"}, actor="alice", request_id="req-2")
    try:
        with pytest.raises(RuntimeError):
            manager.start({"batch_label": "batch-2"}, actor="alice", request_id="req-3")
    finally:
        manager.kill(first["run_id"], actor="alice", request_id="req-4")


def test_pause_and_resume_use_same_state_and_audit_parameter_diff(tmp_path):
    manager = _manager(tmp_path)
    started = manager.start({"batch_label": "batch-1", "execute_send": False}, actor="alice", request_id="r1")
    run_id = started["run_id"]
    try:
        paused = manager.pause(run_id, actor="alice", request_id="r2")
        assert paused["run_id"] == run_id
        assert (tmp_path / "runs" / f"{run_id}.pause").exists()
        manager.approve(run_id, "send", "alice", "batch-1", request_id="r2a")
        resumed = manager.resume(
            run_id,
            {"batch_label": "batch-1", "execute_send": True},
            actor="alice",
            request_id="r3",
        )
        assert resumed["run_id"] == run_id
        events = AuditLog(tmp_path / "audit.jsonl").tail(20)
        assert any(event["event"] == "resume" and event.get("old", {}).get("execute_send") is False
                   and event.get("new", {}).get("execute_send") is True for event in events)
    finally:
        manager.kill(run_id, actor="alice", request_id="r4")


def test_resume_rejects_changed_write_gate_without_fresh_approval(tmp_path):
    manager = _manager(tmp_path)
    started = manager.start({"batch_label": "batch-1", "execute_send": False}, actor="alice", request_id="r1")
    try:
        with pytest.raises(PermissionError):
            manager.resume(started["run_id"], {"batch_label": "batch-1", "execute_send": True},
                           actor="alice", request_id="r2")
    finally:
        manager.kill(started["run_id"], actor="alice", request_id="r3")


def test_kill_reconciles_running_stages_and_health_is_critical(tmp_path):
    manager = _manager(tmp_path)
    started = manager.start({"batch_label": "batch-1"}, actor="alice", request_id="r1")
    run_id = started["run_id"]
    state_path = tmp_path / "runs" / f"{run_id}.json"
    deadline = time.time() + 3
    while time.time() < deadline and not state_path.exists():
        time.sleep(0.01)
    state = json.loads(state_path.read_text())
    next(iter(state["stages"].values()))["status"] = "running"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = manager.kill(run_id, actor="alice", request_id="r2")

    assert result["status"] == "interrupted"
    final = json.loads(state_path.read_text())
    assert final["status"] == "interrupted"
    assert all(stage["status"] != "running" for stage in final["stages"].values())
    assert inspect_state(state_path)["status"] == "critical"
    assert inspect_state(state_path)["exit_code"] == 2
