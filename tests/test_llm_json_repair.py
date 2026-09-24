from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_part2_json_repair", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_json_accepts_fence_prose_trailing_commas_and_nested_braces():
    module = load_module()
    raw = 'Result follows:\n```json\n{"notes": "literal {brace}", "items": [1, 2,],}\n```'
    parsed = module.extract_json(raw)
    assert parsed == {"notes": "literal {brace}", "items": [1, 2]}


def test_extract_json_rejects_malformed_semantic_content():
    module = load_module()
    # Syntax is valid, but this is not a usable Part2 result. The parser must
    # not invent missing semantic fields; validation remains authoritative.
    parsed = module.normalize_result(module.extract_json('{"notes": "only notes"}'))
    issues = module.validate_result(parsed)
    assert "missing_keys" not in issues  # normalize_result supplies schema keys
    assert parsed["latest_price_normalized"] == ""
    assert parsed["latest_price_basis"] == ""


def test_extract_json_does_not_use_eval(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "eval", lambda *a, **k: (_ for _ in ()).throw(AssertionError("eval used")), raising=False)
    assert module.extract_json("prefix {\"a\": 1,}") == {"a": 1}
