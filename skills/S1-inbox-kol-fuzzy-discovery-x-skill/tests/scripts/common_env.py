from __future__ import annotations

from pathlib import Path


def load_simple_env(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists():
        raise FileNotFoundError(f"Missing env file: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def tests_root() -> Path:
    return Path(__file__).resolve().parents[1]
