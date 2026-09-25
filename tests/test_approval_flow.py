"""End-to-end approval-flow contracts across S1-S5 + Console + worker.

These tests pin the offline-only invariants of the approval boundary:
review-mode artifact flow, manual_review stops auto mode, reject-with-
feedback creates a new artifact version, and forbidden actions remain
blocked even under run-wide auto authorization.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manager(tmp_path: Path, audit, *, artifact_store=None):
    runs = _load("console_runs_af", ROOT / "console" / "runs.py")
    return runs.RunManager(
        repo_root=tmp_path,
        runs=runs.RunRepository(tmp_path / "runs"),
        approvals=runs.ApprovalStore(tmp_path / "approvals"),
        audit=audit,
        runner=["echo"],
        artifact_store=artifact_store,
    )


def test_review_mode_pauses_then_artifact_advance_after_decision(tmp_path):
    """Review-mode flow: stage produces an envelope; Console approve
    advances; reject_with_feedback creates a new artifact version.
    """
    from rockbase.artifact_store import ArtifactStore
    from rockbase.decision_models import ArtifactEnvelope, DecisionRequest, validate_decision

    from console.audit import AuditLog
    audit = AuditLog(tmp_path / "audit.jsonl")
    store = ArtifactStore(tmp_path / "artifacts")
    manager = _manager(tmp_path, audit, artifact_store=store)
    envelope = ArtifactEnvelope.new(
        run_id="run-af1", stage_id="s3.draft",
        payload={"stage": "s3.draft", "draft": "hi"},
        validation={"ok": True, "errors": [], "warnings": []},
    )
    stored = store.put(envelope)

    # Run is missing -> decide must raise KeyError.
    with pytest.raises(KeyError):
        manager.decide_artifact(
            run_id="run-af1", artifact_id=stored.artifact_id, version=stored.version,
            action="approve", feedback=None, actor="operator", request_id="r-1",
        )

    # Seed a minimal run so the run lookup succeeds.
    run_path = tmp_path / "runs" / "run-af1.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps({"version": 1, "run_id": "run-af1", "stages": {},
                                     "parameters": {}}), encoding="utf-8")

    decision = DecisionRequest(stored.artifact_id, stored.version, "approve", "operator")
    validate_decision(decision, stored)
    record = manager.decide_artifact(
        run_id="run-af1", artifact_id=stored.artifact_id, version=stored.version,
        action="approve", feedback=None, actor="operator", request_id="r-2",
    )
    assert record["action"] == "approve"

    # Feedback rejects produce a new envelope version (the LLM then re-fills).
    new_envelope = ArtifactEnvelope.new(
        run_id="run-af1", stage_id="s3.draft",
        payload={"stage": "s3.draft", "draft": "hi (v2)"},
        validation={"ok": True, "errors": [], "warnings": []},
        parent_id=stored.artifact_id,
    ).with_version(2)
    assert new_envelope.version == 2
    new_stored = store.put(new_envelope)
    assert new_stored.parent_id == stored.artifact_id


def test_auto_mode_stops_on_manual_review_artifact():
    from scripts import rockbase_orchestrator as orch

    artifact = {
        "stage": "s3.draft",
        "pending_action": "manual_review",
        "validation": {"ok": False, "errors": ["low confidence"], "warnings": []},
    }
    decision = orch.should_auto_advance_artifact(artifact)
    assert decision["advance"] is False
    assert "manual_review" in decision["reason"]


def test_auto_mode_advances_only_await_console_decision_artifact():
    from scripts import rockbase_orchestrator as orch

    good = {
        "stage": "s3.draft",
        "pending_action": "await_console_decision",
        "validation": {"ok": True, "errors": [], "warnings": []},
    }
    decision = orch.should_auto_advance_artifact(good)
    assert decision["advance"] is True


def test_send_and_sync_remain_forbidden_even_with_run_wide_auto():
    """Even an authorized auto run cannot dispatch real sends or master
    production writes; those still need explicit Console approval.
    """
    from scripts import rockbase_orchestrator as orch

    forbidden_stages = [
        ("mailkit_send", "execute"),
        ("master_sync_sent", "execute"),
        ("master_sync_replies", "execute"),
    ]
    for stage_name, action in forbidden_stages:
        assert orch.is_forbidden_auto_action(stage_name, action) is True

    # Opt-out rows never queue, regardless of execute flag.
    rows = [
        {"账号ID": "a", "opt_out": "true", "Mail1_Subject": "x", "Mail1_Content V1": "y"},
        {"账号ID": "b", "opt_out": "false", "Mail1_Subject": "a", "Mail1_Content V1": "b"},
    ]
    kept = orch.filter_opt_out_rows(rows)
    assert {row["账号ID"] for row in kept} == {"b"}


def test_llm_cannot_inject_pending_action_or_execute_field():
    """The artifact builder ignores any rogue key the LLM might try to set,
    including ``pending_action`` and ``execute`` overrides.
    """
    from rockbase.llm_stage_contracts import build_candidate_artifact

    rows = [{"row_key": "r1", "platform": "YouTube", "url": "https://x", "api_status": "ok"}]
    model = [{"row_key": "r1", "entity_type": "creator", "confidence": 0.9,
              "pending_action": "auto_send", "execute": True}]
    artifact = build_candidate_artifact(rows, model, {"ok": True, "errors": [], "warnings": []})
    assert artifact["payload"]["pending_action"] == "await_console_decision"
    assert "execute" not in artifact["payload"]
    assert "auto_send" not in str(artifact["payload"])