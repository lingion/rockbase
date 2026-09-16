#!/usr/bin/env python3
"""Apply validated S3-Codex shadow rows to the live S3 master in one batch."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path


SELECTED_REPLY_STATUS = "shadow_backfill_preview_applied"


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


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def sort_key(row: dict[str, str]) -> tuple[int, float]:
    bucket = row.get("Sort_Bucket", "")
    try:
        bucket_rank = int(bucket.split("_", 1)[0])
    except Exception:
        bucket_rank = 99
    dt = parse_dt(row.get("Reply_Last_At", ""))
    return bucket_rank, -dt.timestamp() if dt != datetime.min else float("inf")


def union_fieldnames(live_fields: list[str], shadow_fields: list[str]) -> list[str]:
    fields = list(live_fields)
    for field in shadow_fields:
        if field not in fields:
            fields.append(field)
    return fields


def normalize_rows(rows: list[dict[str, str]], fieldnames: list[str]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        out = {field: "" for field in fieldnames}
        out.update(row)
        normalized.append(out)
    return normalized


def match_row(candidate: dict[str, str], live_rows: list[dict[str, str]]) -> tuple[int | None, str]:
    thread_id = candidate.get("Reply_Thread_ID", "").strip()
    email = candidate.get("Reply_Contact_Email", "").strip().lower()
    creator = candidate.get("频道/作者名称", "").strip().lower()

    for idx, row in enumerate(live_rows):
        if thread_id and row.get("Reply_Thread_ID", "").strip() == thread_id:
            return idx, "Reply_Thread_ID"
    for idx, row in enumerate(live_rows):
        if email and row.get("Reply_Contact_Email", "").strip().lower() == email:
            return idx, "Reply_Contact_Email"
    for idx, row in enumerate(live_rows):
        if creator and row.get("频道/作者名称", "").strip().lower() == creator:
            return idx, "频道/作者名称"
    return None, "append_new"


def select_shadow_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("Reply_Status", "").strip() == SELECTED_REPLY_STATUS]


def manifest_row(row: dict[str, str], operation: str, match_basis: str) -> dict[str, str]:
    return {
        "operation": operation,
        "match_basis": match_basis,
        "creator_name": row.get("频道/作者名称", ""),
        "reply_contact_email": row.get("Reply_Contact_Email", ""),
        "reply_thread_id": row.get("Reply_Thread_ID", ""),
        "reply_last_at": row.get("Reply_Last_At", ""),
        "pricing_round": row.get("Pricing_Round", ""),
        "current_reply_scenario": row.get("Current_Reply_Scenario", ""),
        "next_reply_action": row.get("Next_Reply_Action", ""),
        "attachment_ocr_status": row.get("Attachment_OCR_Status", ""),
        "reply_needs_manual_review": row.get("Reply_Needs_Manual_Review", ""),
        "draft_workflow_status": row.get("Draft_Workflow_Status", ""),
        "current_price_summary": row.get("current_price_summary", ""),
        "latest_price_raw": row.get("latest_price_raw", ""),
        "latest_price_normalized": row.get("latest_price_normalized", ""),
        "latest_price_basis": row.get("latest_price_basis", ""),
        "sort_bucket": row.get("Sort_Bucket", ""),
        "pipeline_stage": row.get("Pipeline_Stage", ""),
    }


def write_summary(path: Path, manifest_rows: list[dict[str, str]], live_rows_before: int, live_rows_after: int, backup_paths: list[Path]) -> None:
    appended = sum(1 for row in manifest_rows if row["operation"] == "append")
    updated = sum(1 for row in manifest_rows if row["operation"] == "update")
    manual = sum(1 for row in manifest_rows if row["reply_needs_manual_review"].strip().lower() == "yes")
    ocr_related = sum(1 for row in manifest_rows if row["attachment_ocr_status"].strip() not in {"", "none"})
    lines = [
        "# Live Master Writeback Summary",
        "",
        f"- selected rows: `{len(manifest_rows)}`",
        f"- appended rows: `{appended}`",
        f"- updated rows: `{updated}`",
        f"- live rows before: `{live_rows_before}`",
        f"- live rows after: `{live_rows_after}`",
        f"- manual review rows: `{manual}`",
        f"- attachment/OCR rows: `{ocr_related}`",
        "",
        "## Backups",
    ]
    for path_item in backup_paths:
        lines.append(f"- `{path_item}`")
    lines.extend(["", "## Written Rows"])
    for row in manifest_rows:
        lines.append(f"- `{row['creator_name']}` | `{row['operation']}` | `{row['pricing_round']}` | `{row['next_reply_action']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-master", required=True)
    parser.add_argument("--shadow-master", required=True)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--batch-id", default="batch_001")
    args = parser.parse_args()

    live_path = Path(args.live_master)
    shadow_path = Path(args.shadow_master)
    batch_dir = Path(args.batch_dir)
    backup_dir = Path(args.backup_dir)
    batch_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%H%M%S")
    live_fields, live_rows_raw = read_csv(live_path)
    shadow_fields, shadow_rows_raw = read_csv(shadow_path)
    selected_rows = select_shadow_rows(shadow_rows_raw)
    if not selected_rows:
        raise SystemExit("No selected shadow rows found for live writeback.")

    fieldnames = union_fieldnames(live_fields, shadow_fields)
    live_rows = normalize_rows(live_rows_raw, fieldnames)
    selected_rows = normalize_rows(selected_rows, fieldnames)

    backup_name = f"{live_path.name}_bak_{stamp}.csv"
    workbench_backup = batch_dir / f"pre_writeback_master_bak_{stamp}.csv"
    agency_backup = backup_dir / backup_name
    shutil.copy2(live_path, workbench_backup)
    shutil.copy2(live_path, agency_backup)

    manifest_rows: list[dict[str, str]] = []
    raw_threads: list[dict[str, str]] = []
    llm_inputs: list[dict[str, str]] = []
    llm_outputs: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []

    for row in selected_rows:
        idx, match_basis = match_row(row, live_rows)
        operation = "append" if idx is None else "update"
        if idx is None:
            live_rows.append(row)
        else:
            live_rows[idx].update(row)

        mrow = manifest_row(row, operation, match_basis)
        manifest_rows.append(mrow)
        audit_rows.append(mrow)
        raw_threads.append({
            "batch_id": args.batch_id,
            "creator_name": row.get("频道/作者名称", ""),
            "reply_thread_id": row.get("Reply_Thread_ID", ""),
            "mail1_reply_block": row.get("mail1_reply_block", ""),
            "mail2_reply_block": row.get("mail2_reply_block", ""),
            "source_subject": row.get("Reply_Last_Subject", ""),
        })
        llm_inputs.append({
            "batch_id": args.batch_id,
            "creator_name": row.get("频道/作者名称", ""),
            "thread_context_source": "existing_validated_shadow_master",
        })
        llm_outputs.append({
            "batch_id": args.batch_id,
            "creator_name": row.get("频道/作者名称", ""),
            "pricing_round": row.get("Pricing_Round", ""),
            "next_reply_action": row.get("Next_Reply_Action", ""),
            "attachment_ocr_status": row.get("Attachment_OCR_Status", ""),
            "manual_review": row.get("Reply_Needs_Manual_Review", ""),
        })

    live_rows.sort(key=sort_key)
    write_csv(live_path, fieldnames, live_rows)
    post_snapshot = batch_dir / f"post_writeback_master_snapshot_{stamp}.csv"
    shutil.copy2(live_path, post_snapshot)

    manifest_fields = list(manifest_rows[0].keys())
    write_csv(batch_dir / "writeback_manifest.csv", manifest_fields, manifest_rows)
    write_csv(batch_dir / f"writeback_manifest_{args.batch_id}_{stamp}.csv", manifest_fields, manifest_rows)
    write_csv(batch_dir / "audit_live_writeback.csv", manifest_fields, audit_rows)
    write_csv(batch_dir / "thread_candidates.csv", ["creator_name", "reply_contact_email", "reply_thread_id", "reply_last_at", "pricing_round", "next_reply_action"], manifest_rows)
    write_jsonl(batch_dir / "raw_threads.jsonl", raw_threads)
    write_jsonl(batch_dir / "llm_judgment_input.jsonl", llm_inputs)
    write_jsonl(batch_dir / "llm_judgment_output.jsonl", llm_outputs)
    write_summary(
        batch_dir / "summary_live_writeback.md",
        manifest_rows,
        len(live_rows_raw),
        len(live_rows),
        [agency_backup, workbench_backup],
    )


if __name__ == "__main__":
    main()
