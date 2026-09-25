"""Small, resumable runner for Rockbase server pipeline stages."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Stage:
    name: str
    command: Sequence[str]
    artifacts: tuple[Path, ...] = ()
    timeout_seconds: int = 1800
    decision_stage: str | None = None
    artifact_path: Path | None = None
    forbidden_auto: bool = False


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
            resolved.append(str(matches[-1]) if matches else item)
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
    print(json.dumps({"version": state.get("version", 1), "status": state.get("status"),
                      "stages": state.get("stages", {})}, ensure_ascii=False, sort_keys=True))


def _approval_valid(path: Path, gate: str) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(record["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return record.get("gate") == gate and datetime.now(timezone.utc) < expires
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _stage_gate(name: str) -> str | None:
    if name == "mailkit_send":
        return "send"
    if name.startswith("master_sync"):
        return "sync"
    return None


# Permanent auto-mode gates. A run-level ``auto`` authorization can never
# override these: real send, production master writes, and queue-building
# actions on send/sync stages stay Console-gated forever.
_FORBIDDEN_AUTO_STAGES = frozenset({"mailkit_send", "master_sync_sent", "master_sync_replies"})
_FORBIDDEN_AUTO_ACTIONS = frozenset({"execute", "queue", "send", "sync", "write_master"})


def is_forbidden_auto_action(stage_name: str, action: str) -> bool:
    """True when ``action`` on ``stage_name`` can never be auto-advanced."""
    if stage_name in _FORBIDDEN_AUTO_STAGES:
        return True
    return action in _FORBIDDEN_AUTO_ACTIONS


def should_auto_advance_artifact(artifact: Mapping[str, Any] | None) -> dict[str, Any]:
    """Decide whether an auto-mode run may advance past an artifact.

    Deterministic: invalid validation, explicit ``manual_review``, or a
    missing pending action all block the advance. The model can never set
    ``pending_action`` — it is derived by the artifact builders.
    """
    if not isinstance(artifact, Mapping):
        return {"advance": False, "reason": "missing-artifact"}
    pending = artifact.get("pending_action") or (
        artifact.get("payload", {}).get("pending_action")
        if isinstance(artifact.get("payload"), Mapping) else None
    )
    if pending == "manual_review":
        return {"advance": False, "reason": "manual_review"}
    validation = artifact.get("validation") if isinstance(artifact.get("validation"), Mapping) else {}
    if not validation.get("ok", False):
        return {"advance": False, "reason": "invalid-artifact"}
    if list(validation.get("errors") or []):
        return {"advance": False, "reason": "invalid-artifact"}
    if pending != "await_console_decision":
        return {"advance": False, "reason": f"unknown-pending:{pending}"}
    if pending != "await_console_decision":
        return {"advance": False, "reason": f"unknown-pending:{pending}"}
    return {"advance": True, "reason": "await_console_decision"}


def filter_opt_out_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Drop rows whose opt_out column is truthy from any outbound queue.

    Opt-out is permanent: no run mode, actor, or model output can queue a
    row that opted out.
    """
    kept: list[Mapping[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        raw = row.get("opt_out")
        flag = str(raw or "").strip().lower()
        if flag in {"true", "1", "yes", "y", "是"}:
            continue
        kept.append(row)
    return kept


def _load_decision(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _decision_for_stage(stage: Stage, *, decision_file: Path | None = None,
                         run_id: str | None = None) -> dict | None:
    """Resolve a Console decision for a given stage.

    Decisions are read-only here; the producer is the Console (Task 4).
    CLI/automation callers may pass ``decision_file`` pointing at a JSON file
    the Console exported (the human partner or a follow-up workflow copies
    the redacted approval record out of band).
    """
    if decision_file is None:
        return None
    payload = _load_decision(decision_file)
    if not payload:
        return None
    return payload


def _persist_decision_state(state: dict, decision_status: str,
                             artifact_id: str | None = None) -> None:
    state["decision_status"] = decision_status
    state["current_artifact_id"] = artifact_id


def run_pipeline(
    stages: Sequence[Stage],
    *,
    state_path: Path,
    plan_only: bool = False,
    retries: int = 0,
    pause_file: Path | None = None,
    approval_files: Mapping[str, Path] | None = None,
    console_run: bool = False,
    run_id: str | None = None,
    mode: str | None = None,
    artifact_store: Any | None = None,
    decision_store: Any | None = None,
    decision_files: Mapping[str, Path] | None = None,
) -> int:
    """Run stages in order, resuming only valid completed stages.

    ``mode`` pins the run to ``review`` (default; decision stages pause for a
    Console decision) or ``auto`` (non-forbidden decision stages advance with
    an authorization record; send/sync gates still apply). The mode is
    recorded at first start and can never change mid-run.
    """
    if retries < 0:
        raise ValueError("retries must be non-negative")
    if plan_only:
        for stage in stages:
            print(f"[plan] {stage.name}: {' '.join(_safe_command(stage.command))}")
        return 0

    if mode is not None and mode not in {"review", "auto"}:
        raise ValueError(f"invalid run mode: {mode!r}")

    state = _load_state(state_path)
    stage_state = state.setdefault("stages", {})
    if run_id:
        state["run_id"] = run_id
    recorded_mode = state.get("mode")
    if mode is not None:
        if recorded_mode is not None and recorded_mode != mode:
            raise ValueError(
                f"run mode is fixed at start (recorded={recorded_mode!r}); "
                f"refusing change to {mode!r}"
            )
        state["mode"] = mode
    elif recorded_mode is None:
        state["mode"] = "review"
    effective_mode = state.get("mode", "review")
    state.setdefault("policy_version", 1)
    state["runner_pid"] = os.getpid()
    try:
        state["runner_pgid"] = os.getpgid(os.getpid())
    except OSError:
        state["runner_pgid"] = os.getpid()
    state["status"] = "running"
    _save_state(state_path, state)

    if run_id is None:
        run_id = state_path.stem

    def _create_artifact(stage: Stage, record: dict) -> Any | None:
        """Snapshot the stage output into a versioned envelope for decisions."""
        if artifact_store is None or not stage.decision_stage:
            return None
        try:
            payload_text = Path(record["artifacts"][0]).read_text(encoding="utf-8")
        except (KeyError, IndexError, OSError, UnicodeDecodeError):
            payload_text = ""
        from rockbase.decision_models import ArtifactEnvelope

        envelope = ArtifactEnvelope.new(
            run_id=run_id, stage_id=stage.decision_stage,
            payload={"stage": stage.name, "artifact": payload_text},
            validation={"ok": True, "errors": [], "warnings": []},
        )
        stored = artifact_store.put(envelope)
        record["artifact_id"] = stored.artifact_id
        record["artifact_version"] = stored.version
        return stored

    for stage in stages:
        stage_state.setdefault(stage.name, {"status": "pending"})
    for stage in stages:
        record = stage_state.setdefault(stage.name, {"status": "pending"})
        if record.get("status") == "completed" and _artifacts_exist(stage):
            print(f"[skip] {stage.name} (completed; artifacts present)")
            continue
        if record.get("status") == "completed":
            record["status"] = "pending"

        if pause_file is not None and pause_file.exists():
            state.update({"status": "paused", "paused_at": _now()})
            _save_state(state_path, state)
            _print_summary(state)
            return 0

        decision_file = (decision_files or {}).get(stage.name)

        if stage.decision_stage and record.get("status") == "awaiting_approval":
            # Resume path: a paused decision stage only advances on an
            # approve / approve_run decision recorded by the Console.
            decision = _decision_for_stage(stage, decision_file=decision_file,
                                           run_id=run_id)
            action = (decision or {}).get("action")
            if action not in {"approve", "approve_run"}:
                state.update({"status": "paused",
                              "paused_at": _now(),
                              "decision_status": "awaiting_approval"})
                _save_state(state_path, state)
                _print_summary(state)
                return 2
            _persist_decision_state(state, "approved",
                                    record.get("artifact_id"))
            record.update({"status": "completed",
                           "finished_at": _now(), "returncode": 0})
            state["status"] = "running"
            _save_state(state_path, state)
            print(f"[skip] {stage.name} (decision approved)")
            continue
        if stage.decision_stage and effective_mode == "review" \
                and record.get("status") != "completed":
            # Run the stage once to produce its artifact, then hold the
            # enveloped output for a Console decision before any dependent
            # stage (send/sync/follow-up) may run.
            record.update({"status": "running", "started_at": _now(),
                           "command": _safe_command(stage.command), "attempts": 1})
            _save_state(state_path, state)
            print(f"[run] {stage.name} (decision boundary)")
            try:
                completed = subprocess.run(
                    _resolve_command(stage.command), check=False, capture_output=True,
                    text=True, timeout=stage.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                record.update({"status": "failed", "finished_at": _now(), "returncode": None,
                               "error": f"timeout after {stage.timeout_seconds}s",
                               "stdout": _safe_output(exc.stdout or "", stage.command),
                               "stderr": _safe_output(exc.stderr or "", stage.command)})
                state["status"] = "failed"
                _save_state(state_path, state)
                _print_summary(state)
                return 124
            record.update({"finished_at": _now(),
                           "returncode": completed.returncode,
                           "stdout": _safe_output(completed.stdout, stage.command),
                           "stderr": _safe_output(completed.stderr, stage.command),
                           "artifacts": [str(path) for path in stage.artifacts]})
            if completed.returncode != 0 or not _artifacts_exist(stage):
                record.update({"status": "failed",
                               "error": "stage failed before decision boundary"})
                state["status"] = "failed"
                _save_state(state_path, state)
                _print_summary(state)
                return completed.returncode or 1
            _create_artifact(stage, record)
            _persist_decision_state(state, "awaiting_approval",
                                    record.get("artifact_id"))
            record.update({"status": "awaiting_approval"})
            state["status"] = "awaiting_approval"
            _save_state(state_path, state)
            _print_summary(state)
            return 2
        if stage.decision_stage and effective_mode == "auto":
            if stage.forbidden_auto:
                record.update({"status": "failed", "finished_at": _now(),
                               "returncode": None,
                               "error": "forbidden in auto mode"})
                state["status"] = "failed"
                _save_state(state_path, state)
                _print_summary(state)
                return 1
            # Pre-authorized for this run: run the stage and record the
            # authorization alongside the produced artifact.
            record.update({"status": "running", "started_at": _now(),
                           "command": _safe_command(stage.command), "attempts": 1})
            _save_state(state_path, state)
            print(f"[run] {stage.name} (auto pre-authorized)")

        gate = _stage_gate(stage.name) if console_run else None
        if gate is not None:
            approval_path = (approval_files or {}).get(gate)
            if approval_path is None or not _approval_valid(approval_path, gate):
                record.update({"status": "failed", "finished_at": _now(),
                               "returncode": None, "error": f"gate-blocked: {gate}"})
                state["status"] = "failed"
                _save_state(state_path, state)
                _print_summary(state)
                return 1

        record.update({"status": "running", "started_at": _now(),
                       "command": _safe_command(stage.command), "attempts": 0})
        _save_state(state_path, state)
        final_code = 1
        for attempt in range(1, retries + 2):
            record["attempts"] = attempt
            _save_state(state_path, state)
            print(f"[run] {stage.name} (attempt {attempt}/{retries + 1})")
            try:
                completed = subprocess.run(
                    _resolve_command(stage.command), check=False, capture_output=True,
                    text=True, timeout=stage.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                record.update({"status": "failed", "finished_at": _now(), "returncode": None,
                               "error": f"timeout after {stage.timeout_seconds}s",
                               "stdout": _safe_output(exc.stdout or "", stage.command),
                               "stderr": _safe_output(exc.stderr or "", stage.command)})
                state["status"] = "failed"
                _save_state(state_path, state)
                _print_summary(state)
                return 124

            final_code = completed.returncode
            record.update({"status": "completed" if final_code == 0 else "failed",
                           "finished_at": _now(), "returncode": final_code,
                           "stdout": _safe_output(completed.stdout, stage.command),
                           "stderr": _safe_output(completed.stderr, stage.command),
                           "artifacts": [str(path) for path in stage.artifacts]})
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
            state["status"] = "failed"
            _save_state(state_path, state)
            _print_summary(state)
            return final_code

        if stage.decision_stage and effective_mode == "auto":
            _create_artifact(stage, record)
            _persist_decision_state(state, "approved",
                                    record.get("artifact_id"))
            _save_state(state_path, state)

    state["status"] = "completed"
    state.pop("paused_at", None)
    state.pop("runner_pid", None)
    state.pop("runner_pgid", None)
    _save_state(state_path, state)
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
