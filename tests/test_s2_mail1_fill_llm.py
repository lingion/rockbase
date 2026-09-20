"""Offline contract tests for the LLM-driven Mail1 fill path.

These tests lock the contract that:
- `fill_mail1_with_codex` exposes a `run_llm_batch` function (OpenAI SDK call).
- Public argparse surface replaces `--codex-bin` with `--api-key` / `--base-url` /
  `--model-name` and keeps `--model` as an alias for back-compat.
- The schema returned per row is identical to the legacy Codex path:
    Mail1_Greeting_Name, Mail1_Hook, Mail1_Variant, Mail1_Reason.
- Network is never touched: an injected fake client drives the batch.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py"
CONFIG = ROOT / "skills/S2-ag-gmail-bulk-drafts/references/cold_mail_workflow_config.json"


def load_module():
    spec = importlib.util.spec_from_file_location("fill_mail1_with_codex", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass needs cls.__module__ resolvable
    spec.loader.exec_module(module)
    return module


def make_rows(n: int = 2):
    base = {
        "账号ID": f"id_{n}",
        "频道/作者名称": f"Channel {n}",
        "平台": "YouTube",
        "语言": "English",
        "账号类目标签": "tech",
        "账号简介": "explains AI tooling",
        "账号简介__平台抓取": "",
        "Recommendation": "",
        "联系方式": f"user{n}@example.invalid",
        "clean_email": f"user{n}@example.invalid",
    }
    for i in range(1, n + 1):
        yield dict(base, **{"账号ID": f"id_{i}", "频道/作者名称": f"Channel {i}"})


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, model, temperature, messages):
        self.calls.append({"model": model, "temperature": temperature, "messages": messages})
        body = self.responses.pop(0)
        msg = body if isinstance(body, str) else json.dumps(body)

        class _Choice:
            def __init__(self, content):
                self.message = type("M", (), {"content": content})()

        class _Response:
            def __init__(self, content):
                self.choices = [_Choice(content)]

        return _Response(msg)


class FakeClient:
    def __init__(self, responses):
        self.chat = type("Chat", (), {"completions": FakeCompletions(responses)})()


def test_module_exposes_run_llm_batch_and_drops_codex_runner():
    module = load_module()
    assert hasattr(module, "run_llm_batch"), "expected run_llm_batch for the OpenAI SDK path"
    assert not hasattr(module, "run_codex_batch"), "legacy codex runner must be removed"
    assert hasattr(module, "MODEL_DEFAULT"), "default model constant must remain for ops docs"


def test_run_llm_batch_normalizes_schema_per_row():
    module = load_module()
    rows = list(make_rows(2))
    targets = [
        module.TargetRow(sheet_row_number=2, row_index=0, data=rows[0]),
        module.TargetRow(sheet_row_number=3, row_index=1, data=rows[1]),
    ]
    fake_response = {
        "rows": [
            {
                "sheet_row_number": 2,
                "Mail1_Greeting_Name": "Channel 1",
                "Mail1_Hook": "Hook for the first creator covering AI tooling in plain English.",
                "Mail1_Variant": "A1_media_kit_soft",
                "Mail1_Reason": "brand channel, soft ask",
            },
            {
                "sheet_row_number": 3,
                "Mail1_Greeting_Name": "Channel 2 Team",
                "Mail1_Hook": "Hook for the second creator covering AI tooling in plain English.",
                "Mail1_Variant": "B1_creator_specific_soft",
                "Mail1_Reason": "personal brand, soft ask",
            },
        ]
    }
    workflow_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    client = FakeClient([fake_response])

    result = module.run_llm_batch(
        batch=targets,
        client=client,
        model="gpt-4o-mini",
        workflow_config=workflow_config,
        temperature=0,
    )

    assert set(result.keys()) == {2, 3}
    for row_number, payload in result.items():
        assert set(payload.keys()) == {
            "Mail1_Greeting_Name",
            "Mail1_Hook",
            "Mail1_Variant",
            "Mail1_Reason",
        }
        assert payload["Mail1_Variant"] in set(workflow_config["allowed_variants"])
        assert len(payload["Mail1_Hook"].split()) >= 6
    # one OpenAI call per batch
    assert len(client.chat.completions.calls) == 1
    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["temperature"] == 0
    # both target rows visible to the model
    user_payload = call["messages"][-1]["content"]
    assert "sheet_row_number" in user_payload


def test_run_llm_batch_parses_fenced_json_payload():
    module = load_module()
    row = next(make_rows(1))
    target = module.TargetRow(sheet_row_number=2, row_index=0, data=row)
    workflow_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    fenced = (
        "Here is the result:\n"
        "```json\n"
        + json.dumps(
            {
                "rows": [
                    {
                        "sheet_row_number": 2,
                        "Mail1_Greeting_Name": "Channel 1",
                        "Mail1_Hook": "Hook sentence with at least six words about AI tooling.",
                        "Mail1_Variant": "A1_media_kit_soft",
                        "Mail1_Reason": "brand channel, soft ask",
                    }
                ]
            }
        )
        + "\n```\n"
    )
    client = FakeClient([fenced])
    result = module.run_llm_batch(
        batch=[target],
        client=client,
        model="gpt-4o-mini",
        workflow_config=workflow_config,
        temperature=0,
    )
    assert 2 in result
    assert result[2]["Mail1_Variant"] == "A1_media_kit_soft"


def test_argparse_replaces_codex_bin_with_api_key_and_base_url():
    """`python -m` style introspection: drive argparse and assert the new flags."""
    module = load_module()
    parser = module._build_argparser() if hasattr(module, "_build_argparser") else None
    if parser is None:
        pytest.skip("argparser builder not exposed yet")
    args = parser.parse_args(
        [
            "--input",
            "in.csv",
            "--api-key",
            "sk-test",
            "--base-url",
            "https://example.invalid/v1",
            "--model",
            "gpt-4o-mini",
        ]
    )
    assert args.api_key == "sk-test"
    assert args.base_url == "https://example.invalid/v1"
    assert args.model == "gpt-4o-mini"
    # legacy flag must no longer be registered
    with pytest.raises(SystemExit):
        parser.parse_args(["--input", "in.csv", "--codex-bin", "codex"])


def test_main_with_dry_run_writes_audit_only(tmp_path, monkeypatch):
    """End-to-end smoke against a fake CSV + fake LLM. dry-run must NOT mutate the CSV."""
    module = load_module()
    input_csv = tmp_path / "input.csv"
    input_csv.write_text(
        "﻿账号ID,频道/作者名称,平台,语言,账号类目标签,账号简介,联系方式,clean_email,Mail1发出状态,manual_clean_decision,email_qc_flag\n"
        "id_1,Channel 1,YouTube,English,tech,explains AI,user1@example.invalid,user1@example.invalid,,,\n",
        encoding="utf-8",
    )
    workflow_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    fake_response = {
        "rows": [
            {
                "sheet_row_number": 2,
                "Mail1_Greeting_Name": "Channel 1",
                "Mail1_Hook": "Hook sentence with at least six words about AI tooling.",
                "Mail1_Variant": "A1_media_kit_soft",
                "Mail1_Reason": "brand channel, soft ask",
            }
        ]
    }
    client = FakeClient([fake_response])

    monkeypatch.setattr(module, "build_llm_client", lambda api_key, base_url, timeout: client)

    argv = [
        "--input",
        str(input_csv),
        "--api-key",
        "sk-test",
        "--base-url",
        "https://example.invalid/v1",
        "--model",
        "gpt-4o-mini",
        "--batch-size",
        "1",
        "--max-workers",
        "1",
        "--audit-dir",
        str(tmp_path),
        "--dry-run",
    ]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = module.main(argv)
    summary = json.loads(buf.getvalue())
    assert rc == 0
    assert summary["selected_rows"] == 1
    assert summary["written_rows"] == 0  # dry-run must not write back
    assert Path(summary["audit_csv"]).exists()
    # CSV body untouched
    csv_text = input_csv.read_text(encoding="utf-8")
    assert "Mail1_Greeting_Name" not in csv_text  # column never appeared


def test_validation_rejects_unknown_variant():
    module = load_module()
    row = next(make_rows(1))
    target = module.TargetRow(sheet_row_number=2, row_index=0, data=row)
    workflow_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    bad = {
        "rows": [
            {
                "sheet_row_number": 2,
                "Mail1_Greeting_Name": "Channel 1",
                "Mail1_Hook": "Hook sentence with at least six words about AI tooling.",
                "Mail1_Variant": "ZZ_unknown_variant",
                "Mail1_Reason": "n/a",
            }
        ]
    }
    client = FakeClient([bad])
    with pytest.raises(ValueError):
        module.run_llm_batch(
            batch=[target],
            client=client,
            model="gpt-4o-mini",
            workflow_config=workflow_config,
            temperature=0,
        )
