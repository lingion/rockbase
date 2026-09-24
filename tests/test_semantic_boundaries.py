from __future__ import annotations

import importlib.util
import json
import sys
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


sys.path.insert(0, str(ROOT / "mailkit"))
from mailkit.reply_semantics import ReplySummary, summarize_reply  # noqa: E402


def _reply(text: str) -> str:
    return text


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))]
        )


class _TimeoutLLM:
    def chat(self):
        raise TimeoutError("upstream timeout")

    chat_completions_create = chat

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **_kwargs):
        raise TimeoutError("upstream timeout")


def test_reply_summary_extracts_conditions_and_next_action():
    client = _FakeLLM({
        "summary": "willing after brief approval",
        "conditions": ["after brief approval"],
        "next_action": "send_brief",
        "language": "en",
        "confidence": 0.7,
    })

    summary = summarize_reply("We can do $500 after the brief is approved", client=client)

    assert isinstance(summary, ReplySummary)
    assert summary.next_action == "send_brief"
    assert tuple(summary.conditions) == ("after brief approval",)
    assert summary.manual_review is False
    assert summary.to_artifact()["payload"]["next_action"] == "send_brief"


def test_summary_timeout_returns_bounded_manual_review():
    summary = summarize_reply("long reply " * 50, client=_TimeoutLLM())

    assert summary.manual_review is True
    assert len(summary.summary) <= 160
    assert summary.next_action == "manual_review"


def test_summary_redacts_email_phone_url():
    client = _FakeLLM({
        "summary": "Contact alice@example.com at +1 555-1212 or https://x.test",
        "conditions": [],
        "next_action": "respond",
        "language": "en",
        "confidence": 0.5,
    })

    summary = summarize_reply("Contact alice@example.com at +1 555-1212 or https://x.test",
                              client=client)
    encoded = json.dumps(summary.to_artifact())
    assert "alice@example.com" not in encoded
    assert "555-1212" not in encoded
    assert "https://x.test" not in encoded
