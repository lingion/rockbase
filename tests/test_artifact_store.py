from __future__ import annotations

import pytest

from rockbase.artifact_store import ArtifactStore
from rockbase.decision_models import ArtifactEnvelope


def test_artifact_versions_are_monotonic_and_hashed(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.put(ArtifactEnvelope.new("run-1", "s3.intent", {"intent": "quoted"}, {"ok": True}))
    second = store.put(ArtifactEnvelope.new("run-1", "s3.intent", {"intent": "decline"}, {"ok": True}, parent_id=first.artifact_id))
    assert second.version == first.version + 1
    assert second.content_hash() != first.content_hash()
    assert store.get(first.artifact_id).version == 1
    assert store.get(second.artifact_id, 2).payload["intent"] == "decline"


def test_store_rejects_corrupt_or_missing_artifacts(tmp_path):
    store = ArtifactStore(tmp_path)
    assert store.get("missing") is None
    with pytest.raises(ValueError, match="payload"):
        store.put(ArtifactEnvelope.new("run-1", "stage", {"x": "a" * 100001}, {"ok": True}))


def test_list_for_run_is_stable(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.put(ArtifactEnvelope.new("run-1", "s1", {"x": 1}, {"ok": True}))
    second = store.put(ArtifactEnvelope.new("run-2", "s1", {"x": 2}, {"ok": True}))
    assert [item.artifact_id for item in store.list_for_run("run-1")] == [first.artifact_id]
    assert store.list_for_run("missing") == []
