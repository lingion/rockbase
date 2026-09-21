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


def _resolve_command(command: Sequence[str]) -> list[str]:
    resolved: list[str] = []
    for item in command:
        path = Path(item)
        if any(char in item for char in "*?["):
            matches = sorted(path.parent.glob(path.name))
            if not matches:
                resolved.append(item)
            else:
                resolved.append(str(matches[-1]))
        else:
            resolved.append(item)
    return resolved


def _artifact_exists(path: Path) -> bool:
    if any(char in str(path) for char in "*?["):
        return bool(path.parent.glob(path.name))
    return path.exists()


def _artifacts_exist(stage: Stage) -> bool:
    return all(_artifact_exists(path) for path in stage.artifacts)


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


def _safe_output(text: str, command: Sequence[str]) -> str:
    """Remove values paired with credential flags from captured output."""
    redacted = text or ""
    secret_flags = {"--api-key", "--llm-api-key", "--access-token", "--token"}
    for index, item in enumerate(command[:-1]):
        if item in secret_flags:
            redacted = redacted.replace(command[index + 1], "REDACTED")
    return redacted[-4000:]


def _print_summary(state: dict) -> None:
    print(json.dumps({"version": state.get("version", 1), "stages": state.get("stages", {})},
                     ensure_ascii=False, sort_keys=True))


def run_pipeline(
    stages: Sequence[Stage],
    *,
    state_path: Path,
    plan_only: bool = False,
    retries: int = 0,
) -> int:
    """Run stages in order, resuming only valid completed stages."""
    if retries < 0:
        raise ValueError("retries must be non-negative")
    if plan_only:
        for stage in stages:
            print(f"[plan] {stage.name}: {' '.join(_safe_command(stage.command))}")
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

        record.update({"status": "running", "started_at": _now(),
                       "command": _safe_command(stage.command),
                       "attempts": 0})
        _save_state(state_path, state)
        final_code = 1
        for attempt in range(1, retries + 2):
            record["attempts"] = attempt
            print(f"[run] {stage.name} (attempt {attempt}/{retries + 1})")
            try:
                completed = subprocess.run(
                    _resolve_command(stage.command),
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
                    "stdout": _safe_output(exc.stdout or "", stage.command),
                    "stderr": _safe_output(exc.stderr or "", stage.command),
                })
                _save_state(state_path, state)
                _print_summary(state)
                return 124

            final_code = completed.returncode
            record.update({
                "status": "completed" if final_code == 0 else "failed",
                "finished_at": _now(),
                "returncode": final_code,
                "stdout": _safe_output(completed.stdout, stage.command),
                "stderr": _safe_output(completed.stderr, stage.command),
                "artifacts": [str(path) for path in stage.artifacts],
            })
            _save_state(state_path, state)
            if final_code == 0:
                if not _artifacts_exist(stage):
                    record.update({"status": "failed", "error": "declared artifact missing after command"})
                    final_code = 1
                else:
                    break
            if attempt <= retries:
                record["status"] = "retrying"
                _save_state(state_path, state)
        if final_code != 0:
            _print_summary(state)
            return final_code
    _print_summary(state)
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
