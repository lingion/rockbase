"""Validated state discovery and console approval persistence."""
from __future__ import annotations

import json
import os
import re
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
