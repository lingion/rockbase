from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from load_env import default_workbench_dir


def backup_csv(csv_path: Path) -> Path:
    base_dir = csv_path.parent.parent / "list-bak" / datetime.now().strftime("%Y-%m-%d")
    base_dir.mkdir(parents=True, exist_ok=True)
    backup = base_dir / f"{csv_path.name}_bak_{datetime.now().strftime('%H%M%S')}.csv"
    shutil.copy2(csv_path, backup)
    return backup


def dedupe_csv(csv_path: Path, key_fields: list[str], report_path: Path) -> dict[str, int]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    seen: dict[tuple[str, ...], dict[str, str]] = {}
    dropped = 0
    for row in rows:
        key = tuple(str(row.get(field, "") or "").strip().lower() for field in key_fields)
        if not any(key):
            suffix = str(len(seen))
            key = (*key, suffix)
        current = seen.get(key)
        if current is None:
            seen[key] = row
            continue
        current_score = sum(1 for v in current.values() if str(v or "").strip())
        row_score = sum(1 for v in row.values() if str(v or "").strip())
        if row_score > current_score:
            seen[key] = row
        dropped += 1

    deduped = list(seen.values())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped)

    report = {
        "before": len(rows),
        "after": len(deduped),
        "dropped": dropped,
        "keys": key_fields,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_subprocess(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True)


def clear_stale_fetch_processes() -> list[dict[str, object]]:
    current_pid = os.getpid()
    output = subprocess.check_output(["ps", "-o", "pid=,command=", "-ax"], text=True)
    killed: list[dict[str, object]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, command = line.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if "fetch_x_user_tweets.py" not in command:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append({"pid": pid, "command": command})
        except ProcessLookupError:
            continue
    return killed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the standard Layer 2 workflow: backup -> dedupe -> fetch -> enrich -> finalize"
    )
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--workbench-date", default="")
    parser.add_argument("--handle-col", default="账号ID")
    parser.add_argument("--mode", choices=["preview", "apply"], default="apply")
    parser.add_argument("--skip-dedupe", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-enrich", action="store_true")
    parser.add_argument("--skip-finalize", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=10)
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    skill_dir = Path(__file__).resolve().parent
    root_dir = skill_dir.parent.parent.parent.parent
    out_dir = default_workbench_dir(args.workbench_date or None)
    out_dir.mkdir(parents=True, exist_ok=True)

    backup = backup_csv(csv_path)
    summary: dict[str, object] = {"backup": str(backup)}

    if not args.skip_dedupe:
        dedupe_report = out_dir / f"{csv_path.stem}_dedupe_report.json"
        summary["dedupe"] = dedupe_csv(csv_path, ["账号ID", "账号链接"], dedupe_report)
        summary["dedupe_report"] = str(dedupe_report)

    if not args.skip_fetch:
        killed = clear_stale_fetch_processes()
        summary["stale_fetch_cleanup"] = {"count": len(killed), "killed": killed}
        run_subprocess(
            [
                "python3",
                str(skill_dir / "fetch_x_user_tweets.py"),
                "--csv",
                str(csv_path),
                "--handle-col",
                args.handle_col,
                "--batch-name",
                args.batch_name,
                "--workbench-date",
                args.workbench_date,
                "--chunk-size",
                str(args.chunk_size),
            ],
            root_dir,
        )
        summary["fetch"] = {"status": "completed", "chunk_size": args.chunk_size}

    if not args.skip_enrich:
        run_subprocess(
            [
                "python3",
                str(skill_dir / "enrich_x_csv_layer2.py"),
                "--csv",
                str(csv_path),
                "--mode",
                args.mode,
                "--workbench-date",
                args.workbench_date,
            ],
            root_dir,
        )
        summary["enrich"] = args.mode

    if not args.skip_finalize:
        run_subprocess(
            [
                "python3",
                str(skill_dir / "finalize_x_csv_layer2.py"),
                "--csv",
                str(csv_path),
                "--mode",
                args.mode,
                "--workbench-date",
                args.workbench_date,
            ],
            root_dir,
        )
        summary["finalize"] = args.mode

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
