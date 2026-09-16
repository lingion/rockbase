from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x_kol_discovery.config import Layer1RunConfig, SearchQuery


def _run_json_command(cmd: list[str]) -> list[dict[str, Any]]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd[:-1])}\n{proc.stderr[:1500]}")
    if not proc.stdout.strip():
        return []
    payload = json.loads(proc.stdout)
    if not isinstance(payload, list):
        raise RuntimeError(f"Expected list JSON from command: {' '.join(cmd[:-1])}")
    return payload


def _redacted_command(cmd: list[str], auth_token: str, ct0: str) -> str:
    redacted: list[str] = []
    for part in cmd:
        if part == auth_token:
            redacted.append("[REDACTED_AUTH_TOKEN]")
        elif part == ct0:
            redacted.append("[REDACTED_CT0]")
        else:
            redacted.append(part)
    return " ".join(redacted)


class BirdCliAdapter:
    def __init__(self, auth_token: str, ct0: str, language: str = "en") -> None:
        self.auth_token = auth_token
        self.ct0 = ct0
        self.language = language

    def search(self, search_query: SearchQuery, config: Layer1RunConfig, db_path: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cmd = [
            "bird",
            "--auth-token",
            self.auth_token,
            "--ct0",
            self.ct0,
            "search",
            search_query.query,
            "-n",
            str(search_query.limit),
            "--json-full",
        ]
        started = datetime.now(timezone.utc).isoformat()
        rows = _run_json_command(cmd)
        meta = {
            "query_name": search_query.name,
            "query": search_query.query,
            "command": _redacted_command(cmd, self.auth_token, self.ct0),
            "started_utc": started,
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "result_count": len(rows),
            "provider": "bird_cli",
        }
        return rows, meta
