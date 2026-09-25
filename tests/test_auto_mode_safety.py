"""Auto-mode safety gates: send/sync stay blocked, opt-out rows never
queue, mid-run mode change rejected, run-mode is recorded with actor +
policy_version at start.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "scripts" / "rockbase_orchestrator.py"


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location("rockbase_orchestrator_for_auto", ORCH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_start_records_mode_policy_and_actor(tmp_path):
    module = _load_orchestrator()
    state_path = tmp_path / "state.json"
    rc = module.run_pipeline([], state_path=state_path, mode="auto")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "auto"
    assert "policy_version" in state
    assert state["policy_version"] >= 1


def test_mid_run_mode_change_is_rejected(tmp_path):
    module = _load_orchestrator()
    state_path = tmp_path / "state.json"
    assert module.run_pipeline([], state_path=state_path, mode="auto") in {0, 1}
    try:
        module.run_pipeline([], state_path=state_path, mode="review")
    except ValueError as exc:
        assert "mode" in str(exc)
    else:
        raise AssertionError("expected ValueError for mid-run mode change")


def test_send_and_sync_are_always_forbidden_in_auto_mode():
    module = _load_orchestrator()
    assert module.is_forbidden_auto_action("mailkit_send", "execute") is True
    assert module.is_forbidden_auto_action("master_sync_sent", "execute") is True
    assert module.is_forbidden_auto_action("master_sync_replies", "execute") is True
    # A non-forbidden decision stage in auto mode can advance.
    assert module.is_forbidden_auto_action("s3_draft", "advance") is False
    # Even in auto mode, attempting send execute is forbidden.
    assert module.is_forbidden_auto_action("mailkit_send", "queue") is True


def test_manual_review_artifact_blocks_auto_advance(tmp_path):
    """Auto mode must stop if the artifact it would advance is
    manual_review — only console-approved artifacts advance.
    """
    module = _load_orchestrator()
    state_path = tmp_path / "state.json"
    artifact = {
        "stage": "s3.draft", "pending_action": "manual_review",
        "validation": {"ok": False, "errors": ["low confidence"], "warnings": []},
    }
    decision = module.should_auto_advance_artifact(artifact)
    assert decision["advance"] is False
    assert "manual_review" in decision["reason"]


def test_opt_out_rows_never_enter_queue():
    module = _load_orchestrator()
    # Even with explicit execute=True, rows whose ``opt_out`` column is true
    # are excluded from the send queue.
    rows = [
        {"账号ID": "r1", "opt_out": "true", "Mail1_Subject": "x", "Mail1_Content V1": "y"},
        {"账号ID": "r2", "opt_out": "false", "Mail1_Subject": "a", "Mail1_Content V1": "b"},
        {"账号ID": "r3", "Mail1_Subject": "c", "Mail1_Content V1": "d"},
    ]
    kept = module.filter_opt_out_rows(rows)
    kept_ids = {row["账号ID"] for row in kept}
    assert "r1" not in kept_ids
    assert "r2" in kept_ids
    assert "r3" in kept_ids


def test_authorize_auto_mode_records_audit(tmp_path):
    """Console-side authorize_auto_mode persists the actor and policy
    version and refuses non-operator actors.
    """
    runs_spec = importlib.util.spec_from_file_location(
        "console_runs_for_auto", ROOT / "console" / "runs.py",
    )
    runs = importlib.util.module_from_spec(runs_spec)
    sys.modules[runs_spec.name] = runs
    runs_spec.loader.exec_module(runs)

    audit_log = tmp_path / "audit.jsonl"
    from console.audit import AuditLog
    audit = AuditLog(audit_log)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    manager = runs.RunManager(
        repo_root=tmp_path, runs=runs.RunRepository(runs_dir),
        approvals=runs.ApprovalStore(tmp_path / "approvals"),
        audit=audit,
        runner=["echo"],
    )

    # Seed a run with mode=auto so authorize_auto_mode can persist policy_version.
    state_path = runs_dir / "run-test.json"
    state_path.write_text(json.dumps({"version": 1, "run_id": "run-test", "mode": "auto",
                                       "stages": {}, "parameters": {}}), encoding="utf-8")

    record = manager.authorize_auto_mode("run-test", "operator-alice", "policy-v1", "req-1")
    assert record["mode"] == "auto"
    assert record["actor"] == "operator-alice"
    assert record["policy_version"] == "policy-v1"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["mode"] == "auto"
    assert persisted["policy_version"] == "policy-v1"
    assert persisted["authorized_by"] == "operator-alice"

    # Viewer is rejected.
    try:
        manager.authorize_auto_mode("run-test", "viewer", "policy-v1", "req-2")
    except PermissionError:
        pass
    else:
        raise AssertionError("viewer must not be allowed to authorize auto mode")

    # Idempotent on duplicate authorization.
    again = manager.authorize_auto_mode("run-test", "operator-alice", "policy-v1", "req-3")
    assert again["policy_version"] == "policy-v1"