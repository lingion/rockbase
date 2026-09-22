"""Validated state discovery and console approval persistence."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_BATCH_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_GATES = frozenset({"send", "sync"})
_DEFAULT_MAX_STATE_BYTES = 1024 * 1024


def _valid_id(value: str) -> bool:
    return bool(_RUN_ID.fullmatch(value))


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RunRepository:
    def __init__(self, runs_dir: Path, *, max_state_bytes: int = _DEFAULT_MAX_STATE_BYTES) -> None:
        self.runs_dir = Path(runs_dir)
        self.max_state_bytes = max_state_bytes
        self._root = self.runs_dir.resolve()

    def _path_for(self, run_id: str) -> Path | None:
        if not _valid_id(run_id):
            return None
        path = self.runs_dir / f"{run_id}.json"
        try:
            if path.is_symlink() or path.resolve().parent != self._root:
                return None
            if not path.is_file() or path.stat().st_size > self.max_state_bytes:
                return None
        except OSError:
            return None
        return path

    @staticmethod
    def _valid_state(payload: Any, fallback_id: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict) or not isinstance(payload.get("stages"), dict):
            return None
        result = dict(payload)
        run_id = result.get("run_id", fallback_id)
        if not isinstance(run_id, str) or not _valid_id(run_id):
            return None
        result["run_id"] = run_id
        return result

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self._path_for(run_id)
        if path is None:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return self._valid_state(payload, run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        try:
            candidates = sorted(self.runs_dir.glob("*.json"))
        except OSError:
            return []
        for path in candidates:
            run_id = path.stem
            item = self.get_run(run_id)
            if item is not None:
                results.append(item)
        return results


class ApprovalStore:
    def __init__(self, directory: Path, *, ttl: timedelta = timedelta(hours=24)) -> None:
        self.directory = Path(directory)
        self.ttl = ttl

    def _path(self, run_id: str, gate: str) -> Path:
        if not _valid_id(run_id):
            raise ValueError("invalid run id")
        if gate not in _GATES:
            raise ValueError("unsupported approval gate")
        return self.directory / f"{run_id}.{gate}.json"

    def approve(
        self,
        run_id: str,
        gate: str,
        actor: str,
        batch_label: str,
        now: datetime,
    ) -> dict[str, Any]:
        path = self._path(run_id, gate)
        if not isinstance(batch_label, str) or not _BATCH_LABEL.fullmatch(batch_label):
            raise ValueError("invalid batch label")
        if not isinstance(actor, str) or not actor or len(actor) > 128:
            raise ValueError("invalid actor")
        issued = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
        record = {
            "run_id": run_id,
            "gate": gate,
            "actor": actor,
            "batch_label": batch_label,
            "approved_at": issued.isoformat(),
            "expires_at": (issued + self.ttl).isoformat(),
        }
        _atomic_json(path, record)
        return record

    def validate(self, run_id: str, gate: str, now: datetime) -> bool:
        try:
            path = self._path(run_id, gate)
            record = json.loads(path.read_text(encoding="utf-8"))
            expires_at = _parse_datetime(record["expires_at"])
            current = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
            return (
                record.get("run_id") == run_id
                and record.get("gate") == gate
                and isinstance(record.get("batch_label"), str)
                and bool(_BATCH_LABEL.fullmatch(record["batch_label"]))
                and current < expires_at
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False


class RunManager:
    """Own managed runner processes and their console control files."""

    _ALLOWED_PARAMETERS = frozenset({"batch_label", "execute_send", "execute_sync", "retries"})

    def __init__(self, *, repo_root: Path, runs: RunRepository, approvals: ApprovalStore,
                 audit: Any, runner: list[str]) -> None:
        self.repo_root = Path(repo_root)
        self.runs = runs
        self.approvals = approvals
        self.audit = audit
        self.runner = tuple(runner)
        self._processes: dict[str, Any] = {}

    @staticmethod
    def _validate_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(parameters, dict) or set(parameters) - RunManager._ALLOWED_PARAMETERS:
            raise ValueError("unsupported run parameter")
        result = dict(parameters)
        label = result.get("batch_label", "batch")
        if not isinstance(label, str) or not _BATCH_LABEL.fullmatch(label):
            raise ValueError("invalid batch label")
        if "retries" in result and (isinstance(result["retries"], bool) or
                                      not isinstance(result["retries"], int) or result["retries"] < 0 or
                                      result["retries"] > 10):
            raise ValueError("invalid retries")
        for key in ("execute_send", "execute_sync"):
            if key in result and not isinstance(result[key], bool):
                raise ValueError(f"invalid {key}")
        return result

    def list_runs(self) -> list[dict[str, Any]]:
        """Expose validated run state to the HTTP layer."""
        return self.runs.list_runs()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Expose one validated run state to the HTTP layer."""
        return self.runs.get_run(run_id)

    def _state_path(self, run_id: str) -> Path:
        if not _valid_id(run_id):
            raise ValueError("invalid run id")
        return self.runs.runs_dir / f"{run_id}.json"

    def _active(self, run_id: str) -> bool:
        state = self.runs.get_run(run_id)
        if state is None or state.get("status") not in {"running", "paused", "retrying"}:
            return False
        process = self._processes.get(run_id)
        if process is not None and process.poll() is None:
            return True
        pid = state.get("runner_pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                pass
        return state.get("status") == "paused"

    def start(self, parameters: dict[str, Any], *, actor: str, request_id: str) -> dict[str, Any]:
        clean = self._validate_parameters(parameters)
        if any(self._active(item["run_id"]) for item in self.runs.list_runs()):
            raise RuntimeError("an active run already owns the state directory")
        run_id = f"run-{os.urandom(8).hex()}"
        state_path = self._state_path(run_id)
        initial = {"version": 1, "run_id": run_id, "status": "starting", "parameters": clean,
                   "stages": {"runner": {"status": "running"}},
                   "runner_pid": None, "runner_pgid": None}
        _atomic_json(state_path, initial)
        command = list(self.runner) + ["--run-id", run_id, "--state", str(state_path)]
        process = subprocess.Popen(command, cwd=self.repo_root,
                                    start_new_session=True,
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        self._processes[run_id] = process
        state = dict(initial)
        state.update({"status": "running", "runner_pid": process.pid, "runner_pgid": process.pid})
        _atomic_json(state_path, state)
        self.audit.append("start", request_id=request_id, actor=actor, run_id=run_id,
                          details={"result": "ok"})
        return state

    def pause(self, run_id: str, *, actor: str, request_id: str) -> dict[str, Any]:
        if not self._active(run_id):
            raise RuntimeError("run is not active")
        marker = self.runs.runs_dir / f"{run_id}.pause"
        marker.touch(exist_ok=True)
        self.audit.append("pause", request_id=request_id, actor=actor, run_id=run_id)
        return {"run_id": run_id, "status": "pause_requested"}

    def approve(self, run_id: str, gate: str, actor: str, batch_label: str, *, request_id: str) -> dict[str, Any]:
        record = self.approvals.approve(run_id, gate, actor, batch_label, datetime.now(timezone.utc))
        self.audit.append("approve", request_id=request_id, actor=actor, run_id=run_id,
                          details={"gate": gate, "batch_label": batch_label})
        return record

    def resume(self, run_id: str, parameters: dict[str, Any] | None, *, actor: str, request_id: str) -> dict[str, Any]:
        state = self.runs.get_run(run_id)
        if state is None:
            raise KeyError(run_id)
        old = state.get("parameters", {})
        new = self._validate_parameters(parameters if parameters is not None else old)
        for key, gate in (("execute_send", "send"), ("execute_sync", "sync")):
            if bool(old.get(key, False)) != bool(new.get(key, False)) and new.get(key, False):
                if not self.approvals.validate(run_id, gate, datetime.now(timezone.utc)):
                    raise PermissionError(f"fresh approval required: {gate}")
        marker = self.runs.runs_dir / f"{run_id}.pause"
        marker.unlink(missing_ok=True)
        state["parameters"] = new
        _atomic_json(self._state_path(run_id), state)
        self.audit.append("resume", request_id=request_id, actor=actor, run_id=run_id,
                          details={"old": old, "new": new})
        return {"run_id": run_id, "status": "resume_requested"}

    def kill(self, run_id: str, *, actor: str, request_id: str) -> dict[str, Any]:
        state = self.runs.get_run(run_id)
        if state is None:
            raise KeyError(run_id)
        process = self._processes.get(run_id)
        pgid = state.get("runner_pgid") or (process.pid if process is not None else None)
        if isinstance(pgid, int):
            try:
                os.killpg(pgid, signal.SIGTERM)
            except OSError:
                pass
            if process is not None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except OSError:
                        pass
                    process.wait(timeout=3)
        state["status"] = "interrupted"
        state["interrupted_at"] = datetime.now(timezone.utc).isoformat()
        state.pop("runner_pid", None)
        state.pop("runner_pgid", None)
        for record in state.get("stages", {}).values():
            if isinstance(record, dict) and record.get("status") in {"running", "retrying"}:
                record.update({"status": "failed", "returncode": None,
                               "error": "interrupted by console kill"})
        _atomic_json(self._state_path(run_id), state)
        self.audit.append("kill", request_id=request_id, actor=actor, run_id=run_id)
        return {"run_id": run_id, "status": "interrupted"}
