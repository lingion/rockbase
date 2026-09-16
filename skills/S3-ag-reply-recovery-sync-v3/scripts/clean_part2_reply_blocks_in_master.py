#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from build_part2_reply_blocks_preview import make_block
from project_paths import project_path


DEFAULT_MASTER = project_path("Agency", "list-master", "【S3 ReplyOps】Corestar-Replied-KOL_V3.csv")
DEFAULT_AUDIT = project_path("workbench", "rockbase-gmail-reply-recovery-v3", "audit", "2026-03-26_reply_block_cleaning_audit.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean quoted outbound content from Part2 reply blocks in the V3 master.")
    parser.add_argument("--master", default=str(DEFAULT_MASTER), help="Path to the V3 master CSV.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT), help="Audit CSV output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    master = Path(args.master)
    rows = []
    with master.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    audit_rows = []
    for row in rows:
        before_values = {
            "mail1_reply_block": row.get("mail1_reply_block", ""),
            "mail2_reply_block": row.get("mail2_reply_block", ""),
            "mail3_reply_block": row.get("mail3_reply_block", ""),
        }
        after_values = {
            "mail1_reply_block": make_block("", before_values["mail1_reply_block"]),
            "mail2_reply_block": make_block("", before_values["mail2_reply_block"]),
            "mail3_reply_block": make_block("", before_values["mail3_reply_block"]),
        }
        changed = False
        for key, new_value in after_values.items():
            # make_block("", block) removes only quote noise and leaves existing stamp line intact.
            if new_value != before_values[key]:
                row[key] = new_value
                changed = True
        if changed:
            audit_rows.append(
                {
                    "账号ID": row.get("账号ID", ""),
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "mail1_changed": "yes" if after_values["mail1_reply_block"] != before_values["mail1_reply_block"] else "no",
                    "mail2_changed": "yes" if after_values["mail2_reply_block"] != before_values["mail2_reply_block"] else "no",
                    "mail3_changed": "yes" if after_values["mail3_reply_block"] != before_values["mail3_reply_block"] else "no",
                }
            )

    with master.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    audit = Path(args.audit)
    audit.parent.mkdir(parents=True, exist_ok=True)
    with audit.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["账号ID", "频道/作者名称", "mail1_changed", "mail2_changed", "mail3_changed"],
        )
        writer.writeheader()
        writer.writerows(audit_rows)


if __name__ == "__main__":
    main()
