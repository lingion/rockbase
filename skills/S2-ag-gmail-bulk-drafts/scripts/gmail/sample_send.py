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
    writeback_source_status,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create sample Gmail drafts from a manifest.")
    add_manifest_args(parser)
    add_common_gmail_args(parser)
    add_source_writeback_args(parser)
    parser.add_argument("--limit", type=int, default=1, help="Number of sample drafts to create.")
    parser.add_argument(
        "--status-filter",
        default=STATUS_PENDING,
        help="Only sample rows with this status. Default: pending.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview selected jobs without creating drafts.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    selected = [row for row in rows if row.get("status", "") == args.status_filter][: args.limit]
    if args.dry_run:
        print_json({"selected_jobs": selected, "count": len(selected), "dry_run": True})
        return

    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    profile = gmail_get_profile(config)
    created = []
    source_row_ids = []
    for row in selected:
        try:
            payload = gmail_create_draft(config, row["to"], row["subject"], row["body"])
            row["status"] = STATUS_SAMPLED
            row["draft_id"] = payload.get("id", "")
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            created.append({"job_id": row["job_id"], "draft_id": row["draft_id"], "to": row["to"]})
            source_row_ids.append(row["row_id"])
        except Exception as exc:
            row["status"] = STATUS_FAILED
            row["error"] = str(exc)
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
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
            "sample_limit": args.limit,
            "created": created,
            "created_count": len(created),
            "source_writeback_count": source_writeback_count,
        }
    )


if __name__ == "__main__":
    main()
