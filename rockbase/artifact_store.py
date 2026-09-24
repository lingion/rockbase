"""Atomic local persistence for versioned artifact envelopes."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from .decision_models import ArtifactEnvelope


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    def _path(self, artifact_id: str, version: int) -> Path:
        return self.root / artifact_id / f"{version}.json"

    def _next_version(self, run_id: str, stage_id: str) -> int:
        """Versions are monotonic per (run_id, stage_id) lineage."""
        highest = 0
        for path in self.root.glob("art-*/*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("run_id") == run_id and data.get("stage_id") == stage_id:
                try:
                    highest = max(highest, int(data.get("version", 0)))
                except (TypeError, ValueError):
                    continue
        return highest + 1

    def put(self, artifact: ArtifactEnvelope) -> ArtifactEnvelope:
        with self._lock:
            version = self._next_version(artifact.run_id, artifact.stage_id)
            stored = artifact.with_version(version)
            path = self._path(stored.artifact_id, version)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f".{version}.", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(stored.to_dict(), handle, ensure_ascii=False, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return stored

    def get(self, artifact_id: str, version: int | None = None) -> ArtifactEnvelope | None:
        directory = self.root / artifact_id
        if version is None:
            candidates = [path for path in directory.glob("*.json") if path.stem.isdigit()]
            if not candidates:
                return None
            path = max(candidates, key=lambda candidate: int(candidate.stem))
        else:
            path = self._path(artifact_id, version)
        if not path.exists():
            return None
        return ArtifactEnvelope.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_for_run(self, run_id: str) -> list[ArtifactEnvelope]:
        if not self.root.exists():
            return []
        result: list[ArtifactEnvelope] = []
        for path in self.root.glob("art-*/*.json"):
            try:
                item = ArtifactEnvelope.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if item.run_id == run_id:
                result.append(item)
        return sorted(result, key=lambda item: (item.created_at, item.stage_id, item.version))
