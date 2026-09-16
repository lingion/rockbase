from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/S1-inbox-enrichment/scripts/browser/internal/path_resolver.py"


def load_module():
    spec = importlib.util.spec_from_file_location("s1_path_resolver", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_s1_resolves_input_from_external_working_directory(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "receiver project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("ROCKBASE_PROJECT_ROOT", os.fspath(project))

    module = load_module()
    assert module.resolve_csv_path("inputs/creators.csv") == project / "inputs/creators.csv"
    assert not (project / "inputs").exists()
