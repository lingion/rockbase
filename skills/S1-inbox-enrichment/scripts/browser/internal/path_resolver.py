from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rockbase.paths import project_root as resolve_project_root
from rockbase.paths import resolve_input, workbench_dir


def project_root() -> Path:
    return resolve_project_root(start=Path(__file__))


def workbench_day_dir() -> Path:
    day_dir = workbench_dir(project_root()) / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def resolve_csv_path(raw_path: str) -> Path:
    return resolve_input(raw_path, root=project_root(), must_exist=False)


def build_report_dir(csv_path: Path) -> Path:
    report_dir = workbench_day_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def build_test_copy_path(csv_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return workbench_day_dir() / f"{csv_path.stem}__enrichment_test__{stamp}{csv_path.suffix}"
