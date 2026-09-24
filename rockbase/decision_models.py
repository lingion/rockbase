"""Bounded, versioned contracts for LLM artifacts and Console decisions."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

MAX_PAYLOAD_BYTES = 100_000
MAX_FEEDBACK_CHARS = 2_000
MAX_ID_CHARS = 128
_ALLOWED_ACTIONS = frozenset({"approve", "reject", "reject_with_feedback", "approve_run"})
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _validate_id(value: str, name: str) -> str:
    value = str(value).strip()
    if not value or len(value) > MAX_ID_CHARS or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _bounded_json(value: Mapping[str, Any], name: str = "payload") -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"{name} exceeds size bound")
    return dict(value)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(str(x)[:256] for x in self.errors))
        object.__setattr__(self, "warnings", tuple(str(x)[:256] for x in self.warnings))

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings)}


@dataclass(frozen=True)
class ArtifactEnvelope:
    artifact_id: str
    run_id: str
    stage_id: str
    version: int
    payload: dict[str, Any]
    validation: dict[str, Any]
    created_at: str
    parent_id: str | None = None
    content_hash_value: str = field(default="")

    @classmethod
    def new(
        cls,
        run_id: str,
        stage_id: str,
        payload: Mapping[str, Any],
        validation: Mapping[str, Any] | ValidationResult,
        *,
        parent_id: str | None = None,
    ) -> "ArtifactEnvelope":
        run_id = _validate_id(run_id, "run_id")
        stage_id = _validate_id(stage_id, "stage_id")
        payload_dict = _bounded_json(payload)
        validation_dict = validation.to_dict() if isinstance(validation, ValidationResult) else _bounded_json(validation, "validation")
        if parent_id is not None:
            parent_id = _validate_id(parent_id, "parent_id")
        artifact = cls(
            artifact_id=f"art-{uuid.uuid4().hex}", run_id=run_id, stage_id=stage_id,
            version=1, payload=payload_dict, validation=validation_dict,
            created_at=datetime.now(timezone.utc).isoformat(), parent_id=parent_id,
        )
        return artifact.with_hash()

    def with_version(self, version: int) -> "ArtifactEnvelope":
        if not isinstance(version, int) or version < 1:
            raise ValueError("version must be positive")
        return type(self)(**{**self.__dict__, "version": version}).with_hash()

    def with_hash(self) -> "ArtifactEnvelope":
        value = hashlib.sha256(self._hash_input()).hexdigest()
        return type(self)(**{**self.__dict__, "content_hash_value": value})

    def _hash_input(self) -> bytes:
        data = {
            "artifact_id": self.artifact_id, "run_id": self.run_id,
            "stage_id": self.stage_id, "version": self.version,
            "payload": self.payload, "validation": self.validation,
            "parent_id": self.parent_id,
        }
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    def content_hash(self) -> str:
        return self.content_hash_value or hashlib.sha256(self._hash_input()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id, "run_id": self.run_id,
            "stage_id": self.stage_id, "version": self.version,
            "payload": self.payload, "validation": self.validation,
            "created_at": self.created_at, "parent_id": self.parent_id,
            "content_hash": self.content_hash(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArtifactEnvelope":
        artifact = cls(
            artifact_id=_validate_id(data["artifact_id"], "artifact_id"),
            run_id=_validate_id(data["run_id"], "run_id"),
            stage_id=_validate_id(data["stage_id"], "stage_id"),
            version=int(data["version"]), payload=_bounded_json(data["payload"]),
            validation=_bounded_json(data["validation"], "validation"),
            created_at=str(data["created_at"]), parent_id=data.get("parent_id"),
            content_hash_value=str(data.get("content_hash", "")),
        )
        if artifact.content_hash() != artifact.content_hash_value:
            raise ValueError("artifact content hash mismatch")
        return artifact


@dataclass(frozen=True)
class DecisionRequest:
    artifact_id: str
    artifact_version: int
    action: str
    actor: str
    feedback: str | None = None

    def __post_init__(self) -> None:
        _validate_id(self.artifact_id, "artifact_id")
        _validate_id(self.actor, "actor")
        if not isinstance(self.artifact_version, int) or self.artifact_version < 1:
            raise ValueError("artifact version must be positive")
        if self.action not in _ALLOWED_ACTIONS:
            raise ValueError("unknown decision action")
        if self.action == "reject_with_feedback" and not (self.feedback or "").strip():
            raise ValueError("feedback is required")
        if self.feedback is not None and len(self.feedback) > MAX_FEEDBACK_CHARS:
            raise ValueError("feedback exceeds size bound")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in {
            "artifact_id": self.artifact_id, "artifact_version": self.artifact_version,
            "action": self.action, "actor": self.actor, "feedback": self.feedback,
        }.items() if v is not None}


def validate_decision(request: DecisionRequest, artifact: ArtifactEnvelope) -> None:
    if request.artifact_id != artifact.artifact_id:
        raise ValueError("artifact_id does not match current artifact")
    if request.artifact_version != artifact.version:
        raise ValueError("artifact version is stale")
    if request.actor == "viewer" or not request.actor.strip():
        raise ValueError("actor is not an operator")
    if not artifact.validation.get("ok", False) and request.action in {"approve", "approve_run"}:
        raise ValueError("invalid artifact cannot be approved")
