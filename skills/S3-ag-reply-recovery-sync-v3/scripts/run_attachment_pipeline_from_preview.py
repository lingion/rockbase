#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full-thread fetch + attachment extraction for threads listed in a recovery preview CSV."
    )
    parser.add_argument("--master", required=True, help="Path to the V3 replied master CSV.")
    parser.add_argument("--preview-csv", required=True, help="Path to recent_reply_window_preview.csv or a combined preview CSV.")
    parser.add_argument("--output-dir", required=True, help="Output directory for thread fetch and attachment extraction.")
    parser.add_argument("--token", default="", help="Optional Gmail OAuth token path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max thread count. 0 means all unique threads in preview.")
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    args = parse_args()
    preview_csv = Path(args.preview_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(preview_csv)
    thread_ids: List[str] = []
    seen = set()
    for row in rows:
        thread_id = (row.get("Reply_Thread_ID") or row.get("thread_id") or "").strip()
        if not thread_id or thread_id in seen:
            continue
        seen.add(thread_id)
        thread_ids.append(thread_id)
    if args.limit and args.limit > 0:
        thread_ids = thread_ids[: args.limit]

    thread_ids_path = output_dir / "thread_ids.json"
    thread_ids_path.write_text(json.dumps(thread_ids, ensure_ascii=False, indent=2), encoding="utf-8")

    fetch_dir = output_dir / "thread_fetch"
    extract_dir = output_dir / "attachment_extract"

    fetch_cmd = [
        "python3",
        str(Path(__file__).with_name("fetch_reply_threads.py")),
        "--master",
        args.master,
        "--thread-ids-json",
        str(thread_ids_path),
        "--output-dir",
        str(fetch_dir),
        "--limit",
        str(len(thread_ids)),
    ]
    if args.token:
        fetch_cmd.extend(["--token", args.token])
    fetch_proc = subprocess.run(fetch_cmd, capture_output=True, text=True)

    attachments_csv = fetch_dir / f"reply_batch_attachments_first{len(thread_ids)}.csv"
    extract_proc = None
    if attachments_csv.exists() and attachments_csv.stat().st_size > 0:
        extract_cmd = [
            "python3",
            str(Path(__file__).with_name("extract_reply_attachments.py")),
            "--attachments-csv",
            str(attachments_csv),
            "--output-dir",
            str(extract_dir),
        ]
        if args.token:
            extract_cmd.extend(["--token", args.token])
        extract_proc = subprocess.run(extract_cmd, capture_output=True, text=True)

    summary = {
        "preview_csv": str(preview_csv.resolve()),
        "threads_requested": len(thread_ids),
        "thread_ids_json": str(thread_ids_path.resolve()),
        "fetch_returncode": fetch_proc.returncode,
        "fetch_stdout": fetch_proc.stdout.strip(),
        "fetch_stderr": fetch_proc.stderr.strip(),
        "fetch_dir": str(fetch_dir.resolve()),
        "attachments_csv": str(attachments_csv.resolve()) if attachments_csv.exists() else "",
        "extract_returncode": extract_proc.returncode if extract_proc is not None else None,
        "extract_stdout": extract_proc.stdout.strip() if extract_proc is not None else "",
        "extract_stderr": extract_proc.stderr.strip() if extract_proc is not None else "",
        "extract_dir": str(extract_dir.resolve()) if extract_proc is not None else "",
    }
    summary_path = output_dir / "attachment_pipeline_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
