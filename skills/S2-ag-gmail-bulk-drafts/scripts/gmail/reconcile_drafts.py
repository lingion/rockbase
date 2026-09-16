#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import (
    add_common_gmail_args,
    add_manifest_args,
    build_gmail_config,
    gmail_get_draft_signature,
    gmail_get_subject_only,
    gmail_list_drafts,
    load_manifest,
    print_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile manifest against Gmail drafts.")
    add_manifest_args(parser)
    add_common_gmail_args(parser)
    parser.add_argument(
        "--key-mode",
        choices=["subject", "to-subject", "to-subject-bodyhash"],
        default="to-subject-bodyhash",
        help="Business key used for reconciliation.",
    )
    parser.add_argument(
        "--max-drafts",
        type=int,
        default=0,
        help="Optional cap for Gmail drafts scanned. Use for smoke tests only.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Optional progress log frequency while reading Gmail drafts.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows = load_manifest(manifest_path)
    if args.key_mode == "subject":
        manifest_keys = [row["subject"] for row in rows]
    elif args.key_mode == "to-subject-bodyhash":
        manifest_keys = [f'{row["to"]}|||{row["subject"]}|||{row.get("body_hash", "")}' for row in rows]
    else:
        manifest_keys = [f'{row["to"]}|||{row["subject"]}' for row in rows]
    manifest_counter = Counter(manifest_keys)

    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    drafts = gmail_list_drafts(config)
    if args.max_drafts and args.max_drafts > 0:
        drafts = drafts[: args.max_drafts]
    draft_items = []
    for index, draft in enumerate(drafts, start=1):
        draft_id = draft["id"]
        if args.key_mode == "to-subject-bodyhash":
            key, internal_date = gmail_get_draft_signature(config, draft_id)
        else:
            key, internal_date = gmail_get_subject_only(config, draft_id)
        if args.key_mode == "subject":
            key = key.split("|||", 1)[1] if "|||" in key else key
        draft_items.append({"draft_id": draft_id, "key": key, "internal_date": internal_date})
        if args.progress_every and index % args.progress_every == 0:
            print_json(
                {
                    "progress": {
                        "drafts_processed": index,
                        "drafts_total": len(drafts),
                        "key_mode": args.key_mode,
                    }
                }
            )

    draft_counter = Counter(item["key"] for item in draft_items)
    by_key = defaultdict(list)
    for item in draft_items:
        by_key[item["key"]].append(item)
    for key in by_key:
        by_key[key].sort(key=lambda item: item["internal_date"])

    missing = []
    duplicate = []
    unexpected = []
    for key, need in manifest_counter.items():
        have = draft_counter.get(key, 0)
        if have < need:
            missing.append({"key": key, "missing_count": need - have})
        elif have > need:
            duplicate.append({"key": key, "extra_count": have - need, "draft_ids": [item["draft_id"] for item in by_key[key][need:]]})
    for key, have in draft_counter.items():
        if key not in manifest_counter:
            unexpected.append({"key": key, "extra_count": have, "draft_ids": [item["draft_id"] for item in by_key[key]]})

    print_json(
        {
            "manifest": str(manifest_path),
            "key_mode": args.key_mode,
            "manifest_total": len(rows),
            "draft_total": len(drafts),
            "missing_count": sum(item["missing_count"] for item in missing),
            "duplicate_count": sum(item["extra_count"] for item in duplicate),
            "unexpected_count": sum(item["extra_count"] for item in unexpected),
            "missing": missing,
            "duplicate": duplicate,
            "unexpected": unexpected,
        }
    )


if __name__ == "__main__":
    main()
