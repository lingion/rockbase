from __future__ import annotations

import pytest

from rockbase.decision_models import (
    ArtifactEnvelope,
    DecisionRequest,
    ValidationResult,
    validate_decision,
)


def test_artifact_envelope_is_bounded_and_hashed():
    artifact = ArtifactEnvelope.new(
        "run-1", "s3.intent", {"intent": "quoted"}, {"ok": True}
    )
    assert artifact.run_id == "run-1"
    assert artifact.version == 1
    assert artifact.content_hash()
    assert artifact.to_dict()["content_hash"] == artifact.content_hash()


def test_feedback_and_payload_bounds_are_rejected():
    with pytest.raises(ValueError, match="feedback"):
        DecisionRequest("a1", 1, "reject_with_feedback", "operator", "x" * 2001)
    with pytest.raises(ValueError, match="payload"):
        ArtifactEnvelope.new("run-1", "s3.intent", {"text": "x" * 100001}, {"ok": True})


def test_decision_validation_requires_current_version_and_operator():
    artifact = ArtifactEnvelope.new("run-1", "s3.intent", {"intent": "quoted"}, {"ok": True})
    valid = DecisionRequest(artifact.artifact_id, 1, "approve", "operator")
    validate_decision(valid, artifact)
    with pytest.raises(ValueError, match="artifact_id"):
        validate_decision(DecisionRequest("wrong", 1, "approve", "operator"), artifact)
    with pytest.raises(ValueError, match="version"):
        validate_decision(DecisionRequest(artifact.artifact_id, 0, "approve", "operator"), artifact)
    with pytest.raises(ValueError, match="actor"):
        validate_decision(DecisionRequest(artifact.artifact_id, 1, "approve", "viewer"), artifact)


def test_validation_result_serializes():
    result = ValidationResult(ok=False, errors=("missing field",), warnings=("low confidence",))
    assert result.to_dict() == {
        "ok": False,
        "errors": ["missing field"],
        "warnings": ["low confidence"],
    }
