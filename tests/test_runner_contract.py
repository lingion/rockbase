"""Runner contract: pipeline runner accepts --run-id and env-supplied inputs.

The Rockbase console hands each runner a `--run-id` and a `--state` path it
allocated; the runner must echo the run-id into the state file so the
workbench can correlate runs even after restart. The runner must also
accept `--csv`, `--config`, and `--fetch-out` with environment-variable
fallbacks so the Docker pipeline service can drive it without a console.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.rockbase_orchestrator import Stage, run_pipeline
from scripts.run_full_pipeline import main


def _write_minimal_csv(path: Path) -> None:
    path.write_text(
        "creator_id,联系方式,频道/作者名称,Mail1_Subject,Mail1_Content V1\n"
        "1,u@example.com,name,subject,body\n",
        encoding="utf-8",
    )


def _write_minimal_config(path: Path) -> None:
    path.write_text("[mail]\nsmtp_host = localhost\n", encoding="utf-8")


def test_run_pipeline_records_run_id_into_state(tmp_path: Path) -> None:
    """run_pipeline writes the console-allocated run-id into state['run_id']."""
    state = tmp_path / "state.json"
    stages = [Stage("noop", (sys.executable, "-c", "pass"))]

    rc = run_pipeline(stages, state_path=state, run_id="run-deadbeef")

    assert rc == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-deadbeef"
    assert payload["status"] == "completed"


def test_run_pipeline_omits_run_id_when_not_supplied(tmp_path: Path) -> None:
    """Legacy callers that pass no run-id keep the old state shape."""
    state = tmp_path / "state.json"
    stages = [Stage("noop", (sys.executable, "-c", "pass"))]

    rc = run_pipeline(stages, state_path=state)

    assert rc == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "run_id" not in payload
    assert payload["status"] == "completed"


def test_runner_cli_plan_accepts_run_id_flag(tmp_path: Path, monkeypatch) -> None:
    """`--run-id` is a recognised flag on the CLI (plan mode exits 0)."""
    csv = tmp_path / "master.csv"
    config = tmp_path / "config.toml"
    _write_minimal_csv(csv)
    _write_minimal_config(config)

    argv = [
        "--csv", str(csv),
        "--config", str(config),
        "--state", str(tmp_path / "state.json"),
        "--fetch-out", str(tmp_path / "replies"),
        "--date", "2026-09-22",
        "--run-id", "run-cli-test",
        "--plan",
    ]
    assert main(argv) == 0


def test_runner_cli_resolves_missing_inputs_from_env(tmp_path: Path, monkeypatch) -> None:
    """--csv / --config / --fetch-out fall back to their env vars."""
    csv = tmp_path / "master.csv"
    config = tmp_path / "config.toml"
    _write_minimal_csv(csv)
    _write_minimal_config(config)

    monkeypatch.setenv("ROCKBASE_MASTER_CSV", str(csv))
    monkeypatch.setenv("ROCKBASE_MAILKIT_CONFIG", str(config))
    monkeypatch.setenv("ROCKBASE_PIPELINE_FETCH_OUT", str(tmp_path / "replies"))
    monkeypatch.setenv("ROCKBASE_RUN_ID", "run-env-test")

    argv = ["--state", str(tmp_path / "state.json"), "--date", "2026-09-22", "--plan"]
    assert main(argv) == 0


def test_runner_cli_errors_clearly_when_no_input_anywhere(tmp_path: Path, monkeypatch) -> None:
    """Missing csv/config with no env fallback exits with a clear error."""
    monkeypatch.delenv("ROCKBASE_MASTER_CSV", raising=False)
    monkeypatch.delenv("ROCKBASE_MAILKIT_CONFIG", raising=False)

    argv = [
        "--state", str(tmp_path / "state.json"),
        "--fetch-out", str(tmp_path / "replies"),
        "--plan",
    ]
    with pytest.raises(SystemExit, match="ROCKBASE_MASTER_CSV"):
        main(argv)
