"""Task 8: S5 OCR artifacts + semantic brief matching.

The OCR artifact boundary carries only bounded extracted fields,
validation counts, and image references — never raw image data or
credentials. The brief matcher uses the LLM only to explain and rank
candidates from a deterministic candidate set; a model response cannot
select a row outside that set or override hard exclusions.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OCR_SCRIPT = ROOT / "skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py"
BRIEF_SCRIPT = ROOT / "skills/S5-ag-kol-brief-matching/scripts/brief_match.py"


def load_ocr():
    if "cv2" not in sys.modules:
        sys.modules["cv2"] = type("Cv2Stub", (), {})()
    spec = importlib.util.spec_from_file_location("ag_ocr_sync_artifacts", OCR_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_brief():
    spec = importlib.util.spec_from_file_location("brief_match", BRIEF_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# OCR artifact
# ---------------------------------------------------------------------------


def _make_screenshot_data(module, **overrides):
    defaults = dict(
        path="/tmp/profile_001.png",
        handle="@creator.one",
        author_name="Creator One",
        email="creator@example.com",
        countries="美国 30% / 中国 22% / 巴西 18% / 德国 12%",
        gender="男60%/女40%",
        age="18-25 (38%)/25-45 (45%)",
        raw_hits={"engine": "llm", "payload": {"sensitive": True}},
        matched_row=42,
        match_reason="handle",
        review_reasons=[],
        blocked_fields=[],
        duplicate=False,
        confidence=0.91,
        review_required=False,
        second_pass_fixed=False,
        second_pass_notes=[],
    )
    defaults.update(overrides)
    return module.ScreenshotData(**defaults)


def test_build_ocr_artifact_happy_path_bounded_and_no_payload():
    module = load_ocr()
    data = _make_screenshot_data(module)
    duplicate_images = [{"path": "/tmp/dup.png", "exact_hash": "abc123", "visual_hash": "v456"}]
    validation = {"ok": True, "errors": [], "warnings": []}

    artifact = module.build_ocr_artifact(
        results=[data],
        duplicate_images=duplicate_images,
        validation=validation,
        image_dir="/tmp/screens",
    )

    assert artifact["stage"] == "s5.ocr"
    assert artifact["payload"]["pending_action"] == "await_console_decision"
    assert artifact["payload"]["validation"]["ok"] is True
    assert artifact["payload"]["counts"]["selected"] == 1
    # duplicate_images holds skipped files (not per-result duplicate flags),
    # so the per-image duplicate count is 0 while the skipped-file table has 1.
    assert artifact["payload"]["counts"]["duplicates"] == 0
    assert len(artifact["payload"]["duplicate_images"]) == 1
    assert artifact["payload"]["counts"]["review_required"] == 0
    assert artifact["payload"]["counts"]["blocked_fields"] == 0

    image = artifact["payload"]["images"][0]
    assert image["handle"] == "@creator.one"
    assert image["author_name"] == "Creator One"
    assert image["countries"] == "美国 30% / 中国 22% / 巴西 18% / 德国 12%"
    assert image["confidence"] == 0.91
    assert image["matched_row"] == 42
    assert image["match_reason"] == "handle"

    # raw_hits must not leak into the artifact boundary
    encoded = str(artifact)
    assert "raw_hits" not in encoded
    assert "sensitive" not in encoded
    assert "data:image" not in encoded
    assert "base64" not in encoded
    assert "creator@example.com" not in encoded


def test_build_ocr_artifact_invalid_validation_forces_manual_review():
    module = load_ocr()
    data = _make_screenshot_data(module, confidence=0.4)
    data.review_reasons = ["low-confidence"]
    validation = {"ok": False, "errors": ["low confidence"], "warnings": []}

    artifact = module.build_ocr_artifact(
        results=[data],
        duplicate_images=[],
        validation=validation,
        image_dir="",
    )

    assert artifact["payload"]["pending_action"] == "manual_review"
    assert artifact["validation"]["ok"] is False
    assert "low confidence" in artifact["validation"]["errors"]


def test_build_ocr_artifact_duplicate_image_is_flagged_but_not_leaked():
    module = load_ocr()
    primary = _make_screenshot_data(module, duplicate=False, matched_row=10)
    dup = _make_screenshot_data(
        module,
        path="/tmp/dup_same.png",
        duplicate=True,
        matched_row=10,
        confidence=0.88,
    )
    duplicates = [{"path": "/tmp/dup_same.png", "exact_hash": "hash-X", "visual_hash": "hash-Y"}]

    artifact = module.build_ocr_artifact(
        results=[primary, dup],
        duplicate_images=duplicates,
        validation={"ok": True, "errors": [], "warnings": []},
        image_dir="/tmp/screens",
    )

    duplicate_payload = [img for img in artifact["payload"]["images"] if img.get("duplicate")]
    assert len(duplicate_payload) == 1
    assert duplicate_payload[0]["path"] == "/tmp/dup_same.png"
    assert artifact["payload"]["counts"]["duplicates"] == 1
    # The duplicate-hash table itself stays opaque references, not raw bytes.
    assert all("data:" not in str(d) for d in artifact["payload"]["duplicate_images"])


def test_build_ocr_artifact_emits_blocked_field_summary():
    module = load_ocr()
    data = _make_screenshot_data(module, gender="", age="")
    data.blocked_fields = ["粉丝性别", "粉丝年龄"]
    validation = {"ok": True, "errors": [], "warnings": ["blocked fields present"]}

    artifact = module.build_ocr_artifact(
        results=[data],
        duplicate_images=[],
        validation=validation,
        image_dir="",
    )

    assert artifact["payload"]["counts"]["blocked_fields"] == 2
    summary = artifact["payload"]["blocked_fields_summary"]
    assert "粉丝性别" in summary
    assert "粉丝年龄" in summary


# ---------------------------------------------------------------------------
# Brief matching
# ---------------------------------------------------------------------------


def _row(key: str, **values) -> dict:
    row = {"row_key": key, "账号ID": values.get("handle", key)}
    for k, v in values.items():
        row[k] = v
    return row


def test_match_brief_to_master_deterministic_candidates_only():
    module = load_brief()
    brief = {
        "must_have": ["tag_topics:美妆"],
        "should_have": ["tag_audience:女性 25-45"],
        "must_avoid": [],
        "preferred_platform": ["instagram"],
        "preferred_market": ["中国"],
        "narrative_need": "education",
    }
    rows = [
        _row("r1", handle="@creator.one", tag_topics="美妆/护肤", tag_audience="女性 25-45",
             tag_platform_fit="instagram", tag_market="中国", tag_risk="none",
             tag_narrative="education"),
        _row("r2", handle="@creator.two", tag_topics="游戏", tag_audience="男性 18-25",
             tag_platform_fit="youtube", tag_market="美国", tag_risk="none",
             tag_narrative="entertainment"),
        _row("r3", handle="@creator.three", tag_topics="美妆", tag_audience="女性 18-25",
             tag_platform_fit="tiktok", tag_market="中国", tag_risk="low",
             tag_narrative="education"),
    ]

    matches = module.match_brief_to_master(brief, rows, client=None)

    row_keys = [m.row_key for m in matches]
    # r2 fails the platform+market must-have, so it must be excluded.
    assert "r2" not in row_keys
    # r1 and r3 satisfy deterministic must-haves.
    assert "r1" in row_keys
    assert "r3" in row_keys
    for m in matches:
        assert isinstance(m.manual_review, bool)
        assert 0.0 <= m.confidence <= 1.0
        assert m.row_key in {"r1", "r3"}


def test_match_brief_to_master_model_row_outside_set_is_rejected():
    """An LLM cannot pick a row that failed deterministic filtering."""
    module = load_brief()

    class _AdversarialClient:
        def __init__(self):
            self.calls = 0

        def rank(self, candidates, brief):
            self.calls += 1
            # The adversarial model tries to inject a row that was filtered out.
            return [
                module.MatchResult(
                    row_key="r_filtered",
                    semantic_reason="model insists",
                    confidence=0.99,
                    constraints="model",
                    manual_review=False,
                ),
                *candidates,
            ]

    brief = {
        "must_have": ["tag_topics:美妆"],
        "must_avoid": [],
        "preferred_platform": [],
        "preferred_market": [],
    }
    rows = [
        _row("r_good", tag_topics="美妆"),
        _row("r_filtered", tag_topics="游戏"),
    ]
    client = _AdversarialClient()

    matches = module.match_brief_to_master(brief, rows, client=client)

    row_keys = [m.row_key for m in matches]
    assert "r_filtered" not in row_keys
    assert "r_good" in row_keys
    # The injected row should have been dropped, not just demoted.
    assert all(m.row_key != "r_filtered" for m in matches)


def test_match_brief_to_master_low_confidence_forces_manual_review():
    module = load_brief()

    class _LowConfidenceClient:
        def rank(self, candidates, brief):
            return [
                module.MatchResult(
                    row_key=candidates[0].row_key,
                    semantic_reason="weak fit",
                    confidence=0.4,
                    constraints="model",
                    manual_review=False,
                ),
            ]

    brief = {"must_have": ["tag_topics:美妆"], "must_avoid": []}
    rows = [_row("r1", tag_topics="美妆")]

    matches = module.match_brief_to_master(brief, rows, client=_LowConfidenceClient())

    assert len(matches) == 1
    assert matches[0].manual_review is True
    assert matches[0].confidence == 0.4


def test_match_brief_to_master_no_client_falls_back_to_deterministic():
    module = load_brief()
    brief = {"must_have": ["tag_topics:美妆"], "must_avoid": []}
    rows = [
        _row("r_a", tag_topics="美妆/护肤"),
        _row("r_b", tag_topics="游戏"),
    ]

    matches = module.match_brief_to_master(brief, rows, client=None)

    row_keys = [m.row_key for m in matches]
    assert "r_a" in row_keys
    assert "r_b" not in row_keys
    # Without a client, results are pure deterministic scoring. A single
    # must-have hit scores below the 0.75 review threshold, so the row is
    # still flagged for manual review — deterministic coverage is preserved
    # but thin evidence never auto-approves.
    assert matches
    for m in matches:
        if m.confidence < 0.75:
            assert m.manual_review is True


def test_match_brief_to_master_must_avoid_hard_exclusion():
    module = load_brief()
    brief = {"must_have": ["tag_topics:美妆"], "must_avoid": ["risk:political"]}
    rows = [
        _row("r_safe", tag_topics="美妆", tag_risk="none"),
        _row("r_political", tag_topics="美妆", tag_risk="political"),
    ]

    matches = module.match_brief_to_master(brief, rows, client=None)
    row_keys = [m.row_key for m in matches]
    assert "r_safe" in row_keys
    assert "r_political" not in row_keys