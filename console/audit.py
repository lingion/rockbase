"""Append-only, bounded audit events for the local operations console."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SAFE_DETAIL_KEYS = frozenset({"result", "gate", "batch_label", "old", "new", "reason"})
_MAX_DETAIL_VALUE = 256
_MAX_LINE_BYTES = 4096


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    safe: dict[str, Any] = {}
    for key in _SAFE_DETAIL_KEYS:
        value = details.get(key)
        if value is None or isinstance(value, (bool, int, float)):
            if value is not None:
                safe[key] = value
        elif isinstance(value, str):
            safe[key] = value[:_MAX_DETAIL_VALUE]
        elif isinstance(value, dict):
            nested: dict[str, Any] = {}
            for child_key, child_value in value.items():
                if not isinstance(child_key, str):
                    continue
                if isinstance(child_value, (bool, int, float)) or child_value is None:
                    nested[child_key[:64]] = child_value
                elif isinstance(child_value, str):
                    nested[child_key[:64]] = child_value[:_MAX_DETAIL_VALUE]
            safe[key] = nested
    return safe


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(
        self,
        event: str,
        *,
        request_id: str,
        actor: str,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "event": str(event)[:128],
            "request_id": str(request_id)[:128],
            "actor": str(actor)[:128],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "ok",
        }
        if run_id is not None:
            record["run_id"] = str(run_id)[:128]
        record.update(_safe_details(details))
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")
        if len(encoded) > _MAX_LINE_BYTES:
            record["details_truncated"] = True
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    def tail(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        limit = min(limit, 500)
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines()[-limit:]:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(item)
        return events
