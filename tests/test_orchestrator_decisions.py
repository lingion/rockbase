from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.rockbase_orchestrator import Stage, run_pipeline


def _touch_command(path: Path) -> list[str]:
    return [sys.executable, "-c", f"from pathlib import Path; Path({str(path)!r}).touch()"]


def test_review_mode_pauses_after_artifact(tmp_path):
    marker = tmp_path / "draft.md"
    state_path = tmp_path / "state.json"
    stage = Stage("draft", _touch_command(marker), artifacts=(marker,), decision_stage="s3.draft")

    rc = run_pipeline([stage], state_path=state_path, mode="review")

    assert rc != 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "review"
    assert state["decision_status"] == "awaiting_approval"
    assert state["stages"]["draft"]["status"] == "awaiting_approval"


def test_auto_mode_advances_non_forbidden_but_not_send(tmp_path):
    marker = tmp_path / "draft.md"
    send_marker = tmp_path / "sent.txt"
    state_path = tmp_path / "state.json"
    stages = [
        Stage("draft", _touch_command(marker), artifacts=(marker,), decision_stage="s3.draft"),
        Stage("mailkit_send", _touch_command(send_marker), artifacts=(send_marker,)),
    ]

    rc = run_pipeline(stages, state_path=state_path, mode="auto", console_run=True)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "auto"
    assert state["stages"]["draft"]["status"] == "completed"
    assert state["stages"]["mailkit_send"]["status"] == "failed"
    assert "gate-blocked" in state["stages"]["mailkit_send"]["error"]
    assert rc != 0


def test_mode_change_mid_run_is_rejected(tmp_path):
    marker = tmp_path / "draft.md"
    state_path = tmp_path / "state.json"
    stage = Stage("draft", _touch_command(marker), artifacts=(marker,), decision_stage="s3.draft")

    assert run_pipeline([stage], state_path=state_path, mode="review") != 0
    with_tampered_mode = json.loads(state_path.read_text(encoding="utf-8"))
    with_tampered_mode["mode"] = "auto"
    state_path.write_text(json.dumps(with_tampered_mode), encoding="utf-8")

    try:
        run_pipeline([stage], state_path=state_path, mode="review")
    except ValueError as exc:
        assert "mode" in str(exc)
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "auto", "review resume must refuse a tampered auto mode"


def test_review_mode_resumes_once_after_current_decision(tmp_path, monkeypatch):
    from rockbase.artifact_store import ArtifactStore
    from rockbase.decision_models import ArtifactEnvelope, DecisionRequest, validate_decision

    marker = tmp_path / "draft.md"
    state_path = tmp_path / "state.json"
    store = ArtifactStore(tmp_path / "artifacts")
    stage = Stage("draft", _touch_command(marker), artifacts=(marker,), decision_stage="s3.draft")

    assert run_pipeline([stage], state_path=state_path, mode="review",
                        artifact_store=store) != 0

    # Console would create this decision; simulate the recorded approval.
    artifact = store.list_for_run("state")[0] if store.list_for_run("state") else None
    assert artifact is not None
    run_id = artifact.run_id
    decision = DecisionRequest(artifact.artifact_id, artifact.version, "approve", "operator")
    validate_decision(decision, artifact)
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps(decision.to_dict()), encoding="utf-8")

    monkeypatch.setattr(
        "scripts.rockbase_orchestrator._decision_for_stage",
        lambda stage, decision_file=None, run_id=None: (
            json.loads(decision_path.read_text(encoding="utf-8"))
            if decision_path.exists() else None
        ),
    )
    assert run_pipeline([stage], state_path=state_path, mode="review",
                        artifact_store=store) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["stages"]["draft"]["status"] == "completed"
    assert state["decision_status"] == "approved"
