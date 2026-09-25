"""S1 candidate artifact contract: bounded, allow-listed, preview/apply."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "rockbase" / "llm_stage_contracts.py"


def load_contracts():
    spec = importlib.util.spec_from_file_location("llm_stage_contracts", CONTRACTS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_candidate_artifact_happy_path_is_bounded_and_await():
    c = load_contracts()
    rows = [
        {"row_key": "r1", "platform": "YouTube", "url": "https://youtube.com/@x",
         "handle": "@x", "author_name": "X", "api_status": "ok"},
        {"row_key": "r2", "platform": "Instagram", "url": "https://instagram.com/x",
         "handle": "@x2", "author_name": "X2", "api_status": "ok"},
    ]
    model = [
        {"row_key": "r1", "entity_type": "creator", "relevance": "core",
         "confidence": 0.91, "reason": "fitness topic"},
        {"row_key": "r2", "entity_type": "creator", "relevance": "core",
         "confidence": 0.83, "reason": "lifestyle"},
    ]
    artifact = c.build_candidate_artifact(rows, model, {"ok": True, "errors": [], "warnings": []})
    assert artifact["stage"] == "s1.candidates"
    assert artifact["payload"]["pending_action"] == "await_console_decision"
    keys = {item["row_key"] for item in artifact["payload"]["candidates"]}
    assert keys == {"r1", "r2"}
    encoded = str(artifact)
    # Boundary: model cannot smuggle in policy-like keys.
    for forbidden in ("send", "execute", "recipient", "policy_version", "auto"):
        assert forbidden not in artifact["payload"]


def test_build_candidate_artifact_api_failure_forces_manual_review():
    c = load_contracts()
    rows = [{"row_key": "r1", "platform": "YouTube", "url": "https://youtube.com/@x", "api_status": "404"}]
    model = [{"row_key": "r1", "entity_type": "creator", "confidence": 0.95, "reason": "looks fine"}]
    artifact = c.build_candidate_artifact(rows, model, {"ok": True, "errors": [], "warnings": []})
    assert artifact["payload"]["pending_action"] == "manual_review"
    item = artifact["payload"]["candidates"][0]
    assert item["candidate_status"] == "manual_review"
    assert "api:404" in item["constraints"]


def test_build_candidate_artifact_low_confidence_forces_manual_review():
    c = load_contracts()
    rows = [{"row_key": "r1", "platform": "YouTube", "url": "https://youtube.com/@x", "api_status": "ok"}]
    model = [{"row_key": "r1", "entity_type": "creator", "confidence": 0.5, "reason": "maybe"}]
    artifact = c.build_candidate_artifact(rows, model, {"ok": True, "errors": [], "warnings": []})
    assert artifact["payload"]["pending_action"] == "manual_review"
    assert artifact["payload"]["candidates"][0]["confidence"] == 0.5


def test_build_candidate_artifact_unknown_row_dropped_with_warning():
    c = load_contracts()
    rows = [{"row_key": "r1", "platform": "YouTube", "url": "https://youtube.com/@x", "api_status": "ok"}]
    model = [
        {"row_key": "r1", "entity_type": "creator", "confidence": 0.9},
        {"row_key": "ghost", "entity_type": "creator", "confidence": 0.9},
    ]
    artifact = c.build_candidate_artifact(rows, model, {"ok": True, "errors": [], "warnings": []})
    assert len(artifact["payload"]["candidates"]) == 1
    assert any("unknown:row_key:ghost" in w for w in artifact["validation"]["warnings"])


def test_apply_approved_artifact_requires_execute_and_approval():
    c = load_contracts()
    approved = {
        "artifact_id": "art-abc", "version": 3, "approved": True,
        "content_hash": "deadbeef", "write_count": 5,
    }
    preview = c.apply_approved_artifact("art-abc", 3, approved)
    assert preview["ok"] is True and preview["status"] == "preview" and preview["writes"] == 0
    applied = c.apply_approved_artifact("art-abc", 3, approved, execute=True)
    assert applied["ok"] is True and applied["status"] == "applied" and applied["writes"] == 5
    # Stale version rejected.
    stale = c.apply_approved_artifact("art-abc", 2, approved, execute=True)
    assert stale["ok"] is False and stale["status"] == "rejected" and stale["reason"] == "stale-artifact"
    # Id mismatch rejected.
    mismatch = c.apply_approved_artifact("art-other", 3, approved, execute=True)
    assert mismatch["ok"] is False and mismatch["reason"] == "artifact-id-mismatch"
    # Unapproved rejected even with execute=True.
    unapproved = dict(approved, approved=False)
    blocked = c.apply_approved_artifact("art-abc", 3, unapproved, execute=True)
    assert blocked["ok"] is False and blocked["reason"] == "not-approved"