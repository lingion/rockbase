#!/usr/bin/env python3
import argparse
from pathlib import Path

from common import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SAMPLED,
    add_common_args,
    get_token_file_access_token,
    gmail_create_reply_draft,
    gmail_get_profile,
    load_manifest,
    now_iso,
    save_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create sample reply drafts from a manifest.")
    add_common_args(parser)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    selected = [row for row in rows if row.get("status", "") == STATUS_PENDING][: args.limit]
    access_token = args.access_token or get_token_file_access_token(args.token_file)
    profile = gmail_get_profile(access_token)

    created = []
    for row in selected:
        try:
            payload = gmail_create_reply_draft(
                access_token,
                row["to"],
                row["subject"],
                row["body"],
                row["thread_id"],
                row["latest_message_id"],
            )
            row["status"] = STATUS_SAMPLED
            row["draft_id"] = payload.get("id", "")
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            created.append({"job_id": row["job_id"], "draft_id": row["draft_id"], "wave": row["reply_wave"]})
        except Exception as exc:
            row["status"] = STATUS_FAILED
            row["error"] = str(exc)
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()

    save_manifest(manifest_path, rows)
    print({"profile": profile, "created_count": len(created), "created": created, "manifest": str(manifest_path.resolve())})


if __name__ == "__main__":
    main()
