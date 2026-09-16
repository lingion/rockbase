#!/usr/bin/env python3
"""Apply preview rows to a shadow S3 master without touching the live master."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path


NEW_COLUMNS = [
    "current_price_summary",
    "Pricing_Effective_Wave",
    "Pricing_Change_Type",
    "Pricing_Round",
    "Current_Reply_Scenario",
    "Next_Reply_Action",
    "Attachment_OCR_Status",
    "Draft_Workflow_Status",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def parse_dt(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.min
    for parser in (
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None),
        lambda v: parsedate_to_datetime(v).replace(tzinfo=None),
    ):
        try:
            return parser(value)
        except Exception:
            continue
    return datetime.min


def ensure_columns(fieldnames: list[str]) -> list[str]:
    out = list(fieldnames)
    for col in NEW_COLUMNS:
        if col not in out:
            out.append(col)
    return out


def match_row(preview: dict[str, str], rows: list[dict[str, str]]) -> int | None:
    email = preview.get("reply_contact_email", "").strip().lower()
    thread_id = preview.get("thread_id", "").strip()
    creator = preview.get("creator_name", "").strip().lower()

    for idx, row in enumerate(rows):
        if thread_id and row.get("Reply_Thread_ID", "").strip() == thread_id:
            return idx
    for idx, row in enumerate(rows):
        if email and email == row.get("Reply_Contact_Email", "").strip().lower():
            return idx
    for idx, row in enumerate(rows):
        if creator and creator == row.get("频道/作者名称", "").strip().lower():
            return idx
    return None


def blank_row(fieldnames: list[str]) -> dict[str, str]:
    return {k: "" for k in fieldnames}


def apply_preview(preview: dict[str, str], row: dict[str, str]) -> None:
    row["Source_Tag"] = row.get("Source_Tag") or "S3-Codex plugin reply shadow backfill"
    row["频道/作者名称"] = preview.get("creator_name", row.get("频道/作者名称", ""))
    row["平台"] = preview.get("platform", row.get("平台", ""))
    row["Reply_Contact_Email"] = preview.get("reply_contact_email", row.get("Reply_Contact_Email", ""))
    row["mail1_reply_block"] = preview.get("mail1_reply_block", row.get("mail1_reply_block", ""))
    row["mail2_reply_block"] = preview.get("mail2_reply_block", row.get("mail2_reply_block", ""))
    row["latest_price_raw"] = preview.get("latest_price_raw", row.get("latest_price_raw", ""))
    row["latest_price_normalized"] = preview.get("latest_price_normalized", row.get("latest_price_normalized", ""))
    row["latest_price_basis"] = preview.get("latest_price_basis", row.get("latest_price_basis", ""))
    row["current_price_summary"] = preview.get("current_price_summary", row.get("current_price_summary", ""))
    row["Pricing_Effective_Wave"] = preview.get("pricing_effective_wave", row.get("Pricing_Effective_Wave", ""))
    row["Pricing_Change_Type"] = preview.get("pricing_change_type", row.get("Pricing_Change_Type", ""))
    row["Pricing_Round"] = preview.get("pricing_round", row.get("Pricing_Round", ""))
    row["Current_Reply_Scenario"] = preview.get("current_reply_scenario", row.get("Current_Reply_Scenario", ""))
    row["Next_Reply_Action"] = preview.get("next_reply_action", row.get("Next_Reply_Action", ""))
    row["Attachment_OCR_Status"] = preview.get("attachment_ocr_status", row.get("Attachment_OCR_Status", ""))
    row["Sort_Bucket"] = preview.get("sort_bucket", row.get("Sort_Bucket", ""))
    row["Reply_Thread_ID"] = preview.get("thread_id", row.get("Reply_Thread_ID", ""))
    row["Reply_Last_Message_ID"] = preview.get("latest_inbound_message_id", row.get("Reply_Last_Message_ID", ""))
    row["Reply_Last_Subject"] = preview.get("source_subject", row.get("Reply_Last_Subject", ""))
    row["Reply_Last_At"] = preview.get("latest_inbound_at", row.get("Reply_Last_At", ""))
    row["Outbound_Message_IDs"] = preview.get("outbound_message_ids", row.get("Outbound_Message_IDs", ""))
    row["Latest_Inbound_Message_ID"] = preview.get("latest_inbound_message_id", row.get("Latest_Inbound_Message_ID", ""))
    row["Reply_Stream"] = preview.get("reply_stream", row.get("Reply_Stream", ""))
    row["Pipeline_Stage"] = preview.get("pipeline_stage", row.get("Pipeline_Stage", ""))
    row["Reply_Status"] = "shadow_backfill_preview_applied"
    row["Reply_Needs_Manual_Review"] = preview.get("reply_needs_manual_review", row.get("Reply_Needs_Manual_Review", ""))
    row["Manual_Review_Reason"] = preview.get("manual_review_reason", row.get("Manual_Review_Reason", ""))
    row["Capture_Run_ID"] = "shadow_backfill_2026-05-07"
    row["Capture_At"] = datetime.now().isoformat(timespec="seconds")
    row["Draft_Workflow_Status"] = row.get("Draft_Workflow_Status", "") or "not_started"


def sort_key(row: dict[str, str]) -> tuple[int, float]:
    bucket = row.get("Sort_Bucket", "")
    try:
        bucket_rank = int(bucket.split("_", 1)[0])
    except Exception:
        bucket_rank = 99
    dt = parse_dt(row.get("Reply_Last_At", ""))
    return bucket_rank, -dt.timestamp() if dt != datetime.min else float("inf")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict[str, str]], append_count: int, update_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Shadow Master Writeback Summary",
        "",
        f"- appended rows: `{append_count}`",
        f"- updated rows: `{update_count}`",
        f"- total rows in shadow master: `{len(rows)}`",
        "",
        "## Observations",
        "- `no_quote` cases are intentionally kept in lower sort buckets so they sink below quoted cases.",
        "- `attachment_present_ocr_pending` cases are written into the table immediately, but still wait for OCR before final price confidence is considered complete.",
        "- `mail2_requote` cases float above `mail1_first_quote` cases because they usually deserve faster follow-up decisions.",
        "",
        "## Next Upgrade Candidates",
        "- Add OCR pipeline output merge so `attachment_present_ocr_pending` can automatically become priced rows.",
        "- Add stronger master row matching using `账号ID` and outbound wave lineage instead of email-only matching.",
        "- Add automatic re-sort after future quote updates so `no_quote` rows float up when a real price arrives.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--preview-csv", required=True)
    parser.add_argument("--shadow-csv", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    fieldnames, master_rows = read_csv(Path(args.master_csv))
    preview_fieldnames, preview_rows = read_csv(Path(args.preview_csv))
    _ = preview_fieldnames

    fieldnames = ensure_columns(fieldnames)
    normalized_master_rows: list[dict[str, str]] = []
    for row in master_rows:
        normalized = blank_row(fieldnames)
        normalized.update(row)
        normalized_master_rows.append(normalized)

    appended = 0
    updated = 0
    for preview in preview_rows:
        idx = match_row(preview, normalized_master_rows)
        if idx is None:
            row = blank_row(fieldnames)
            apply_preview(preview, row)
            normalized_master_rows.append(row)
            appended += 1
        else:
            apply_preview(preview, normalized_master_rows[idx])
            updated += 1

    normalized_master_rows.sort(key=sort_key)
    write_csv(Path(args.shadow_csv), fieldnames, normalized_master_rows)
    write_summary(Path(args.summary_md), normalized_master_rows, appended, updated)


if __name__ == "__main__":
    main()
