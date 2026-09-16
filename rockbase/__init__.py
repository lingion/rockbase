"""Shared compatibility helpers for the Rockbase Skills release."""

from .paths import (
    RockbasePathError,
    agency_dir,
    deliverables_dir,
    project_root,
    resolve_input,
    resolve_output,
    workbench_dir,
)

__all__ = [
    "RockbasePathError",
    "agency_dir",
    "deliverables_dir",
    "project_root",
    "resolve_input",
    "resolve_output",
    "workbench_dir",
]
