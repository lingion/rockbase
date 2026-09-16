#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run segmented V3 reply recovery capture over a larger time window.")
    parser.add_argument("--master", required=True, help="Path to the V3 replied master CSV.")
    parser.add_argument("--hub-root", required=True, help="Hub V3 root.")
    parser.add_argument("--output-dir", required=True, help="Directory for segmented run outputs.")
    parser.add_argument("--total-hours", type=int, default=24, help="Total lookback window in hours.")
    parser.add_argument("--segment-hours", type=int, default=6, help="Hours per segment.")
    parser.add_argument("--token", default="", help="Optional Gmail OAuth token path.")
    return parser.parse_args()


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).with_name("capture_replies.py")
    now = datetime.now(timezone.utc)
    segments = []
    aggregate_preview: List[Dict[str, str]] = []
    aggregate_audit: List[Dict[str, str]] = []

    total_segments = max(1, (args.total_hours + args.segment_hours - 1) // args.segment_hours)
    for idx in range(total_segments):
        seg_end = now - timedelta(hours=idx * args.segment_hours)
        seg_start = seg_end - timedelta(hours=args.segment_hours)
        segment_dir = output_dir / f"segment_{idx + 1:02d}"
        cmd = [
            "python3",
            str(script_path),
            "--master",
            args.master,
            "--hub-root",
            args.hub_root,
            "--output-dir",
            str(segment_dir),
            "--ignore-checkpoint",
            "--after-epoch",
            str(int(seg_start.timestamp())),
            "--before-epoch",
            str(int(seg_end.timestamp())),
        ]
        if args.token:
            cmd.extend(["--token", args.token])
        proc = subprocess.run(cmd, capture_output=True, text=True)
        segment_record: Dict[str, object] = {
            "segment_index": idx + 1,
            "after_epoch": int(seg_start.timestamp()),
            "before_epoch": int(seg_end.timestamp()),
            "output_dir": str(segment_dir),
            "returncode": proc.returncode,
        }
        if proc.stdout.strip():
            try:
                segment_record["summary"] = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                segment_record["stdout"] = proc.stdout.strip()
        if proc.stderr.strip():
            segment_record["stderr"] = proc.stderr.strip()
        segments.append(segment_record)

        preview_path = segment_dir / "recent_reply_window_preview.csv"
        if preview_path.exists():
            with preview_path.open("r", encoding="utf-8-sig", newline="") as fh:
                aggregate_preview.extend(list(csv.DictReader(fh)))
        audit_path = segment_dir / "recent_reply_window_audit.csv"
        if audit_path.exists():
            with audit_path.open("r", encoding="utf-8-sig", newline="") as fh:
                aggregate_audit.extend(list(csv.DictReader(fh)))

    summary_path = output_dir / "segmented_capture_summary.json"
    summary_path.write_text(json.dumps({"segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")

    if aggregate_preview:
        write_csv(
            output_dir / "segmented_capture_preview_combined.csv",
            aggregate_preview,
            list(aggregate_preview[0].keys()),
        )
    if aggregate_audit:
        write_csv(
            output_dir / "segmented_capture_audit_combined.csv",
            aggregate_audit,
            list(aggregate_audit[0].keys()),
        )

    final_summary = {
        "segments_requested": total_segments,
        "segments_completed": sum(1 for segment in segments if int(segment.get("returncode", 1)) == 0),
        "combined_preview_rows": len(aggregate_preview),
        "combined_audit_rows": len(aggregate_audit),
        "summary_json": str(summary_path.resolve()),
        "combined_preview_csv": str((output_dir / "segmented_capture_preview_combined.csv").resolve()) if aggregate_preview else "",
        "combined_audit_csv": str((output_dir / "segmented_capture_audit_combined.csv").resolve()) if aggregate_audit else "",
    }
    print(json.dumps(final_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
