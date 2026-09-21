from __future__ import annotations

from pathlib import Path

from scripts.run_full_pipeline import build_full_pipeline_stages


def names(stages):
    return [stage.name for stage in stages]


def test_full_pipeline_defaults_to_s2_mail_loop_only(tmp_path):
    stages = build_full_pipeline_stages(
        csv_path=tmp_path / "master.csv",
        config=tmp_path / "config.toml",
        state_path=tmp_path / "state.json",
        fetch_out=tmp_path / "replies",
        date="2026-09-21",
    )

    assert names(stages) == [
        "s2_mail1_generate",
        "mailkit_send",
        "fetch_replies",
        "master_sync_sent",
        "master_sync_replies",
    ]
    assert all("--execute" not in stage.command for stage in stages)


def test_full_pipeline_optional_s1_and_s5_have_explicit_write_gates(tmp_path):
    stages = build_full_pipeline_stages(
        csv_path=tmp_path / "master.csv",
        config=tmp_path / "config.toml",
        state_path=tmp_path / "state.json",
        fetch_out=tmp_path / "replies",
        date="2026-09-21",
        platform="youtube",
        s1_rows="2,3",
        with_s1=True,
        s1_apply=True,
        with_s5=True,
        image_dir=tmp_path / "images",
        s5_engine="llm",
        s5_write=True,
        execute_send=True,
        execute_sync=True,
    )

    assert names(stages)[:3] == ["s1_export", "s1_apply", "s2_mail1_generate"]
    assert "--mode" in stages[1].command
    assert stages[1].command[stages[1].command.index("--mode") + 1] == "apply"
    s5 = next(stage for stage in stages if stage.name == "s5_ocr")
    assert "--ocr-engine" in s5.command
    assert "--dry-run" not in s5.command
    assert "--execute" in next(stage for stage in stages if stage.name == "mailkit_send").command


def test_full_pipeline_s1_apply_is_preview_by_default(tmp_path):
    stages = build_full_pipeline_stages(
        csv_path=tmp_path / "master.csv",
        config=tmp_path / "config.toml",
        state_path=tmp_path / "state.json",
        fetch_out=tmp_path / "replies",
        date="2026-09-21",
        with_s1=True,
        s1_rows="2",
        s1_apply=False,
    )

    apply = next(stage for stage in stages if stage.name == "s1_apply")
    assert apply.command[apply.command.index("--mode") + 1] == "preview"
