#!/usr/bin/env python3
"""Apply a reviewed ReplyOps writeback manifest to the live master CSV.

The manifest is the boundary between model judgment and deterministic writes:
models decide the row values, this script only validates, backs up, applies,
and audits the batch.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency"
)
BACKUP_ROOT = PROJECT_ROOT / "Agency/list-bak"
DATE = date.today().isoformat()
CLEAR_SENTINEL = "__CLEAR__"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return (value or "").strip().lower()


def should_clear(value: str | None) -> bool:
    return (value or "").strip() == CLEAR_SENTINEL


def build_indexes(rows: list[dict[str, str]]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    by_thread: dict[str, int] = {}
    by_message: dict[str, int] = {}
    by_email_author: dict[str, int] = {}
    for idx, row in enumerate(rows):
        thread_id = norm(row.get("Reply_Thread_ID"))
        if thread_id and thread_id not in by_thread:
            by_thread[thread_id] = idx
        message_id = norm(row.get("Reply_Last_Message_ID") or row.get("Latest_Inbound_Message_ID"))
        if message_id and message_id not in by_message:
            by_message[message_id] = idx
        email = norm(row.get("Reply_Contact_Email") or row.get("联系方式"))
        author = norm(row.get("频道/作者名称"))
        if email and author:
            key = f"{email}|{author}"
            if key not in by_email_author:
                by_email_author[key] = idx
    return by_thread, by_message, by_email_author


def manifest_rows(path: Path) -> list[dict[str, str]]:
    _, rows = read_csv(path)
    return [r for r in rows if norm(r.get("manifest_status") or "approved") == "approved"]


def make_backup(master: Path, batch_dir: Path, ts: str) -> tuple[Path, Path]:
    bak_dir = BACKUP_ROOT / DATE
    bak_dir.mkdir(parents=True, exist_ok=True)
    agency_bak = bak_dir / f"{master.name}_bak_{ts}.csv"
    workbench_bak = batch_dir / f"pre_writeback_master_bak_{ts}.csv"
    shutil.copy2(master, agency_bak)
    shutil.copy2(master, workbench_bak)
    return agency_bak, workbench_bak


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    bucket_order = {
        "0_quoted_mail2_plus": 0,
        "1_quoted_mail1": 1,
        "1_replied_clear_price": 2,
        "2_replied_no_quote": 3,
        "2_replied_need_review": 4,
        "3_contact_update": 5,
        "3_waiting": 6,
        "4_closed": 9,
    }

    def key(row: dict[str, str]) -> tuple[int, str, str]:
        bucket = bucket_order.get(row.get("Sort_Bucket", ""), 8)
        # ISO timestamps sort correctly as strings; reverse by inverting later.
        return (bucket, row.get("Reply_Last_At", ""), row.get("频道/作者名称", ""))

    return sorted(rows, key=key)


def apply_manifest(master: Path, manifest: Path, batch_dir: Path) -> None:
    ts = datetime.now().strftime("%H%M%S")
    fields, rows = read_csv(master)
    approved = manifest_rows(manifest)
    if not approved:
        raise SystemExit("No approved manifest rows to apply.")

    for row in approved:
        for field in row:
            if field not in fields and field not in {
                "manifest_status",
                "manifest_action",
                "match_basis",
                "audit_note",
            }:
                fields.append(field)

    agency_bak, workbench_bak = make_backup(master, batch_dir, ts)
    before_count = len(rows)
    by_thread, by_message, by_email_author = build_indexes(rows)
    audit_rows: list[dict[str, str]] = []
    appended = 0
    updated = 0

    skip_fields = {"manifest_status", "manifest_action", "match_basis", "audit_note"}
    for item in approved:
        action = norm(item.get("manifest_action"))
        thread_id = norm(item.get("Reply_Thread_ID"))
        message_id = norm(item.get("Reply_Last_Message_ID") or item.get("Latest_Inbound_Message_ID"))
        email_author = f"{norm(item.get('Reply_Contact_Email'))}|{norm(item.get('频道/作者名称'))}"
        target_idx = by_thread.get(thread_id) if thread_id else None
        if target_idx is None and message_id:
            target_idx = by_message.get(message_id)
        if target_idx is None and action == "update":
            target_idx = by_email_author.get(email_author)

        if target_idx is None:
            new_row = {field: "" for field in fields}
            for field, value in item.items():
                if field not in skip_fields:
                    new_row[field] = value
            rows.append(new_row)
            appended += 1
            applied_action = "append"
        else:
            target = rows[target_idx]
            for field, value in item.items():
                if field in skip_fields:
                    continue
                if should_clear(value):
                    target[field] = ""
                elif value != "":
                    target[field] = value
            updated += 1
            applied_action = "update"

        audit_rows.append(
            {
                "applied_action": applied_action,
                "requested_action": item.get("manifest_action", ""),
                "match_basis": item.get("match_basis", ""),
                "Reply_Thread_ID": item.get("Reply_Thread_ID", ""),
                "Reply_Contact_Email": item.get("Reply_Contact_Email", ""),
                "频道/作者名称": item.get("频道/作者名称", ""),
                "latest_price_normalized": item.get("latest_price_normalized", ""),
                "Next_Reply_Action": item.get("Next_Reply_Action", ""),
                "audit_note": item.get("audit_note", ""),
            }
        )

    rows = sort_rows(rows)
    write_csv(master, fields, rows)
    snapshot = batch_dir / f"post_writeback_master_snapshot_{ts}.csv"
    write_csv(snapshot, fields, rows)
    audit = batch_dir / "audit_live_writeback.csv"
    write_csv(
        audit,
        [
            "applied_action",
            "requested_action",
            "match_basis",
            "Reply_Thread_ID",
            "Reply_Contact_Email",
            "频道/作者名称",
            "latest_price_normalized",
            "Next_Reply_Action",
            "audit_note",
        ],
        audit_rows,
    )

    summary = batch_dir / "summary_live_writeback.md"
    summary.write_text(
        "\n".join(
            [
                "# S3 ReplyOps Live Writeback Summary",
                "",
                f"- Applied at: {datetime.now().isoformat(timespec='seconds')}",
                f"- Manifest: `{manifest}`",
                f"- Live master: `{master}`",
                f"- Agency backup: `{agency_bak}`",
                f"- Workbench backup: `{workbench_bak}`",
                f"- Post snapshot: `{snapshot}`",
                f"- Rows before: {before_count}",
                f"- Rows after: {len(rows)}",
                f"- Appended: {appended}",
                f"- Updated: {updated}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Applied manifest: appended={appended} updated={updated} before={before_count} after={len(rows)}")
    print(f"Agency backup: {agency_bak}")
    print(f"Workbench backup: {workbench_bak}")
    print(f"Snapshot: {snapshot}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args()
    apply_manifest(Path(args.master), Path(args.manifest), Path(args.batch_dir))


if __name__ == "__main__":
    main()
