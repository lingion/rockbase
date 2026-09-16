#!/usr/bin/env python3
"""
Apply manual DM outcome notes back to the Rockbase S2 cold DM CSV.

This helper only updates the `备注` column and always creates a physical backup first.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import read_csv_rows, write_csv_rows


def parse_updates(raw_values: List[str]) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise ValueError(f"invalid update {raw!r}, expected @handle=备注")
        handle, note = raw.split("=", 1)
        key = handle.strip()
        value = note.strip()
        if not key or not value:
            raise ValueError(f"invalid update {raw!r}, expected non-empty handle and note")
        updates[key] = value
    return updates


def make_backup(input_path: Path, backup_root: Path) -> Path:
    stamp_date = datetime.now().strftime("%Y-%m-%d")
    stamp_time = datetime.now().strftime("%H%M%S")
    backup_dir = backup_root / stamp_date
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{input_path.name}_bak_{stamp_time}.csv"
    shutil.copy2(input_path, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply manual DM outcome notes back to the source CSV.")
    parser.add_argument("--input", required=True, help="Source CSV path to update in place.")
    parser.add_argument("--set", nargs="+", required=True, help="Updates in the form @handle=备注")
    parser.add_argument("--backup-root", default="Agency/list-bak", help="Backup root directory. Default: Agency/list-bak")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    backup_root = Path(args.backup_root).expanduser().resolve()
    updates = parse_updates(args.set)

    backup_path = make_backup(input_path, backup_root)
    fieldnames, rows = read_csv_rows(input_path)

    if "备注" not in fieldnames:
        fieldnames = list(fieldnames) + ["备注"]
        for row in rows:
            row.setdefault("备注", "")

    seen = set()
    for row in rows:
        handle = row.get("账号ID", "").strip()
        if handle in updates:
            row["备注"] = updates[handle]
            seen.add(handle)

    missing = sorted(set(updates) - seen)
    if missing:
        raise SystemExit(f"missing rows: {missing}")

    write_csv_rows(input_path, fieldnames, rows)
    print(
        {
            "input": str(input_path),
            "backup": str(backup_path),
            "updated": updates,
        }
    )


if __name__ == "__main__":
    main()
