#!/usr/bin/env python3
import argparse
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
    add_common_gmail_args,
    add_manifest_args,
    build_gmail_config,
    gmail_get_profile,
    gmail_send_draft,
    load_manifest,
    now_iso,
    print_json,
    save_manifest,
    summarize_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an approved fixed-size batch of existing Gmail drafts from a manifest.")
    add_manifest_args(parser)
    add_common_gmail_args(parser)
    parser.add_argument("--batch-size", type=int, default=10, help="Maximum number of drafts to send in this run.")
    parser.add_argument(
        "--allowed-statuses",
        default=f"{STATUS_SAMPLED},{STATUS_DONE}",
        help="Comma-separated manifest statuses eligible to send. Default: sampled,done.",
    )
    parser.add_argument(
        "--pause-flag",
        default="",
        help="If this file exists, exit without sending anything.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview the next send batch only.")
    args = parser.parse_args()

    if args.pause_flag and Path(args.pause_flag).exists():
        print_json(
            {
                "manifest": args.manifest,
                "paused": True,
                "pause_flag": args.pause_flag,
            }
        )
        return

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    allowed = {item.strip() for item in args.allowed_statuses.split(",") if item.strip()}
    selected = [row for row in rows if row.get("status", "") in allowed and row.get("draft_id", "").strip()][: args.batch_size]

    if args.dry_run:
        print_json(
            {
                "manifest": str(manifest_path),
                "selected_count": len(selected),
                "selected_jobs": selected,
                "summary": summarize_manifest(rows),
                "dry_run": True,
            }
        )
        return

    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    profile = gmail_get_profile(config)

    sent = []
    failures = []
    for row in selected:
        try:
            payload = gmail_send_draft(config, row["draft_id"])
            row["status"] = STATUS_SENT
            row["error"] = ""
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            sent.append(
                {
                    "job_id": row["job_id"],
                    "draft_id": row["draft_id"],
                    "to": row["to"],
                    "message_id": payload.get("id", ""),
                    "thread_id": payload.get("threadId", ""),
                }
            )
        except Exception as exc:
            row["status"] = STATUS_FAILED
            row["error"] = str(exc)
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            failures.append({"job_id": row["job_id"], "draft_id": row["draft_id"], "to": row["to"], "error": str(exc)})

    save_manifest(manifest_path, rows)
    print_json(
        {
            "profile": profile,
            "manifest": str(manifest_path),
            "batch_size": args.batch_size,
            "processed": len(selected),
            "sent_count": len(sent),
            "failure_count": len(failures),
            "sent": sent,
            "failures": failures,
            "summary": summarize_manifest(rows),
        }
    )


if __name__ == "__main__":
    main()
