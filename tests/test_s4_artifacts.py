"""S4 enrichment artifact contract tests."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "rockbase" / "llm_stage_contracts.py"


def load_contracts():
    spec = importlib.util.spec_from_file_location("llm_stage_contracts_s4", CONTRACTS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_enrichment_artifact_allowlists_labels_and_keeps_evidence():
    c = load_contracts()
    suggestions = {
        "账号类目标签": "AI工具",
        "tag_topics": "人工智能/开发者工具",
        "tag_risk": "low",
        "tag_confidence": "0.91",
        "recipient": "attacker@example.com",
        "execute": True,
    }
    evidence = [{"source": "bio", "field": "tag_topics", "quote": "Builds AI tools", "url": "https://example.com"}]
    artifact = c.build_enrichment_artifact("acct-1", suggestions, evidence, {"ok": True, "errors": [], "warnings": []})
    assert artifact["stage"] == "s4.enrichment"
    assert artifact["payload"]["pending_action"] == "await_console_decision"
    assert artifact["payload"]["suggestions"]["tag_topics"] == "人工智能/开发者工具"
    assert "recipient" not in artifact["payload"]["suggestions"]
    assert "execute" not in artifact["payload"]
    assert artifact["payload"]["evidence"][0]["quote"] == "Builds AI tools"


def test_build_enrichment_artifact_low_confidence_and_invalid_validation_require_review():
    c = load_contracts()
    low = c.build_enrichment_artifact(
        "acct-1", {"tag_topics": "unknown", "tag_confidence": 0.4}, [],
        {"ok": True, "errors": [], "warnings": []},
    )
    assert low["payload"]["pending_action"] == "manual_review"
    assert "low-confidence" in low["validation"]["warnings"]
    invalid = c.build_enrichment_artifact(
        "acct-1", {"tag_confidence": 0.9}, [],
        {"ok": False, "errors": ["bad label"], "warnings": []},
    )
    assert invalid["payload"]["pending_action"] == "manual_review"
    assert invalid["validation"]["errors"] == ["bad label"]


def test_apply_approved_artifact_refuses_unapproved_or_stale():
    c = load_contracts()
    base = {"artifact_id": "art-s4", "version": 4, "approved": False}
    assert c.apply_approved_artifact("art-s4", 4, base)["reason"] == "not-approved"
    approved = dict(base, approved=True)
    assert c.apply_approved_artifact("art-s4", 3, approved)["reason"] == "stale-artifact"
    assert c.apply_approved_artifact("art-s4", 4, approved)["status"] == "preview"
