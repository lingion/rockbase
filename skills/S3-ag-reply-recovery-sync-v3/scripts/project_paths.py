"""Compatibility wrapper around the V2 shared path resolver."""

from pathlib import Path

from rockbase.paths import project_root as resolve_project_root


def project_root() -> Path:
    return resolve_project_root(start=Path(__file__))


def project_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)
