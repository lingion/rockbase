from __future__ import annotations

import json
from pathlib import Path

from scripts.rockbase_health import inspect_state


def test_health_reports_successful_run(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "version": 1,
        "stages": {
            "mailkit_send": {"status": "completed", "finished_at": "2026-09-21T06:00:00+00:00", "attempts": 1},
            "master_sync_replies": {"status": "completed", "finished_at": "2026-09-21T06:01:00+00:00", "attempts": 1},
        },
    }))

    report = inspect_state(state)

    assert report["status"] == "ok"
    assert report["failed_stages"] == []
    assert report["last_success_at"] == "2026-09-21T06:01:00+00:00"


def test_health_reports_failed_stage_and_nonzero_exit(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "version": 1,
        "stages": {
            "fetch_replies": {
                "status": "failed", "returncode": 7, "attempts": 2,
                "stderr": "receiver unavailable",
            },
            "master_sync_replies": {"status": "pending"},
        },
    }))

    report = inspect_state(state)

    assert report["status"] == "critical"
    assert report["failed_stages"] == ["fetch_replies"]
    assert report["pending_stages"] == ["master_sync_replies"]
    assert report["exit_code"] == 2


def test_health_missing_state_is_unknown(tmp_path):
    report = inspect_state(tmp_path / "missing.json")

    assert report["status"] == "unknown"
    assert report["exit_code"] == 2
