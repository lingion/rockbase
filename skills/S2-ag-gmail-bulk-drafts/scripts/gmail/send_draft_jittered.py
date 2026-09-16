#!/usr/bin/env python3
import argparse
import random
import time
from urllib import parse
from dataclasses import dataclass
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_SAMPLED,
    STATUS_SENT,
    build_gmail_config,
    gmail_get_profile,
    gmail_request,
    gmail_send_draft,
    load_manifest,
    now_iso,
    print_json,
    save_manifest,
    summarize_manifest,
    writeback_source_status,
)


@dataclass
class SendJob:
    manifest: Path
    source_csv: Path


def parse_job(value: str) -> SendJob:
    parts = value.split("::", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("job must look like manifest.csv::source.csv")
    manifest, source_csv = (Path(part).expanduser() for part in parts)
    return SendJob(manifest=manifest, source_csv=source_csv)


def load_selected_rows(job: SendJob, allowed_statuses: set[str], limit: int) -> tuple[list[dict], list[dict]]:
    rows = load_manifest(job.manifest)
    selected = [
        row for row in rows
        if row.get("status", "") in allowed_statuses and row.get("draft_id", "").strip()
    ][:limit]
    return rows, selected


def find_sent_after_empty_payload(config, row: dict) -> dict:
    subject = (row.get("subject", "") or "").replace('"', "")
    query = f'in:sent to:{row.get("to", "")} subject:"{subject}"'
    payload = gmail_request(config, "GET", "messages?" + parse.urlencode({"q": query, "maxResults": "1"}))
    messages = payload.get("messages", [])
    if not messages:
        return {}
    return messages[0]


def mark_sent(row: dict, job: SendJob, payload: dict) -> dict:
    row["status"] = STATUS_SENT
    row["error"] = ""
    row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
    row["updated_at"] = now_iso()
    return {
        "manifest": str(job.manifest),
        "job_id": row["job_id"],
        "draft_id": row["draft_id"],
        "to": row["to"],
        "message_id": payload.get("id", ""),
        "thread_id": payload.get("threadId", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send Gmail drafts with randomized batch size and pause interval inside one execution window."
    )
    parser.add_argument(
        "--job",
        action="append",
        required=True,
        type=parse_job,
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
    parser.add_argument("--min-batch-size", type=int, default=10, help="Minimum drafts to send per round.")
    parser.add_argument("--max-batch-size", type=int, default=15, help="Maximum drafts to send per round.")
    parser.add_argument("--min-wait-seconds", type=int, default=300, help="Minimum wait between rounds.")
    parser.add_argument("--max-wait-seconds", type=int, default=360, help="Maximum wait between rounds.")
    parser.add_argument("--per-email-min-seconds", type=int, default=0, help="Minimum wait between each draft send.")
    parser.add_argument("--per-email-max-seconds", type=int, default=0, help="Maximum wait between each draft send.")
    parser.add_argument("--window-minutes", type=int, default=55, help="Maximum runtime window for one invocation.")
    parser.add_argument("--single-run", action="store_true", help="Send only one randomized round, then exit.")
    parser.add_argument("--initial-jitter-seconds", type=int, default=0, help="Optional random delay before the first round.")
    parser.add_argument(
        "--allowed-statuses",
        default=f"{STATUS_SAMPLED},{STATUS_DONE}",
        help="Comma-separated manifest statuses eligible to send. Default: sampled,done.",
    )
    parser.add_argument("--pause-flag", default="", help="If this file exists, exit without sending anything.")
    parser.add_argument("--seed", type=int, default=0, help="Optional random seed for reproducible runs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the first randomized round without sending.")
    parser.add_argument(
        "--max-total",
        type=int,
        default=0,
        help="Optional total cap for this invocation. Use 0 for no cap.",
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
    allowed_statuses = {item.strip() for item in args.allowed_statuses.split(",") if item.strip()}
    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    profile = {}
    profile_error = ""
    try:
        profile = gmail_get_profile(config)
    except Exception as exc:
        # Profile lookup is only telemetry; do not abort a send window on transient network issues.
        profile_error = str(exc)

    if args.initial_jitter_seconds > 0:
        time.sleep(rng.randint(0, args.initial_jitter_seconds))

    started_at = time.time()
    deadline = started_at + args.window_minutes * 60
    rounds = []
    sent_total = 0
    failed_total = 0

    while time.time() < deadline:
        if args.pause_flag and Path(args.pause_flag).exists():
            rounds.append({"paused": True, "pause_flag": args.pause_flag})
            break

        batch_size = rng.randint(args.min_batch_size, args.max_batch_size)
        if args.max_total > 0:
            batch_size = min(batch_size, max(args.max_total - sent_total, 0))
        if batch_size <= 0:
            rounds.append({"reason": "max_total_reached"})
            break
        remaining = batch_size
        round_sent = []
        round_failures = []

        if args.dry_run:
            preview = []
            for job in args.job:
                _, selected = load_selected_rows(job, allowed_statuses, remaining)
                for row in selected:
                    preview.append(
                        {
                            "manifest": str(job.manifest),
                            "to": row.get("to", ""),
                            "draft_id": row.get("draft_id", ""),
                            "status": row.get("status", ""),
                        }
                    )
                    remaining -= 1
                    if remaining <= 0:
                        break
                if remaining <= 0:
                    break
            print_json(
                {
                    "profile": profile,
                    "profile_error": profile_error,
                    "dry_run": True,
                    "requested_batch_size": batch_size,
                    "selected_count": len(preview),
                    "selected_jobs": preview,
                }
            )
            return

        for job in args.job:
            if remaining <= 0:
                break
            rows, selected = load_selected_rows(job, allowed_statuses, remaining)
            if not selected:
                continue

            source_row_ids = []
            for row in selected:
                try:
                    payload = gmail_send_draft(config, row["draft_id"])
                    source_row_ids.append(row["row_id"])
                    remaining -= 1
                    sent_total += 1
                    round_sent.append(mark_sent(row, job, payload))
                    # Persist each successful send before pacing can interrupt the process.
                    save_manifest(job.manifest, rows)
                    writeback_source_status(
                        str(job.source_csv),
                        [row["row_id"]],
                        args.source_status_field,
                        args.source_sent_value,
                    )
                    if remaining > 0 and args.per_email_max_seconds > 0:
                        per_email_sleep = rng.randint(args.per_email_min_seconds, args.per_email_max_seconds)
                        round_sent[-1]["post_send_sleep_seconds"] = per_email_sleep
                        time.sleep(per_email_sleep)
                except Exception as exc:
                    recovered_payload = {}
                    if "gmail_send_draft returned empty payload" in str(exc):
                        try:
                            recovered_payload = find_sent_after_empty_payload(config, row)
                        except Exception:
                            recovered_payload = {}
                    if recovered_payload:
                        source_row_ids.append(row["row_id"])
                        remaining -= 1
                        sent_total += 1
                        round_sent.append(mark_sent(row, job, recovered_payload))
                        round_sent[-1]["reconciled_after_empty_payload"] = True
                        save_manifest(job.manifest, rows)
                        writeback_source_status(
                            str(job.source_csv),
                            [row["row_id"]],
                            args.source_status_field,
                            args.source_sent_value,
                        )
                        if remaining > 0 and args.per_email_max_seconds > 0:
                            per_email_sleep = rng.randint(args.per_email_min_seconds, args.per_email_max_seconds)
                            round_sent[-1]["post_send_sleep_seconds"] = per_email_sleep
                            time.sleep(per_email_sleep)
                        if remaining <= 0:
                            break
                        continue
                    row["status"] = STATUS_FAILED
                    row["error"] = str(exc)
                    row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
                    row["updated_at"] = now_iso()
                    failed_total += 1
                    round_failures.append(
                        {
                            "manifest": str(job.manifest),
                            "job_id": row["job_id"],
                            "draft_id": row["draft_id"],
                            "to": row["to"],
                            "error": str(exc),
                        }
                    )
                    save_manifest(job.manifest, rows)
                if remaining <= 0:
                    break

            save_manifest(job.manifest, rows)
            writeback_source_status(
                str(job.source_csv),
                source_row_ids,
                args.source_status_field,
                args.source_sent_value,
            )

        if not round_sent and not round_failures:
            rounds.append({"reason": "no_eligible_drafts_remaining"})
            break

        wait_seconds = rng.randint(args.min_wait_seconds, args.max_wait_seconds)
        rounds.append(
            {
                "requested_batch_size": batch_size,
                "actual_sent_count": len(round_sent),
                "failure_count": len(round_failures),
                "sent": round_sent,
                "failures": round_failures,
                "next_wait_seconds": wait_seconds,
            }
        )

        if args.single_run:
            break
        if args.max_total > 0 and sent_total >= args.max_total:
            rounds.append({"reason": "max_total_reached"})
            break
        if time.time() + wait_seconds >= deadline:
            break
        time.sleep(wait_seconds)

    summaries = {}
    for job in args.job:
        summaries[str(job.manifest)] = summarize_manifest(load_manifest(job.manifest))

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
            "rounds": rounds,
            "summaries": summaries,
        }
    )


if __name__ == "__main__":
    main()
