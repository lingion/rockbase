#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import build_gmail_config, gmail_get_profile, gmail_list_drafts, gmail_send_draft, now_iso, print_json


def emit(event: str, payload: dict) -> None:
    print_json({"event": event, **payload})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Directly send existing Gmail drafts in jittered batches from the draft box."
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
    parser.add_argument("--min-batch-size", type=int, default=8, help="Minimum drafts to send per round.")
    parser.add_argument("--max-batch-size", type=int, default=12, help="Maximum drafts to send per round.")
    parser.add_argument("--min-wait-seconds", type=int, default=240, help="Minimum wait between rounds.")
    parser.add_argument("--max-wait-seconds", type=int, default=360, help="Maximum wait between rounds.")
    parser.add_argument("--per-email-min-seconds", type=int, default=0, help="Minimum wait between each draft send.")
    parser.add_argument("--per-email-max-seconds", type=int, default=0, help="Maximum wait between each draft send.")
    parser.add_argument("--window-minutes", type=int, default=55, help="Maximum runtime window for one invocation.")
    parser.add_argument("--single-run", action="store_true", help="Send only one randomized round, then exit.")
    parser.add_argument("--initial-jitter-seconds", type=int, default=120, help="Random delay before the first round.")
    parser.add_argument("--pause-flag", default="", help="If this file exists, exit without sending anything.")
    parser.add_argument("--seed", type=int, default=0, help="Optional random seed for reproducible runs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the first randomized round without sending.")
    parser.add_argument(
        "--max-total",
        type=int,
        default=0,
        help="Optional total cap for one invocation. Use 0 for no cap.",
    )
    args = parser.parse_args()

    if args.max_batch_size < args.min_batch_size:
        raise SystemExit("max-batch-size must be >= min-batch-size")
    if args.max_wait_seconds < args.min_wait_seconds:
        raise SystemExit("max-wait-seconds must be >= min-wait-seconds")
    if args.per_email_max_seconds < args.per_email_min_seconds:
        raise SystemExit("per-email-max-seconds must be >= per-email-min-seconds")
    if args.pause_flag and Path(args.pause_flag).exists():
        print_json({"paused": True, "pause_flag": args.pause_flag})
        return

    rng = random.Random(args.seed or None)
    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    profile = {}
    profile_error = ""
    try:
        profile = gmail_get_profile(config)
    except Exception as exc:
        profile_error = str(exc)

    emit(
        "loop_start",
        {
            "profile": profile,
            "profile_error": profile_error,
            "window_minutes": args.window_minutes,
            "min_batch_size": args.min_batch_size,
            "max_batch_size": args.max_batch_size,
            "min_wait_seconds": args.min_wait_seconds,
            "max_wait_seconds": args.max_wait_seconds,
        },
    )

    if args.initial_jitter_seconds > 0:
        jitter = rng.randint(0, args.initial_jitter_seconds)
        emit("initial_jitter", {"sleep_seconds": jitter})
        time.sleep(jitter)

    started_at = time.time()
    deadline = started_at + args.window_minutes * 60
    rounds = []
    sent_total = 0
    failed_total = 0
    attempted_draft_ids = set()

    while time.time() < deadline:
        if args.pause_flag and Path(args.pause_flag).exists():
            rounds.append({"paused": True, "pause_flag": args.pause_flag})
            emit("paused", {"pause_flag": args.pause_flag})
            break

        drafts = gmail_list_drafts(config)
        if not drafts:
            rounds.append({"reason": "no_drafts_remaining"})
            emit("no_drafts_remaining", {})
            break

        drafts = [row for row in drafts if row.get("id", "").strip() and row.get("id", "").strip() not in attempted_draft_ids]
        if not drafts:
            rounds.append({"reason": "no_unattempted_drafts_remaining"})
            emit("no_unattempted_drafts_remaining", {"attempted_count": len(attempted_draft_ids)})
            break

        batch_size = rng.randint(args.min_batch_size, args.max_batch_size)
        if args.max_total > 0:
            batch_size = min(batch_size, max(args.max_total - sent_total, 0))
        if batch_size <= 0:
            rounds.append({"reason": "max_total_reached"})
            emit("max_total_reached", {"sent_total": sent_total, "max_total": args.max_total})
            break

        selected = drafts[:batch_size]
        emit(
            "round_start",
            {
                "requested_batch_size": batch_size,
                "available_drafts": len(drafts),
                "selected_count": len(selected),
                "sent_total": sent_total,
                "failed_total": failed_total,
            },
        )
        if args.dry_run:
            print_json(
                {
                    "profile": profile,
                    "profile_error": profile_error,
                    "dry_run": True,
                    "requested_batch_size": batch_size,
                    "selected_count": len(selected),
                    "selected_jobs": [{"draft_id": row.get("id", ""), "raw": row} for row in selected],
                }
            )
            return

        round_sent = []
        round_failures = []
        for row in selected:
            draft_id = row.get("id", "").strip()
            if not draft_id:
                continue
            attempted_draft_ids.add(draft_id)
            try:
                payload = gmail_send_draft(config, draft_id)
                sent_total += 1
                round_sent.append(
                    {
                        "draft_id": draft_id,
                        "message_id": payload.get("id", ""),
                        "thread_id": payload.get("threadId", ""),
                    }
                )
                if len(round_sent) + len(round_failures) < len(selected) and args.per_email_max_seconds > 0:
                    per_email_sleep = rng.randint(args.per_email_min_seconds, args.per_email_max_seconds)
                    round_sent[-1]["post_send_sleep_seconds"] = per_email_sleep
                    time.sleep(per_email_sleep)
            except Exception as exc:
                failed_total += 1
                round_failures.append({"draft_id": draft_id, "error": str(exc)})

        wait_seconds = rng.randint(args.min_wait_seconds, args.max_wait_seconds)
        emit(
            "round_complete",
            {
                "requested_batch_size": batch_size,
                "actual_sent_count": len(round_sent),
                "failure_count": len(round_failures),
                "next_wait_seconds": wait_seconds,
                "sent_total": sent_total,
                "failed_total": failed_total,
            },
        )
        rounds.append(
            {
                "requested_batch_size": batch_size,
                "actual_sent_count": len(round_sent),
                "failure_count": len(round_failures),
                "sent": round_sent,
                "failures": round_failures,
                "next_wait_seconds": wait_seconds,
                "timestamp": now_iso(),
            }
        )

        if args.single_run:
            emit("single_run_exit", {"sent_total": sent_total, "failed_total": failed_total})
            break
        if args.max_total > 0 and sent_total >= args.max_total:
            rounds.append({"reason": "max_total_reached"})
            emit("max_total_reached", {"sent_total": sent_total, "max_total": args.max_total})
            break
        if time.time() + wait_seconds >= deadline:
            emit("window_exhausted_before_wait", {"wait_seconds": wait_seconds, "window_minutes": args.window_minutes})
            break
        emit("sleeping_before_next_round", {"sleep_seconds": wait_seconds})
        time.sleep(wait_seconds)

    remaining = len(gmail_list_drafts(config))
    print_json(
        {
            "profile": profile,
            "profile_error": profile_error,
            "window_minutes": args.window_minutes,
            "min_batch_size": args.min_batch_size,
            "max_batch_size": args.max_batch_size,
            "min_wait_seconds": args.min_wait_seconds,
            "max_wait_seconds": args.max_wait_seconds,
            "sent_total": sent_total,
            "failed_total": failed_total,
            "remaining_drafts": remaining,
            "rounds": rounds,
        }
    )


if __name__ == "__main__":
    main()
