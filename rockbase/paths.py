"""Portable, fail-closed path resolution for the V2 release."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path


class RockbasePathError(ValueError):
    """Raised when a configured path is missing, unresolved, or unsafe."""


_POSIX_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_WINDOWS_VARIABLE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


def _variable_names(value: str) -> set[str]:
    names = {first or second for first, second in _POSIX_VARIABLE.findall(value)}
    names.update(_WINDOWS_VARIABLE.findall(value))
    return names


def expand_path(value: str | os.PathLike[str]) -> Path:
    raw = os.fspath(value)
    missing = sorted(name for name in _variable_names(raw) if name not in os.environ)
    if missing:
        joined = ", ".join(missing)
        raise RockbasePathError(f"Unresolved environment variable(s): {joined}")

    expanded = os.path.expanduser(os.path.expandvars(raw))
    for name in _WINDOWS_VARIABLE.findall(expanded):
        expanded = expanded.replace(f"%{name}%", os.environ[name])
    return Path(expanded)


def _root_from_config(config_file: Path) -> Path | None:
    if not config_file.is_file():
        return None
    try:
        data = tomllib.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RockbasePathError(f"Cannot read Rockbase config: {config_file}: {exc}") from exc
    raw = data.get("paths", {}).get("project_root")
    if not raw:
        return None
    candidate = expand_path(raw)
    if not candidate.is_absolute():
        candidate = config_file.parent / candidate
    return candidate


def _validate_root(candidate: Path, source: str) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise RockbasePathError(f"Rockbase project root from {source} is not a directory: {resolved}")
    return resolved


def _discover_root(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "skills").is_dir():
            return candidate
    return None


def project_root(
    explicit: str | os.PathLike[str] | None = None,
    *,
    start: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the project root without creating any directory."""
    if explicit is not None:
        return _validate_root(expand_path(explicit), "explicit argument")

    env_root = os.environ.get("ROCKBASE_PROJECT_ROOT")
    if env_root:
        return _validate_root(expand_path(env_root), "ROCKBASE_PROJECT_ROOT")

    config_override = os.environ.get("ROCKBASE_CONFIG_FILE")
    config_file = expand_path(config_override) if config_override else Path.cwd() / ".rockbase" / "config.toml"
    config_root = _root_from_config(config_file)
    if config_root is not None:
        return _validate_root(config_root, str(config_file))

    starts = [expand_path(start)] if start is not None else [Path.cwd(), Path(__file__)]
    for candidate in starts:
        discovered = _discover_root(candidate)
        if discovered is not None:
            return discovered
    raise RockbasePathError(
        "Cannot locate the Rockbase project root. Pass an explicit root or set ROCKBASE_PROJECT_ROOT."
    )


def workbench_dir(root: str | os.PathLike[str] | None = None) -> Path:
    return project_root(root) / "workbench"


def agency_dir(root: str | os.PathLike[str] | None = None) -> Path:
    return project_root(root) / "Agency"


def deliverables_dir(root: str | os.PathLike[str] | None = None) -> Path:
    return project_root(root) / "deliverables"


def _resolve(value: str | os.PathLike[str], root: str | os.PathLike[str] | None) -> Path:
    candidate = expand_path(value)
    if not candidate.is_absolute():
        candidate = project_root(root) / candidate
    return candidate.resolve()


def resolve_input(
    value: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    must_exist: bool = True,
) -> Path:
    candidate = _resolve(value, root)
    if must_exist and not candidate.exists():
        raise RockbasePathError(f"Input path does not exist: {candidate}")
    return candidate


def resolve_output(
    value: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    create_parent: bool = False,
) -> Path:
    candidate = _resolve(value, root)
    if create_parent:
        candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate
