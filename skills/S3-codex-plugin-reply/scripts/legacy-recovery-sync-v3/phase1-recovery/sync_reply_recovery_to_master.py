#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Tuple


TARGET_FIELDS = [
    "Reply_Status",
    "Reply_Contact_Email",
    "Reply_Thread_Count",
    "Reply_Message_Count",
    "Reply_Thread_IDs",
    "Reply_Last_At",
    "Reply_Last_Subject",
    "Reply_Main_Dedicated_Rate",
    "Reply_Comprehensive_Pricing",
    "Reply_Attachment_Names",
    "Reply_Needs_Manual_Review",
    "Reply_Body_File",
    "Reply_Source_Tag",
]

WAVE_PRICING_FIELDS = [
    "Mail1_Pricing_Excerpt",
    "Mail2_Pricing_Excerpt",
    "Mail3_Pricing_Excerpt",
    "Pricing_Effective_Wave",
    "Pricing_Change_Type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync reply recovery review tables into replied master.")
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--source-master-csv", help="Optional full master CSV used to append missing rows into replied master.")
    parser.add_argument("--review-csv", action="append", required=True, help="Repeat for each canonical review table.")
    parser.add_argument("--messages-csv", action="append", required=True, help="Repeat for each canonical full messages csv.")
    parser.add_argument("--preview-csv", required=True)
    parser.add_argument("--audit-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--source-tag", required=True)
    parser.add_argument("--allow-add-missing", action="store_true")
    parser.add_argument("--append-recovery-note", action="store_true")
    parser.add_argument("--write-master", action="store_true")
    return parser.parse_args()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_fieldnames(existing: List[str]) -> List[str]:
    fieldnames = list(existing)
    for field in TARGET_FIELDS + WAVE_PRICING_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    return fieldnames


def append_note(existing: str, note: str) -> str:
    existing = (existing or "").strip()
    note = (note or "").strip()
    if not note:
        return existing
    if not existing:
        return note
    if note in existing:
        return existing
    return existing + "\n" + note


def normalize_compare(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def infer_matched_wave(row: Dict[str, str], latest_review: Dict[str, str]) -> str:
    review_at = (latest_review.get("reply_at") or "").strip()
    if review_at and review_at == (row.get("Mail1_Reply_At") or "").strip():
        return "mail1"
    if review_at and review_at == (row.get("Mail2_Reply_At") or "").strip():
        return "mail2"
    if review_at and review_at == (row.get("Mail3_Reply_At") or "").strip():
        return "mail3"
    stage = (row.get("Reply_Stage") or "").strip().lower()
    if "mail2" in stage:
        return "mail2"
    if "mail3" in stage:
        return "mail3"
    if "mail1" in stage:
        return "mail1"
    return ""


def wave_excerpt_from_review(latest_review: Dict[str, str], matched_wave: str) -> str:
    if matched_wave not in {"mail1", "mail2", "mail3"}:
        return ""
    explicit = latest_review.get(f"{matched_wave.capitalize()}_Pricing_Excerpt", "")
    return (explicit or latest_review.get("价格原文摘录", "") or "").strip()


def apply_wave_pricing(row: Dict[str, str], latest_review: Dict[str, str], matched_wave: str) -> None:
    if matched_wave not in {"mail1", "mail2", "mail3"}:
        return
    prefix = matched_wave.capitalize()
    row[f"{prefix}_Pricing_Excerpt"] = wave_excerpt_from_review(latest_review, matched_wave)


def infer_change_type(current_excerpt: str, previous_wave: str, latest_review: Dict[str, str], matched_wave: str) -> str:
    new_excerpt = wave_excerpt_from_review(latest_review, matched_wave)
    if not new_excerpt:
        return ""
    if not current_excerpt:
        return "first_price_mail1" if matched_wave == "mail1" else "first_price_after_followup"
    if normalize_compare(current_excerpt) == normalize_compare(new_excerpt):
        if previous_wave and previous_wave != matched_wave:
            return f"confirmed_same_as_{previous_wave}"
        return "confirmed_same_as_current"
    if matched_wave in {"mail2", "mail3"} and previous_wave:
        return f"revised_from_{previous_wave}"
    if matched_wave in {"mail2", "mail3"}:
        return "revised_after_followup"
    return "revised_mail1"


def parse_reply_at(value: str) -> datetime:
    value = (value or "").strip()
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sort_key(row: Dict[str, str]) -> Tuple[datetime, str]:
    return (parse_reply_at(row.get("reply_at", "")), row.get("message_id", ""))


def aggregate_source(review_paths: List[Path], message_paths: List[Path], source_tag: str) -> Tuple[Dict[str, Dict[str, str]], Dict[str, List[str]], Counter]:
    reviews_by_account: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    messages_by_account: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    duplicate_counter: Counter = Counter()

    for path in review_paths:
        for row in read_csv_rows(path):
            account_id = (row.get("账号ID") or "").strip()
            if not account_id:
                continue
            reviews_by_account[account_id].append(row)
            duplicate_counter[account_id] += 1

    for path in message_paths:
        for row in read_csv_rows(path):
            account_id = (row.get("账号ID") or "").strip()
            if not account_id:
                continue
            messages_by_account[account_id].append(row)

    aggregated: Dict[str, Dict[str, str]] = {}
    issues: Dict[str, List[str]] = defaultdict(list)
    for account_id, review_rows in reviews_by_account.items():
        message_rows = messages_by_account.get(account_id, [])
        if not message_rows:
            issues[account_id].append("missing_messages")
            continue

        latest_review = max(review_rows, key=lambda row: parse_reply_at(row.get("reply_at", "")))
        latest_message = max(message_rows, key=sort_key)
        thread_ids = []
        seen_threads = set()
        for message in sorted(message_rows, key=sort_key):
            thread_id = (message.get("thread_id") or "").strip()
            if thread_id and thread_id not in seen_threads:
                seen_threads.add(thread_id)
                thread_ids.append(thread_id)

        attachment_names = []
        for message in message_rows:
            raw_names = (message.get("attachment_names") or "").strip()
            if raw_names:
                attachment_names.extend([name.strip() for name in raw_names.split("|") if name.strip()])
        if not attachment_names and latest_review.get("attachment_names"):
            attachment_names.extend([name.strip() for name in latest_review["attachment_names"].split("|") if name.strip()])

        aggregated[account_id] = {
            "Reply_Status": "replied",
            "Reply_Contact_Email": latest_review.get("from_email", ""),
            "Reply_Thread_Count": str(len(thread_ids)),
            "Reply_Message_Count": str(len(message_rows)),
            "Reply_Thread_IDs": " | ".join(thread_ids),
            "Reply_Last_At": latest_review.get("reply_at", latest_message.get("reply_at", "")),
            "Reply_Last_Subject": latest_review.get("subject", latest_message.get("subject", "")),
            "Reply_Main_Dedicated_Rate": latest_review.get("main_dedicated_rate", ""),
            "Reply_Comprehensive_Pricing": latest_review.get("综合报价", ""),
            "Reply_Pricing_Excerpt": latest_review.get("价格原文摘录", ""),
            "Reply_Attachment_Names": " | ".join(dict.fromkeys(attachment_names)),
            "Reply_Needs_Manual_Review": latest_review.get("needs_manual_review", ""),
            "Reply_Body_File": latest_review.get("body_file", latest_message.get("body_file", "")),
            "Reply_Source_Tag": source_tag,
        }
        if duplicate_counter[account_id] > 1:
            issues[account_id].append(f"duplicate_review_rows={duplicate_counter[account_id]}")

    return aggregated, issues, duplicate_counter


def main() -> None:
    args = parse_args()
    master_path = Path(args.master_csv)
    review_paths = [Path(p) for p in args.review_csv]
    message_paths = [Path(p) for p in args.messages_csv]

    source_map, issues, duplicate_counter = aggregate_source(review_paths, message_paths, args.source_tag)
    master_rows = read_csv_rows(master_path)
    fieldnames = ensure_fieldnames(list(master_rows[0].keys()) if master_rows else [])
    source_master_rows = read_csv_rows(Path(args.source_master_csv)) if args.source_master_csv else []
    source_master_index = {(row.get("账号ID") or "").strip(): row for row in source_master_rows}

    preview_rows: List[Dict[str, str]] = []
    audit_rows: List[Dict[str, str]] = []
    updated_rows = 0
    unchanged_rows = 0
    conflicting_rows = 0
    matched_rows = 0

    for row in master_rows:
        account_id = (row.get("账号ID") or "").strip()
        source = source_map.get(account_id)
        if not source:
            continue
        matched_rows += 1
        diff_fields = []
        for field in TARGET_FIELDS:
            if (row.get(field, "") or "") != (source.get(field, "") or ""):
                diff_fields.append(field)
        preview = {
            "账号ID": account_id,
            "频道/作者名称": row.get("频道/作者名称", ""),
            "changed_fields": " | ".join(diff_fields),
        }
        for field in TARGET_FIELDS:
            preview[f"old::{field}"] = row.get(field, "")
            preview[f"new::{field}"] = source.get(field, "")
        preview_rows.append(preview)

        if diff_fields:
            updated_rows += 1
            if any((row.get(field, "") or "").strip() for field in diff_fields):
                conflicting_rows += 1
        else:
            unchanged_rows += 1

        previous_excerpt = (row.get("Reply_Pricing_Excerpt") or "").strip()
        previous_wave = (row.get("Pricing_Effective_Wave") or "").strip()
        for field in TARGET_FIELDS:
            if args.write_master:
                row[field] = source.get(field, "")
        matched_wave = infer_matched_wave(row, source)
        if args.write_master:
            apply_wave_pricing(row, source, matched_wave)
            if matched_wave:
                row["Pricing_Effective_Wave"] = matched_wave
                row["Pricing_Change_Type"] = infer_change_type(previous_excerpt, previous_wave, source, matched_wave)
        if args.write_master and args.append_recovery_note:
            note = f"[recovery] source={args.source_tag}"
            if source.get("Reply_Main_Dedicated_Rate", ""):
                note += " | pricing updated"
            row["Ops_Notes"] = append_note(row.get("Ops_Notes", ""), note)

    master_ids = {(row.get("账号ID") or "").strip() for row in master_rows}
    unmatched = sorted(account_id for account_id in source_map if account_id not in master_ids)
    for account_id in unmatched:
        if args.allow_add_missing and account_id in source_master_index:
            if args.write_master:
                base_row = {field: "" for field in fieldnames}
                for key, value in source_master_index[account_id].items():
                    if key in base_row:
                        base_row[key] = value
                for field in TARGET_FIELDS:
                    base_row[field] = source_map[account_id].get(field, "")
                master_rows.append(base_row)
            audit_rows.append(
                {
                    "issue_type": "append_from_source_master",
                    "账号ID": account_id,
                    "频道/作者名称": source_master_index[account_id].get("频道/作者名称", ""),
                    "details": "Missing in replied master; appended from source master and enriched with reply fields." if args.write_master else "Missing in replied master; eligible to append from source master.",
                }
            )
        else:
            audit_rows.append(
                {
                    "issue_type": "missing_master_row",
                    "账号ID": account_id,
                    "频道/作者名称": "",
                    "details": "Source row exists in canonical review tables but target replied master has no matching 账号ID.",
                }
            )

    for account_id, count in sorted(duplicate_counter.items()):
        if count > 1:
            audit_rows.append(
                {
                    "issue_type": "duplicate_review_rows",
                    "账号ID": account_id,
                    "频道/作者名称": "",
                    "details": f"Found {count} review rows across provided review tables; latest reply row used for sync.",
                }
            )

    for account_id, issue_list in sorted(issues.items()):
        for issue in issue_list:
            if issue.startswith("duplicate_review_rows"):
                continue
            audit_rows.append(
                {
                    "issue_type": issue,
                    "账号ID": account_id,
                    "频道/作者名称": "",
                    "details": issue,
                }
            )

    preview_fieldnames = ["账号ID", "频道/作者名称", "changed_fields"] + [f"{prefix}::{field}" for field in TARGET_FIELDS for prefix in ("old", "new")]
    audit_fieldnames = ["issue_type", "账号ID", "频道/作者名称", "details"]
    write_csv(Path(args.preview_csv), preview_rows, preview_fieldnames)
    write_csv(Path(args.audit_csv), audit_rows, audit_fieldnames)

    if args.write_master:
        write_csv(master_path, master_rows, fieldnames)

    summary = {
        "source_tag": args.source_tag,
        "review_tables": [str(path.resolve()) for path in review_paths],
        "message_tables": [str(path.resolve()) for path in message_paths],
        "matched_rows": matched_rows,
        "updated_rows": updated_rows,
        "unchanged_rows": unchanged_rows,
        "unmatched_rows": len(unmatched),
        "appended_rows": sum(1 for row in audit_rows if row["issue_type"] == "append_from_source_master"),
        "conflicting_rows": conflicting_rows,
        "duplicate_source_ids": {account_id: count for account_id, count in duplicate_counter.items() if count > 1},
        "unmatched_source_ids": unmatched,
        "write_master": bool(args.write_master),
        "master_csv": str(master_path.resolve()),
        "preview_csv": str(Path(args.preview_csv).resolve()),
        "audit_csv": str(Path(args.audit_csv).resolve()),
    }
    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
