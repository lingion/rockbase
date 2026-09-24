"""Task 7: S2 Mail1 draft artifacts without LLM policy control.

The artifact envelope carries only bounded, redacted, deterministic
facts. An LLM can never change the recipient, link policy, or send
mode; those fields are absent from the artifact entirely so a later
Console decision is the only path that could advance queueing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py"

sys.path.insert(0, str(ROOT / "mailkit"))


def load_module():
    spec = importlib.util.spec_from_file_location("fill_mail1_with_codex", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["fill_mail1_with_codex"] = module
    spec.loader.exec_module(module)
    return module


def test_build_mail1_artifact_contains_bounded_fields_and_no_policy():
    module = load_module()
    row = {
        "频道/作者名称": "Test Creator",
        "clean_email": "creator@example.com",
        "Mail1_Greeting_Name": "Test",
        "Mail1_Hook": "your recent video on systems was genuinely useful",
        "Mail1_Reason": "your audience matches our brief",
        "Mail1_Variant": "standard",
    }
    generated = {
        "Mail1_Greeting_Name": "Test",
        "Mail1_Hook": "your recent video on systems was genuinely useful",
        "Mail1_Reason": "your audience matches our brief",
        "Mail1_Variant": "standard",
    }
    validation = {"ok": True, "errors": [], "warnings": []}

    artifact = module.build_mail1_artifact(row, generated, validation)

    assert artifact["stage"] == "s2.mail1"
    assert artifact["payload"]["greeting"] == "Test"
    # Body is best-effort — callers wire workflow_config when they want it
    # populated; the artifact boundary is what matters.
    assert isinstance(artifact["payload"]["body"], str)
    assert len(artifact["payload"]["body"]) <= 8000
    assert artifact["payload"]["validation"]["ok"] is True
    assert artifact["payload"]["validation"]["errors"] == []
    assert "pending_action" in artifact["payload"]
    assert artifact["payload"]["pending_action"] == "await_console_decision"
    # Policy fields are entirely absent — an LLM cannot set them because
    # there is nowhere to write them.
    for forbidden in ("send", "recipient", "recipient_email", "to", "cc",
                      "link_policy", "send_mode", "execute"):
        assert forbidden not in artifact["payload"]
    encoded = str(artifact)
    # Email addresses never leave the artifact boundary.
    assert "creator@example.com" not in encoded


def test_missing_required_fields_force_manual_review():
    module = load_module()
    row = {"频道/作者名称": "", "clean_email": "", "Mail1_Variant": "standard"}
    generated = {"Mail1_Greeting_Name": "", "Mail1_Hook": "", "Mail1_Reason": "",
                 "Mail1_Variant": "standard"}
    validation = {"ok": False, "errors": ["empty greeting"], "warnings": []}

    artifact = module.build_mail1_artifact(row, generated, validation)

    assert artifact["payload"]["pending_action"] == "manual_review"
    assert artifact["validation"]["ok"] is False
    assert "empty greeting" in artifact["validation"]["errors"]


def test_llm_payload_override_cannot_change_pending_action():
    """An LLM-returned value with the same key shape cannot inject policy."""
    module = load_module()
    row = {"频道/作者名称": "Test Creator", "Mail1_Variant": "standard"}
    # The "generated" dict here is what the model returned. Extra keys are
    # dropped at the artifact boundary, so no policy field can be injected.
    generated = {
        "Mail1_Greeting_Name": "Test",
        "Mail1_Hook": "a sufficiently long hook line for validation",
        "Mail1_Reason": "fits brief",
        "Mail1_Variant": "standard",
        "pending_action": "auto_send",
        "recipient": "attacker@example.com",
        "execute": True,
    }
    validation = {"ok": True, "errors": [], "warnings": []}

    artifact = module.build_mail1_artifact(row, generated, validation)

    assert artifact["payload"]["pending_action"] == "await_console_decision"
    assert "attacker@example.com" not in str(artifact)
    assert artifact["payload"].get("execute") is None
