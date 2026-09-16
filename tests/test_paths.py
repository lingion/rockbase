from __future__ import annotations

import os
from pathlib import Path

import pytest

from rockbase.paths import RockbasePathError, project_root, resolve_input, resolve_output


def test_environment_root_supports_spaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "Rockbase Project With Spaces"
    root.mkdir()
    monkeypatch.setenv("ROCKBASE_PROJECT_ROOT", str(root))
    assert project_root() == root.resolve()


def test_unresolved_variable_fails_without_creating_literal_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ROCKBASE_MISSING_TEST", raising=False)
    with pytest.raises(RockbasePathError, match="ROCKBASE_MISSING_TEST"):
        resolve_output("${ROCKBASE_MISSING_TEST}/result.csv", root=tmp_path)
    assert not (tmp_path / "${ROCKBASE_MISSING_TEST}").exists()


def test_input_is_project_relative_and_fail_closed(tmp_path: Path) -> None:
    sample = tmp_path / "inputs" / "sample.csv"
    sample.parent.mkdir()
    sample.write_text("id\n1\n", encoding="utf-8")
    assert resolve_input("inputs/sample.csv", root=tmp_path) == sample.resolve()
    with pytest.raises(RockbasePathError, match="does not exist"):
        resolve_input("inputs/missing.csv", root=tmp_path)


def test_output_parent_is_not_created_unless_requested(tmp_path: Path) -> None:
    output = resolve_output("new/result.csv", root=tmp_path)
    assert not output.parent.exists()
    created = resolve_output("new/result.csv", root=tmp_path, create_parent=True)
    assert created == output
    assert output.parent.is_dir()


def test_config_root_is_resolved_relative_to_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "portable-project"
    project.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = config_dir / "rockbase.toml"
    config.write_text('[paths]\nproject_root = "../portable-project"\n', encoding="utf-8")
    monkeypatch.delenv("ROCKBASE_PROJECT_ROOT", raising=False)
    monkeypatch.setenv("ROCKBASE_CONFIG_FILE", os.fspath(config))
    assert project_root() == project.resolve()
