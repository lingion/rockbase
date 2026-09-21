"""Small, resumable runner for Rockbase server pipeline stages."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Stage:
    name: str
    command: Sequence[str]
    artifacts: tuple[Path, ...] = ()
    timeout_seconds: int = 1800


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "stages": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _artifacts_exist(stage: Stage) -> bool:
    return all(path.exists() for path in stage.artifacts)


def _safe_command(command: Sequence[str]) -> list[str]:
    """Keep credential-bearing CLI values out of persisted state and logs."""
    secret_flags = {"--api-key", "--llm-api-key", "--access-token", "--token"}
    safe: list[str] = []
    redact_next = False
    for item in command:
        if redact_next:
            safe.append("REDACTED")
            redact_next = False
        elif item in secret_flags:
            safe.append(item)
            redact_next = True
        else:
            safe.append(item)
    return safe


def run_pipeline(
    stages: Sequence[Stage],
    *,
    state_path: Path,
    plan_only: bool = False,
) -> int:
    """Run stages in order, resuming only valid completed stages."""
    if plan_only:
        for stage in stages:
            print(f"[plan] {stage.name}: {' '.join(stage.command)}")
        return 0

    state = _load_state(state_path)
    stage_state = state.setdefault("stages", {})
    # 运行前登记全部阶段，恢复工具能区分「未开始」与「配置缺失」
    for stage in stages:
        stage_state.setdefault(stage.name, {"status": "pending"})
    for stage in stages:
        record = stage_state.setdefault(stage.name, {"status": "pending"})
        if record.get("status") == "completed" and _artifacts_exist(stage):
            print(f"[skip] {stage.name} (completed; artifacts present)")
            continue
        if record.get("status") == "completed":
            record["status"] = "pending"

        record.update({"status": "running", "started_at": _now(), "command": _safe_command(stage.command)})
        _save_state(state_path, state)
        print(f"[run] {stage.name}")
        try:
            completed = subprocess.run(
                list(stage.command),
                check=False,
                capture_output=True,
                text=True,
                timeout=stage.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            record.update({
                "status": "failed",
                "finished_at": _now(),
                "returncode": None,
                "error": f"timeout after {stage.timeout_seconds}s",
                "stdout": (exc.stdout or "")[-4000:],
                "stderr": (exc.stderr or "")[-4000:],
            })
            _save_state(state_path, state)
            return 124

        record.update({
            "status": "completed" if completed.returncode == 0 else "failed",
            "finished_at": _now(),
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "artifacts": [str(path) for path in stage.artifacts],
        })
        _save_state(state_path, state)
        if completed.returncode != 0:
            return completed.returncode
        if not _artifacts_exist(stage):
            record.update({"status": "failed", "error": "declared artifact missing after command"})
            _save_state(state_path, state)
            return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--plan", action="store_true", help="print stages without executing them")
    args = parser.parse_args(argv)
    parser.error("no pipeline stages are configured; import run_pipeline from a project runner")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
