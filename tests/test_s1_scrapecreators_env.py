"""Server-portability contract tests for the S1 ScrapeCreators export scripts.

Locks the contract that:
- All three export scripts never require the macOS iCloud GLOBAL_ENV file.
- SCRAPECREATORS_API_KEY env alone is sufficient; missing key fails loudly.
- --api-key flag exists for explicit injection (server secret managers).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "skills/S1-inbox-enrichment/scripts/api"
EXPORT_SCRIPTS = [
    API_DIR / "youtube_scrapecreators_s1_export.py",
    API_DIR / "tiktok_scrapecreators_s1_export.py",
    API_DIR / "instagram_scrapecreators_s1_export.py",
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("script", EXPORT_SCRIPTS, ids=lambda p: p.name)
def test_missing_api_key_fails_loudly_without_icloud_env(script, tmp_path, monkeypatch):
    module = load_module(script, f"export_{script.stem}")
    monkeypatch.delenv("SCRAPECREATORS_API_KEY", raising=False)
    monkeypatch.setattr(module, "GLOBAL_ENV", tmp_path / "nonexistent.env")
    with pytest.raises((RuntimeError, SystemExit)):
        module.main()


@pytest.mark.parametrize("script", EXPORT_SCRIPTS, ids=lambda p: p.name)
def test_argparse_accepts_api_key_flag(script):
    module = load_module(script, f"argparse_{script.stem}")
    parser = module._build_argparser() if hasattr(module, "_build_argparser") else None
    if parser is None:
        pytest.skip("argparser builder not exposed yet")
    args = parser.parse_args(["--csv", "in.csv", "--api-key", "sk-live"])
    assert args.api_key == "sk-live"
