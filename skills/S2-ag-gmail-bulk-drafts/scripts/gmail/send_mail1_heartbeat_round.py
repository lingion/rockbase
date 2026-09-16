#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run exactly one jittered Mail1 send round for heartbeat-driven automation."
    )
    parser.add_argument(
        "--job",
        action="append",
        required=True,
        help="Manifest/source pair in the form manifest.csv::source.csv. Repeat for multiple queues.",
    )
    parser.add_argument("--user-id", default="me", help="Gmail user id, default 'me'.")
    parser.add_argument(
        "--access-token",
        default="",
        help="Optional access token override. Default uses the Gmail OAuth token file.",
    )
    parser.add_argument(
        "--token-file",
        default="${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>",
        help="Path to the Gmail OAuth token JSON file.",
    )
    parser.add_argument("--source-status-field", default="Mail1发出状态", help="Source status field name used for writeback.")
    parser.add_argument("--source-sent-value", default="sent", help="Value written back after draft send succeeds.")
    parser.add_argument("--base-batch-size", type=int, default=15, help="Center batch size before plus/minus jitter.")
    parser.add_argument("--batch-minus", type=int, default=3, help="How many below base batch size are allowed.")
    parser.add_argument("--batch-plus", type=int, default=5, help="How many above base batch size are allowed.")
    parser.add_argument("--base-interval-seconds", type=int, default=600, help="Heartbeat cadence reference for reporting only.")
    parser.add_argument("--jitter-min-seconds", type=int, default=15, help="Minimum sleep before this round sends.")
    parser.add_argument("--jitter-max-seconds", type=int, default=45, help="Maximum sleep before this round sends.")
    parser.add_argument("--per-email-min-seconds", type=int, default=0, help="Minimum wait between each draft send.")
    parser.add_argument("--per-email-max-seconds", type=int, default=0, help="Maximum wait between each draft send.")
    parser.add_argument(
        "--max-total",
        type=int,
        default=0,
        help="Optional hard cap for this single round. Use 0 for no cap.",
    )
    parser.add_argument("--pause-flag", default="", help="If this file exists, exit without sending anything.")
    parser.add_argument("--seed", type=int, default=0, help="Optional random seed for reproducible runs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the chosen jitter and batch size without sending.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.base_batch_size <= 0:
        raise SystemExit("base-batch-size must be > 0")
    if args.batch_minus < 0 or args.batch_plus < 0:
        raise SystemExit("batch-minus and batch-plus must be >= 0")
    if args.jitter_max_seconds < args.jitter_min_seconds:
        raise SystemExit("jitter-max-seconds must be >= jitter-min-seconds")
    if args.pause_flag and Path(args.pause_flag).exists():
        print_json({"paused": True, "pause_flag": args.pause_flag})
        return

    rng = random.Random(args.seed or None)
    send_count = rng.randint(max(1, args.base_batch_size - args.batch_minus), args.base_batch_size + args.batch_plus)
    if args.max_total > 0:
        send_count = min(send_count, args.max_total)
    if send_count <= 0:
        print_json(
            {
                "event": "heartbeat_round_plan",
                "mode": "heartbeat_single_round",
                "base_interval_seconds": args.base_interval_seconds,
                "base_batch_size": args.base_batch_size,
                "batch_minus": args.batch_minus,
                "batch_plus": args.batch_plus,
                "chosen_batch_size": 0,
                "jitter_min_seconds": args.jitter_min_seconds,
                "jitter_max_seconds": args.jitter_max_seconds,
                "chosen_jitter_seconds": 0,
                "job_count": len(args.job),
                "pause_flag": args.pause_flag,
                "dry_run": args.dry_run,
                "reason": "max_total_reached",
            }
        )
        return
    jitter_seconds = rng.randint(args.jitter_min_seconds, args.jitter_max_seconds)

    payload = {
        "mode": "heartbeat_single_round",
        "base_interval_seconds": args.base_interval_seconds,
        "base_batch_size": args.base_batch_size,
        "batch_minus": args.batch_minus,
        "batch_plus": args.batch_plus,
        "chosen_batch_size": send_count,
        "jitter_min_seconds": args.jitter_min_seconds,
        "jitter_max_seconds": args.jitter_max_seconds,
        "chosen_jitter_seconds": jitter_seconds,
        "max_total": args.max_total,
        "job_count": len(args.job),
        "pause_flag": args.pause_flag,
        "dry_run": args.dry_run,
    }
    print_json({"event": "heartbeat_round_plan", **payload})

    if args.dry_run:
        return

    if jitter_seconds > 0:
        time.sleep(jitter_seconds)

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "send_draft_jittered.py"),
        "--single-run",
        "--min-batch-size",
        str(send_count),
        "--max-batch-size",
        str(send_count),
        "--min-wait-seconds",
        "0",
        "--max-wait-seconds",
        "0",
        "--per-email-min-seconds",
        str(args.per_email_min_seconds),
        "--per-email-max-seconds",
        str(args.per_email_max_seconds),
        "--initial-jitter-seconds",
        "0",
        "--window-minutes",
        "5",
        "--max-total",
        str(send_count),
        "--user-id",
        args.user_id,
        "--token-file",
        args.token_file,
        "--source-status-field",
        args.source_status_field,
        "--source-sent-value",
        args.source_sent_value,
    ]
    if args.access_token:
        cmd.extend(["--access-token", args.access_token])
    if args.pause_flag:
        cmd.extend(["--pause-flag", args.pause_flag])
    for job in args.job:
        cmd.extend(["--job", job])

    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
