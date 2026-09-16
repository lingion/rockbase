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
    STATUS_PENDING,
    STATUS_SAMPLED,
    add_common_gmail_args,
    add_manifest_args,
    add_source_writeback_args,
    build_gmail_config,
    gmail_create_draft,
    gmail_get_profile,
    load_manifest,
    now_iso,
    print_json,
    save_manifest,
    summarize_manifest,
    writeback_source_status,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run resumable bulk draft creation from a manifest.")
    add_manifest_args(parser)
    add_common_gmail_args(parser)
    add_source_writeback_args(parser)
    parser.add_argument("--batch-size", type=int, default=20, help="Number of jobs per batch.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume only pending/failed jobs. Default processes pending jobs only.",
    )
    parser.add_argument(
        "--include-sampled",
        action="store_true",
        help="Also process sampled jobs. Use only when you intentionally want to recreate sampled drafts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview next batch only.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    eligible_statuses = {STATUS_PENDING, STATUS_FAILED} if args.resume else {STATUS_PENDING}
    if args.include_sampled:
        eligible_statuses.add(STATUS_SAMPLED)
    selected = [row for row in rows if row.get("status", "") in eligible_statuses][: args.batch_size]

    if args.dry_run:
        print_json(
            {
                "manifest": str(manifest_path),
                "selected_jobs": selected,
                "selected_count": len(selected),
                "summary": summarize_manifest(rows),
                "dry_run": True,
            }
        )
        return

    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    profile = gmail_get_profile(config)
    successes = []
    failures = []
    source_row_ids = []
    for row in selected:
        try:
            payload = gmail_create_draft(config, row["to"], row["subject"], row["body"])
            row["status"] = STATUS_DONE
            row["draft_id"] = payload.get("id", "")
            row["error"] = ""
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            successes.append({"job_id": row["job_id"], "draft_id": row["draft_id"], "to": row["to"]})
            source_row_ids.append(row["row_id"])
            # Preserve a created cloud draft before another API call can interrupt the batch.
            save_manifest(manifest_path, rows)
            writeback_source_status(
                args.source_csv,
                [row["row_id"]],
                args.source_status_field,
                args.source_drafted_value,
            )
        except Exception as exc:
            row["status"] = STATUS_FAILED
            row["error"] = str(exc)
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            failures.append({"job_id": row["job_id"], "to": row["to"], "error": str(exc)})
            save_manifest(manifest_path, rows)

    save_manifest(manifest_path, rows)
    source_writeback_count = writeback_source_status(
        args.source_csv,
        source_row_ids,
        args.source_status_field,
        args.source_drafted_value,
    )
    print_json(
        {
            "profile": profile,
            "manifest": str(manifest_path),
            "batch_size": args.batch_size,
            "processed": len(selected),
            "success_count": len(successes),
            "failure_count": len(failures),
            "successes": successes,
            "failures": failures,
            "source_writeback_count": source_writeback_count,
            "summary": summarize_manifest(rows),
        }
    )


if __name__ == "__main__":
    main()
