from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py"


def load_module():
    spec = importlib.util.spec_from_file_location("suggest_reply_templates", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.payload))
                )
            ]
        )


def test_paraphrased_budget_reply_uses_llm_intent():
    module = load_module()
    client = FakeClient({"intent": "ask_budget_first"})

    result = module.classify_reply_intent(
        {}, "We can discuss after next month's budget approval", client
    )

    assert result.intent == "ask_budget_first"
    assert result.manual_review is False
    assert client.calls == 1


def test_invalid_intent_falls_back_and_marks_review():
    module = load_module()
    client = FakeClient({"intent": "send_money"})

    result = module.classify_reply_intent({}, "maybe later", client)

    assert result.intent == "manual_review"
    assert result.manual_review is True
    assert client.calls == 1
