#!/usr/bin/env python3
import argparse
from pathlib import Path

from common import (
    STATUS_DONE,
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
    parser = argparse.ArgumentParser(description="Create reply drafts in bulk from a manifest.")
    add_common_args(parser)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-sampled", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    eligible = {STATUS_PENDING, STATUS_FAILED} if args.resume else {STATUS_PENDING}
    if args.include_sampled:
        eligible.add(STATUS_SAMPLED)
    selected = [row for row in rows if row.get("status", "") in eligible][: args.batch_size]

    access_token = args.access_token or get_token_file_access_token(args.token_file)
    profile = gmail_get_profile(access_token)

    successes = []
    failures = []
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
            row["status"] = STATUS_DONE
            row["draft_id"] = payload.get("id", "")
            row["error"] = ""
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            successes.append({"job_id": row["job_id"], "draft_id": row["draft_id"], "wave": row["reply_wave"]})
        except Exception as exc:
            row["status"] = STATUS_FAILED
            row["error"] = str(exc)
            row["attempt_count"] = str(int(row.get("attempt_count", "0") or "0") + 1)
            row["updated_at"] = now_iso()
            failures.append({"job_id": row["job_id"], "error": str(exc)})

    save_manifest(manifest_path, rows)
    print({"profile": profile, "processed": len(selected), "success_count": len(successes), "failure_count": len(failures), "manifest": str(manifest_path.resolve())})


if __name__ == "__main__":
    main()
