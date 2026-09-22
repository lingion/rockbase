from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from scripts.rockbase_orchestrator import Stage, run_pipeline
from scripts.run_full_pipeline import build_full_pipeline_stages


def _touch(stage_name: str, target: Path) -> Stage:
    return Stage(stage_name, [sys.executable, "-c", f"from pathlib import Path; Path({str(target)!r}).touch()"],
                 artifacts=(target,))


def test_pause_marker_halts_pipeline_between_stages(tmp_path):
    state_path = tmp_path / "state.json"
    pause_file = tmp_path / "pause"
    second = tmp_path / "second"
    first = tmp_path / "first"
    stages = [
        _touch("first", first),
        _touch("second", second),
    ]

    first.touch()
    state_path.write_text(json.dumps({
        "version": 1,
        "stages": {"first": {"status": "completed"}, "second": {"status": "pending"}},
    }))
    pause_file.touch()
    result = run_pipeline(stages, state_path=state_path, pause_file=pause_file)

    assert result == 0
    assert (tmp_path / "first").exists()
    assert not second.exists()
    state = json.loads(state_path.read_text())
    assert state["status"] == "paused"
    assert state["stages"]["first"]["status"] == "completed"
    assert state["stages"]["second"]["status"] == "pending"
    assert "paused_at" in state


def test_resume_after_clear_marker_skips_completed_and_continues(tmp_path):
    state_path = tmp_path / "state.json"
    pause_file = tmp_path / "pause"
    second = tmp_path / "second"
    first_marker = tmp_path / "first"
    stages = [
        _touch("first", first_marker),
        _touch("second", second),
    ]

    pause_file.touch()
    assert run_pipeline(stages, state_path=state_path, pause_file=pause_file) == 0
    pause_file.unlink()
    assert run_pipeline(stages, state_path=state_path, pause_file=pause_file) == 0

    assert second.exists()
    state = json.loads(state_path.read_text())
    assert state["status"] == "completed"
    assert state["stages"]["first"]["status"] == "completed"
    assert state["stages"]["second"]["status"] == "completed"


def test_console_send_stage_blocks_without_approval(tmp_path):
    state_path = tmp_path / "state.json"
    approval_file = tmp_path / "send.json"
    stages = [
        Stage("mailkit_send", [sys.executable, "-c", "pass"]),
    ]

    result = run_pipeline(stages, state_path=state_path, console_run=True,
                          approval_files={"send": approval_file})

    assert result != 0
    state = json.loads(state_path.read_text())
    assert state["stages"]["mailkit_send"]["status"] == "failed"
    assert state["stages"]["mailkit_send"]["error"] == "gate-blocked: send"


def test_console_send_stage_runs_with_current_approval(tmp_path):
    state_path = tmp_path / "state.json"
    approval_file = tmp_path / "send.json"
    approval_file.write_text(json.dumps({
        "run_id": "run-1", "gate": "send", "actor": "alice",
        "batch_label": "batch-2026-09-21", "expires_at": "2999-01-01T00:00:00+00:00",
    }))
    marker = tmp_path / "ran"
    stages = [Stage("mailkit_send", [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                    artifacts=(marker,))]

    assert run_pipeline(stages, state_path=state_path, console_run=True,
                        approval_files={"send": approval_file}) == 0
    assert marker.exists()


def test_bare_cli_path_ignores_console_approval(tmp_path):
    state_path = tmp_path / "state.json"
    marker = tmp_path / "ran"
    stages = [Stage("mailkit_send",
                    [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                    artifacts=(marker,))]

    assert run_pipeline(stages, state_path=state_path) == 0
    assert marker.exists()


def test_run_pipeline_persists_pid_metadata_and_clears_on_success(tmp_path):
    state_path = tmp_path / "state.json"
    marker = tmp_path / "ran"
    stages = [Stage("only", [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                    artifacts=(marker,))]

    assert run_pipeline(stages, state_path=state_path) == 0
    state = json.loads(state_path.read_text())
    assert "pid" not in state
    assert "pgid" not in state
    assert "pid" not in state["stages"]["only"]


def test_build_full_pipeline_stages_accepts_pause_and_approval(tmp_path):
    stages = build_full_pipeline_stages(
        csv_path=tmp_path / "master.csv",
        config=tmp_path / "config.toml",
        state_path=tmp_path / "state.json",
        fetch_out=tmp_path / "replies",
        date="2026-09-21",
        execute_send=True,
        execute_sync=True,
        console_run=True,
        pause_file=tmp_path / "pause",
        approval_files={"send": tmp_path / "send.json", "sync": tmp_path / "sync.json"},
    )

    assert {stage.name for stage in stages}.issuperset({"mailkit_send", "master_sync_sent"})