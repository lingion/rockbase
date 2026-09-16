#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import add_common_gmail_args, build_gmail_config, gmail_delete_draft, print_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete duplicate or unexpected drafts from a reconcile report.")
    add_common_gmail_args(parser)
    parser.add_argument("--report", required=True, help="Path to reconcile report JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Preview draft ids to delete without deleting.")
    args = parser.parse_args()

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    delete_ids = []
    for item in report.get("duplicate", []):
        delete_ids.extend(item.get("draft_ids", []))
    for item in report.get("unexpected", []):
        delete_ids.extend(item.get("draft_ids", []))

    if args.dry_run:
        print_json({"report": str(report_path), "delete_count": len(delete_ids), "draft_ids": delete_ids, "dry_run": True})
        return

    config = build_gmail_config(args.access_token or None, args.user_id, args.token_file)
    deleted = []
    failed = []
    for draft_id in delete_ids:
        try:
            gmail_delete_draft(config, draft_id)
            deleted.append(draft_id)
        except Exception as exc:
            failed.append({"draft_id": draft_id, "error": str(exc)})

    print_json(
        {
            "report": str(report_path),
            "delete_count": len(delete_ids),
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted": deleted,
            "failed": failed,
        }
    )


if __name__ == "__main__":
    main()
