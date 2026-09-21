"""Inspect a Phase 2 state file and emit a machine-readable health report."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def inspect_state(state_path: Path) -> dict[str, Any]:
    base = {
        "state_path": str(state_path),
        "failed_stages": [],
        "pending_stages": [],
        "running_stages": [],
        "last_success_at": None,
        "exit_code": 0,
    }
    if not state_path.exists():
        return {**base, "status": "unknown", "reason": "state file missing", "exit_code": 2}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**base, "status": "critical", "reason": f"invalid state: {exc}", "exit_code": 2}

    stages = state.get("stages")
    if not isinstance(stages, dict):
        return {**base, "status": "critical", "reason": "state.stages is not an object", "exit_code": 2}
    successes: list[tuple[datetime, str]] = []
    for name, record in stages.items():
        status = record.get("status") if isinstance(record, dict) else None
        if status == "failed":
            base["failed_stages"].append(name)
        elif status == "pending":
            base["pending_stages"].append(name)
        elif status in {"running", "retrying"}:
            base["running_stages"].append(name)
        if status == "completed":
            parsed = _parse_time(record.get("finished_at"))
            if parsed:
                successes.append((parsed, record["finished_at"]))

    if successes:
        base["last_success_at"] = max(successes)[1]
    if base["failed_stages"]:
        base.update({"status": "critical", "exit_code": 2})
    elif base["running_stages"]:
        base.update({"status": "degraded", "reason": "stage still running", "exit_code": 1})
    elif base["pending_stages"]:
        base.update({"status": "degraded", "reason": "pipeline incomplete", "exit_code": 1})
    else:
        base["status"] = "ok"
    return base


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args(argv)
    report = inspect_state(args.state)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
