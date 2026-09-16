from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_skill_env() -> Path | None:
    candidates = [
        skill_root() / ".env",
        Path(
            "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env"
        ),
    ]
    for path in candidates:
        if path.exists():
            load_dotenv(path, override=True)
            return path
    load_dotenv(override=True)
    return None


def require_api_key() -> str:
    key = os.getenv("SCRAPECREATORS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SCRAPECREATORS_API_KEY 未配置。请检查 skill 内 .env 软链接。")
    return key


def default_workbench_dir(today: str | None = None) -> Path:
    root = Path(
        "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench"
    )
    if today:
        return root / today
    from datetime import datetime

    return root / datetime.now().strftime("%Y-%m-%d")
