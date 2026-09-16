from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x_kol_discovery.config import Layer1RunConfig, ScweetCookieProfile, SearchQuery
from x_kol_discovery.io_utils import scweet_bin, skill_env_path


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


def _redacted_command(cmd: list[str], auth_token: str) -> str:
    return " ".join(part if part != auth_token else "[REDACTED_TOKEN]" for part in cmd)


class ScweetCliAdapter:
    def __init__(self, auth_token: str, language: str = "en", profiles: list[ScweetCookieProfile] | None = None) -> None:
        self.auth_token = auth_token
        self.language = language
        self.env_path = skill_env_path()
        self.profiles = profiles or []

    def _auth_args(self, profile: ScweetCookieProfile | None = None) -> list[str]:
        if profile and profile.env_path:
            return ["--env-file", str(profile.env_path)]
        if self.env_path.exists():
            return ["--env-file", str(self.env_path)]
        return ["--auth-token", self.auth_token]

    def _profile_chain(self) -> list[ScweetCookieProfile | None]:
        return list(self.profiles) if self.profiles else [None]

    @staticmethod
    def _profile_name(profile: ScweetCookieProfile | None) -> str:
        return profile.name if profile else "default"

    def search(self, search_query: SearchQuery, config: Layer1RunConfig, db_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        started = datetime.now(timezone.utc).isoformat()
        attempts: list[dict[str, Any]] = []
        last_error = ""
        for profile in self._profile_chain():
            cmd = [
                scweet_bin(),
                *self._auth_args(profile),
                "--db-path",
                str(db_path),
                "search",
                search_query.query,
                "--lang",
                config.language,
                "--since",
                config.since,
                "--until",
                config.until,
                "--limit",
                str(search_query.limit),
                "--pretty",
            ]
            try:
                rows = _run_json_command(cmd)
                meta = {
                    "query_name": search_query.name,
                    "query": search_query.query,
                    "command": _redacted_command(cmd, profile.auth_token if profile else self.auth_token),
                    "started_utc": started,
                    "ended_utc": datetime.now(timezone.utc).isoformat(),
                    "result_count": len(rows),
                    "provider": "scweet",
                    "cookie_profile": self._profile_name(profile),
                    "fallback_attempts": attempts,
                }
                return rows, meta
            except Exception as exc:
                last_error = str(exc)
                attempts.append(
                    {
                        "cookie_profile": self._profile_name(profile),
                        "command": _redacted_command(cmd, profile.auth_token if profile else self.auth_token),
                        "error": last_error[:1000],
                    }
                )
        raise RuntimeError(f"Scweet search failed across all cookie profiles. Last error: {last_error[:1000]}")

    def fetch_user_info(self, usernames: list[str], config: Layer1RunConfig, db_path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        profiles: dict[str, dict[str, Any]] = {}
        batch_meta: list[dict[str, Any]] = []
        for index in range(0, len(usernames), config.user_info_batch_size):
            chunk = usernames[index : index + config.user_info_batch_size]
            cmd = [
                scweet_bin(),
                *self._auth_args(),
                "--db-path",
                str(db_path),
                "user-info",
                *chunk,
                "--pretty",
            ]
            started = datetime.now(timezone.utc).isoformat()
            rows = _run_json_command(cmd)
            for row in rows:
                username = str(row.get("username") or "").strip().lower()
                if username:
                    profiles[username] = row
            batch_record = {
                "user_count": len(chunk),
                "resolved_count": len(rows),
                "usernames": chunk,
                "command": _redacted_command(cmd, self.auth_token),
                "provider": "scweet",
                "started_utc": started,
                "ended_utc": datetime.now(timezone.utc).isoformat(),
            }
            batch_meta.append(batch_record)
            if config.user_info_retry_single_on_empty_batch and len(chunk) > 1 and not rows:
                single_results = 0
                single_attempts: list[dict[str, Any]] = []
                for username in chunk:
                    single_cmd = [
                        scweet_bin(),
                        *self._auth_args(),
                        "--db-path",
                        str(db_path),
                        "user-info",
                        username,
                        "--pretty",
                    ]
                    single_started = datetime.now(timezone.utc).isoformat()
                    try:
                        single_rows = _run_json_command(single_cmd)
                    except Exception as exc:
                        single_rows = []
                        single_attempts.append(
                            {
                                "username": username,
                                "resolved_count": 0,
                                "command": _redacted_command(single_cmd, self.auth_token),
                                "provider": "scweet",
                                "started_utc": single_started,
                                "ended_utc": datetime.now(timezone.utc).isoformat(),
                                "error": str(exc)[:1000],
                            }
                        )
                        continue
                    for row in single_rows:
                        resolved_username = str(row.get("username") or "").strip().lower()
                        if resolved_username:
                            profiles[resolved_username] = row
                    single_results += len(single_rows)
                    single_attempts.append(
                        {
                            "username": username,
                            "resolved_count": len(single_rows),
                            "command": _redacted_command(single_cmd, self.auth_token),
                            "provider": "scweet",
                            "started_utc": single_started,
                            "ended_utc": datetime.now(timezone.utc).isoformat(),
                            "error": "",
                        }
                    )
                    if config.user_info_batch_pause_seconds > 0:
                        time.sleep(config.user_info_batch_pause_seconds)
                batch_record["single_retry_attempted"] = True
                batch_record["single_retry_resolved_count"] = single_results
                batch_record["single_retry_attempts"] = single_attempts
            else:
                batch_record["single_retry_attempted"] = False
            if config.user_info_batch_pause_seconds > 0:
                time.sleep(config.user_info_batch_pause_seconds)
        return profiles, batch_meta
