#!/usr/bin/env python3
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def get_x_target_defaults() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    values = _parse_env_file(env_path)
    return {
        "target_url": values.get("FEISHU_X_MASTER_TARGET_URL", ""),
        "sheet_id": values.get("FEISHU_X_MASTER_SHEET_ID", ""),
        "sheet_title": values.get("FEISHU_X_MASTER_SHEET_TITLE", ""),
        "env_path": str(env_path),
    }
