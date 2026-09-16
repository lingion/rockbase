from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from x_kol_discovery.config import ScweetCookieProfile, SearchQuery


_ENV_REF_RE = re.compile(r"\$\{([^}]+)\}")


def load_simple_env(env_path: Path) -> dict[str, str]:
    def expand_refs(raw_value: str, current: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            return current.get(key, match.group(0))
        return _ENV_REF_RE.sub(replace, raw_value)

    def unquote(value: str) -> str:
        text = value.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            return text[1:-1]
        return text

    data: dict[str, str] = {}
    if not env_path.exists():
        raise FileNotFoundError(f"Missing env file: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = unquote(expand_refs(value.strip(), data))
    return data


def safe_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def ensure_project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "workbench").exists():
        return cwd
    for parent in Path(__file__).resolve().parents:
        if (parent / "workbench").exists():
            return parent
    raise FileNotFoundError("Could not locate project root containing workbench/")


def tests_dir() -> Path:
    return skill_dir() / "tests"


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_env_path() -> Path:
    override = os.environ.get("X_KOL_SKILL_ENV_PATH") or os.environ.get("SKILL_ENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return skill_dir() / ".env"


def query_library_path() -> Path:
    return skill_dir() / "QUERY_LIBRARY.md"


def ensure_query_names_exist_in_library(search_queries: list[SearchQuery]) -> None:
    path = query_library_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing query library: {path}")
    text = path.read_text(encoding="utf-8")
    missing: list[str] = []
    for search_query in search_queries:
        needle = f"`{safe_text(search_query.name)}`"
        if needle not in text:
            missing.append(search_query.name)
    if missing:
        missing_text = ", ".join(f"`{name}`" for name in missing)
        raise ValueError(
            "Query name preflight failed. Add every new query name to QUERY_LIBRARY.md Part 2 before running. "
            f"Missing names: {missing_text}"
        )


def load_skill_env() -> dict[str, str]:
    return load_simple_env(skill_env_path())


def _profile_suffix(profile_name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(profile_name or "").strip().upper())


def _lookup_cookie_pair(env: dict[str, str], profile_name: str) -> tuple[str, str]:
    normalized = str(profile_name or "").strip()
    if not normalized or normalized.lower() in {"primary", "default", "steveding150"}:
        return (
            env.get("X_AUTH_TOKEN") or env.get("AUTH_TOKEN") or "",
            env.get("X_CT0") or env.get("CT0") or "",
        )
    suffix = _profile_suffix(normalized)
    return (
        env.get(f"X_AUTH_TOKEN_{suffix}") or env.get(f"AUTH_TOKEN_{suffix}") or "",
        env.get(f"X_CT0_{suffix}") or env.get(f"CT0_{suffix}") or "",
    )


def materialize_scweet_env_for_profile(env: dict[str, str], profile_name: str) -> Path:
    auth_token, ct0 = _lookup_cookie_pair(env, profile_name)
    if not auth_token:
        raise KeyError(f"Missing auth token for Scweet cookie profile: {profile_name}")
    temp_root = Path(tempfile.gettempdir()) / "x_kol_scweet_envs"
    temp_root.mkdir(parents=True, exist_ok=True)
    env_path = temp_root / f"{_profile_suffix(profile_name or 'primary').lower()}.env"
    merged = dict(env)
    merged["AUTH_TOKEN"] = auth_token
    merged["X_AUTH_TOKEN"] = auth_token
    if ct0:
        merged["CT0"] = ct0
        merged["X_CT0"] = ct0
    env_path.write_text("\n".join(f"{key}={value}" for key, value in merged.items()) + "\n", encoding="utf-8")
    return env_path


def resolve_scweet_cookie_profiles(
    env: dict[str, str],
    preferred_profile: str = "",
) -> list[ScweetCookieProfile]:
    primary_profile = str(env.get("X_COOKIE_PROFILE_PRIMARY") or "steveding150").strip() or "steveding150"
    fallback_raw = str(env.get("X_COOKIE_PROFILE_FALLBACKS") or "").strip()
    ordered_names: list[str] = [primary_profile]
    if fallback_raw:
        for item in fallback_raw.split(","):
            candidate = item.strip()
            if candidate and candidate not in ordered_names:
                ordered_names.append(candidate)
    preferred = str(preferred_profile or "").strip()
    if preferred:
        ordered_names = [preferred] + [name for name in ordered_names if name != preferred]

    profiles: list[ScweetCookieProfile] = []
    seen: set[tuple[str, str]] = set()
    for profile_name in ordered_names:
        auth_token, ct0 = _lookup_cookie_pair(env, profile_name)
        if not auth_token:
            continue
        fingerprint = (auth_token, ct0)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        profiles.append(
            ScweetCookieProfile(
                name=profile_name,
                auth_token=auth_token,
                ct0=ct0,
                env_path=str(materialize_scweet_env_for_profile(env, profile_name)),
            )
        )
    return profiles


def workbench_dir(run_date: str) -> Path:
    out_dir = ensure_project_root() / "workbench" / run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def agency_list_master_dir() -> Path:
    # X skill keeps its discovery master inside the skill bundle to avoid
    # mixing platform-specific dedupe state into the project-level list-master.
    out_dir = skill_dir() / "Agency" / "list-master"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def backup_csv_if_exists(path: Path, run_date: str) -> Path | None:
    if not path.exists():
        return None
    backup_dir = ensure_project_root() / "Agency" / "list-bak" / run_date
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    dest = backup_dir / f"{path.name}_bak_{stamp}.csv"
    shutil.copy2(path, dest)
    return dest


def scweet_bin() -> str:
    vendored = tests_dir() / ".venv" / "bin" / "scweet"
    if vendored.exists():
        return str(vendored)
    runtime = tests_dir() / ".runtime311" / "bin" / "scweet"
    if runtime.exists():
        return str(runtime)
    candidate = Path(sys.executable).with_name("scweet")
    if candidate.exists():
        return str(candidate)
    return "scweet"
