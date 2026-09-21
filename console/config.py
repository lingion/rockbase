"""Console configuration sourced from environment variables.

Default bind is loopback. The only non-loopback escape hatch is
``ROCKBASE_CONSOLE_ALLOW_REMOTE=1``, applied at parse time; validation
errors never echo environment content.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _resolve_repo_root() -> Path:
    """Walk up from this file until we find a directory that looks like the repo."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "rockbase").is_dir() or (candidate / "scripts").is_dir():
            return candidate
    return here.parents[1]


@dataclass(frozen=True)
class ConsoleConfig:
    host: str
    port: int
    repo_root: Path
    runs_dir: Path
    users_file: Path
    session_file: Path
    approval_dir: Path
    audit_file: Path
    cookie_secure: bool
    session_ttl_seconds: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ConsoleConfig":
        env = dict(os.environ if environ is None else environ)

        host = env.get("ROCKBASE_CONSOLE_HOST", "127.0.0.1")
        port_raw = env.get("ROCKBASE_CONSOLE_PORT", "8790")
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"ROCKBASE_CONSOLE_PORT must be an integer") from exc
        if not (1 <= port <= 65535):
            raise ValueError("ROCKBASE_CONSOLE_PORT must be in [1, 65535]")

        if host not in _LOOPBACK_HOSTS and env.get("ROCKBASE_CONSOLE_ALLOW_REMOTE") != "1":
            raise ValueError(
                "ROCKBASE_CONSOLE_HOST must be loopback unless "
                "ROCKBASE_CONSOLE_ALLOW_REMOTE=1"
            )

        ttl_raw = env.get("ROCKBASE_CONSOLE_SESSION_TTL_SECONDS", str(8 * 3600))
        try:
            ttl = int(ttl_raw)
        except ValueError as exc:
            raise ValueError("ROCKBASE_CONSOLE_SESSION_TTL_SECONDS must be an integer") from exc
        if ttl <= 0:
            raise ValueError("ROCKBASE_CONSOLE_SESSION_TTL_SECONDS must be positive")

        repo_root = Path(env.get("ROCKBASE_CONSOLE_REPO_ROOT", _resolve_repo_root()))
        base = Path(env.get("ROCKBASE_CONSOLE_BASE_DIR", "/etc/rockbase/console"))

        cookie_secure_raw = env.get("ROCKBASE_CONSOLE_COOKIE_SECURE", "").lower()
        cookie_secure = cookie_secure_raw in {"1", "true", "yes"}

        runs_dir_raw = env.get("ROCKBASE_CONSOLE_RUNS_DIR")
        runs_dir = Path(runs_dir_raw) if runs_dir_raw else base / "state"

        return cls(
            host=host,
            port=port,
            repo_root=repo_root,
            runs_dir=runs_dir,
            users_file=base / "users.toml",
            session_file=base / "sessions.json",
            approval_dir=base / "approvals",
            audit_file=base / "audit.jsonl",
            cookie_secure=cookie_secure,
            session_ttl_seconds=ttl,
        )