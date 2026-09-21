from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.rockbase_orchestrator import Stage, run_pipeline


def _touch_command(path: Path) -> list[str]:
    return [sys.executable, "-c", f"from pathlib import Path; Path({str(path)!r}).touch()"]


def test_plan_mode_redacts_secret_values(tmp_path, capsys):
    secret = "plan-secret"
    run_pipeline(
        [Stage("secret", [sys.executable, "-c", "pass", "--api-key", secret])],
        state_path=tmp_path / "run.json",
        plan_only=True,
    )
    output = capsys.readouterr().out
    assert secret not in output
    assert "REDACTED" in output


def test_plan_mode_reports_stages_without_running_commands(tmp_path, capsys):
    marker = tmp_path / "marker"
    state_path = tmp_path / "run.json"

    result = run_pipeline(
        [Stage("generate", _touch_command(marker), artifacts=(marker,))],
        state_path=state_path,
        plan_only=True,
    )

    assert result == 0
    assert not marker.exists()
    assert "generate" in capsys.readouterr().out
    assert not state_path.exists()


def test_completed_stage_is_resumed_only_when_artifact_exists(tmp_path):
    marker = tmp_path / "marker"
    state_path = tmp_path / "run.json"
    stages = [Stage("generate", _touch_command(marker), artifacts=(marker,))]

    assert run_pipeline(stages, state_path=state_path) == 0
    first_state = json.loads(state_path.read_text())
    assert first_state["stages"]["generate"]["status"] == "completed"

    marker.unlink()
    assert run_pipeline(stages, state_path=state_path) == 0
    assert marker.exists(), "missing artifacts must force a completed stage to rerun"


def test_state_redacts_secret_flag_values(tmp_path):
    state_path = tmp_path / "run.json"
    secret = "super-secret-token"
    stage = Stage("secret", [sys.executable, "-c", "pass", "--api-key", secret])

    assert run_pipeline([stage], state_path=state_path) == 0
    state = json.loads(state_path.read_text())
    assert secret not in json.dumps(state)
    assert "REDACTED" in json.dumps(state)


def test_run_pipeline_prints_json_summary(tmp_path, capsys):
    marker = tmp_path / "marker"
    state_path = tmp_path / "run.json"

    result = run_pipeline(
        [Stage("generate", _touch_command(marker), artifacts=(marker,))],
        state_path=state_path,
    )

    assert result == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["stages"]["generate"]["status"] == "completed"


def test_retries_rerun_failing_stage_until_success(tmp_path):
    counter = tmp_path / "counter"
    state_path = tmp_path / "run.json"
    flaky = [
        sys.executable, "-c",
        "import sys; p = sys.argv[1]; n = int(open(p).read()) if __import__('os').path.exists(p) else 0;"
        "open(p, 'w').write(str(n + 1)); sys.exit(3 if n < 1 else 0)",
        str(counter),
    ]

    result = run_pipeline(
        [Stage("flaky", flaky)],
        state_path=state_path,
        retries=1,
    )

    assert result == 0
    assert counter.read_text() == "2"


def test_retries_exhausted_persists_failure(tmp_path):
    state_path = tmp_path / "run.json"
    failing = [sys.executable, "-c", "raise SystemExit(5)"]

    result = run_pipeline([Stage("broken", failing)], state_path=state_path, retries=2)

    assert result == 5
    state = json.loads(state_path.read_text())
    assert state["stages"]["broken"]["status"] == "failed"
    assert state["stages"]["broken"]["attempts"] == 3


def test_failed_stage_is_persisted_and_stops_following_stages(tmp_path):
    marker = tmp_path / "should-not-run"
    state_path = tmp_path / "run.json"
    failing = [sys.executable, "-c", "raise SystemExit(7)"]

    result = run_pipeline(
        [
            Stage("broken", failing),
            Stage("after", _touch_command(marker), artifacts=(marker,)),
        ],
        state_path=state_path,
    )

    assert result == 7
    state = json.loads(state_path.read_text())
    assert state["stages"]["broken"]["status"] == "failed"
    assert state["stages"]["broken"]["returncode"] == 7
    assert state["stages"]["after"]["status"] == "pending"
    assert not marker.exists()
