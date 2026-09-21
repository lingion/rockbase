from __future__ import annotations

import sys
from pathlib import Path

from scripts.run_mail_loop import build_mail_loop_stages


ROOT = Path(__file__).resolve().parents[1]


def test_mail_loop_orders_send_fetch_then_two_syncs(tmp_path):
    stages = build_mail_loop_stages(
        batch_csv=tmp_path / "mail1.csv",
        config=tmp_path / "config.toml",
        master=tmp_path / "master.csv",
        state_path=tmp_path / "run.json",
        fetch_out=tmp_path / "replies",
    )

    assert [stage.name for stage in stages] == [
        "mailkit_send",
        "fetch_replies",
        "master_sync_sent",
        "master_sync_replies",
    ]
    assert "--execute" not in stages[0].command
    assert "--execute" not in stages[2].command
    assert "--execute" not in stages[3].command


def test_mail_loop_execution_flags_are_independent(tmp_path):
    stages = build_mail_loop_stages(
        batch_csv=tmp_path / "mail1.csv",
        config=tmp_path / "config.toml",
        master=tmp_path / "master.csv",
        state_path=tmp_path / "run.json",
        fetch_out=tmp_path / "replies",
        execute_send=True,
        execute_sync=True,
    )

    assert "--execute" in stages[0].command
    assert "--execute" in stages[2].command
    assert "--execute" in stages[3].command
    assert "--from-csv" in stages[3].command
    assert stages[3].command[stages[3].command.index("--from-csv") + 1].endswith(".csv")


def test_mail_loop_uses_module_invocations_from_repo_root(tmp_path):
    stages = build_mail_loop_stages(
        batch_csv=tmp_path / "mail1.csv",
        config=tmp_path / "config.toml",
        master=tmp_path / "master.csv",
        state_path=tmp_path / "run.json",
        fetch_out=tmp_path / "replies",
    )

    assert all(stage.command[:2] == (sys.executable, "-m") for stage in stages)
    assert all(
        str(ROOT) not in argument
        for stage in stages
        for argument in stage.command[2:]
    )
