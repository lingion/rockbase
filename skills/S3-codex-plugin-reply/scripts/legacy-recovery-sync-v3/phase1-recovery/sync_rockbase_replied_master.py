#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
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
    parser = argparse.ArgumentParser(description="Sync Rockbase last-24h reply recovery into Rockbase-Replied-KOL.")
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--review-csv", action="append", required=True)
    parser.add_argument("--messages-csv", action="append", required=True)
    parser.add_argument("--supplement-csv", action="append", default=[])
    parser.add_argument("--preview-csv", required=True)
    parser.add_argument("--audit-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--source-tag", required=True)
    parser.add_argument("--append-recovery-note", action="store_true")
    parser.add_argument("--write-master", action="store_true")
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def parse_reply_at(value: str) -> datetime:
    value = (value or "").strip()
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sort_key(row: Dict[str, str]) -> Tuple[datetime, str]:
    return (parse_reply_at(row.get("reply_at", "")), row.get("message_id", ""))


def normalize_subject(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"^(re|fw|fwd)\s*:\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def ensure_fieldnames(existing: List[str]) -> List[str]:
    fieldnames = list(existing)
    if "Tier" not in fieldnames:
        fieldnames.append("Tier")
    for field in TARGET_FIELDS + WAVE_PRICING_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    return fieldnames


def infer_matched_wave(row: Dict[str, str], payload: Dict[str, str]) -> str:
    reply_at = (payload.get("Reply_Last_At") or "").strip()
    if reply_at and reply_at == (row.get("Mail1_Reply_At") or "").strip():
        return "mail1"
    if reply_at and reply_at == (row.get("Mail2_Reply_At") or "").strip():
        return "mail2"
    if reply_at and reply_at == (row.get("Mail3_Reply_At") or "").strip():
        return "mail3"
    stage = (row.get("Reply_Stage") or "").strip().lower()
    if "mail2" in stage:
        return "mail2"
    if "mail3" in stage:
        return "mail3"
    if "mail1" in stage:
        return "mail1"
    return ""


def wave_excerpt_from_payload(payload: Dict[str, str], matched_wave: str) -> str:
    if matched_wave not in {"mail1", "mail2", "mail3"}:
        return ""
    explicit = payload.get(f"{matched_wave.capitalize()}_Pricing_Excerpt", "")
    return (explicit or payload.get("Reply_Pricing_Excerpt", "") or "").strip()


def apply_wave_pricing(row: Dict[str, str], payload: Dict[str, str], matched_wave: str) -> None:
    if matched_wave not in {"mail1", "mail2", "mail3"}:
        return
    prefix = matched_wave.capitalize()
    row[f"{prefix}_Pricing_Excerpt"] = wave_excerpt_from_payload(payload, matched_wave)


def infer_change_type(current_excerpt: str, previous_wave: str, payload: Dict[str, str], matched_wave: str) -> str:
    new_excerpt = wave_excerpt_from_payload(payload, matched_wave)
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


def build_master_indexes(master_rows: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, List[Dict[str, str]]]]:
    by_id = {}
    by_email = defaultdict(list)
    for row in master_rows:
        account_id = (row.get("账号ID") or "").strip()
        email = (row.get("联系方式") or "").strip().lower()
        if account_id:
            by_id[account_id] = row
        if email:
            by_email[email].append(row)
    return by_id, by_email


def resolve_account_id(message_row: Dict[str, str], master_email_index: Dict[str, List[Dict[str, str]]]) -> Tuple[str, str]:
    email = (message_row.get("from_email") or "").strip().lower()
    subject = normalize_subject(message_row.get("subject", ""))
    candidates = master_email_index.get(email, [])
    if not candidates:
        ids = [item.strip() for item in (message_row.get("账号ID") or "").split("|") if item.strip()]
        if len(ids) == 1:
            return ids[0], "single_message_account_id"
        return "", "unresolved_no_master_email_match"
    if len(candidates) == 1:
        return (candidates[0].get("账号ID") or "").strip(), "unique_email_match"

    exact_matches = []
    for candidate in candidates:
        candidate_subject = normalize_subject(candidate.get("Email_Subject", ""))
        if candidate_subject and candidate_subject == subject:
            exact_matches.append(candidate)
    if len(exact_matches) == 1:
        return (exact_matches[0].get("账号ID") or "").strip(), "shared_email_exact_subject_match"

    fuzzy_matches = []
    for candidate in candidates:
        name = (candidate.get("频道/作者名称") or "").strip().lower()
        if name and name in subject:
            fuzzy_matches.append(candidate)
    if len(fuzzy_matches) == 1:
        return (fuzzy_matches[0].get("账号ID") or "").strip(), "shared_email_name_in_subject"

    return "", "ambiguous_shared_email"


def aggregate_account_payload(
    account_id: str,
    message_rows: List[Dict[str, str]],
    review_map: Dict[Tuple[str, str, str], Dict[str, str]],
    source_tag: str,
) -> Dict[str, str]:
    message_rows = sorted(message_rows, key=sort_key)
    latest_message = message_rows[-1]
    latest_review = review_map.get(
        (
            (latest_message.get("from_email") or "").strip().lower(),
            latest_message.get("subject", ""),
            latest_message.get("reply_at", ""),
        ),
        {},
    )

    thread_ids = []
    seen = set()
    attachment_names = []
    for row in message_rows:
        thread_id = (row.get("thread_id") or "").strip()
        if thread_id and thread_id not in seen:
            seen.add(thread_id)
            thread_ids.append(thread_id)
        raw_names = (row.get("attachment_names") or "").strip()
        if raw_names:
            attachment_names.extend([x.strip() for x in raw_names.split(";") if x.strip()])

    return {
        "Reply_Status": "replied",
        "Reply_Contact_Email": latest_message.get("from_email", ""),
        "Reply_Thread_Count": str(len(thread_ids)),
        "Reply_Message_Count": str(len(message_rows)),
        "Reply_Thread_IDs": " | ".join(thread_ids),
        "Reply_Last_At": latest_review.get("reply_at", latest_message.get("reply_at", "")),
        "Reply_Last_Subject": latest_review.get("subject", latest_message.get("subject", "")),
        "Reply_Main_Dedicated_Rate": latest_review.get("main_dedicated_rate", ""),
        "Reply_Comprehensive_Pricing": latest_review.get("综合报价", ""),
        "Reply_Pricing_Excerpt": latest_review.get("价格原文摘录", ""),
        "Reply_Attachment_Names": " | ".join(dict.fromkeys(attachment_names)),
        "Reply_Needs_Manual_Review": latest_review.get("needs_manual_review", latest_message.get("needs_manual_review", "")),
        "Reply_Body_File": latest_review.get("body_file", latest_message.get("body_file", "")),
        "Reply_Source_Tag": source_tag,
    }


def build_supplement_index(paths: List[Path]) -> Dict[str, Dict[str, str]]:
    index = {}
    for path in paths:
        for row in read_rows(path):
            account_id = (row.get("账号ID") or "").strip()
            if account_id and account_id not in index:
                index[account_id] = row
    return index


def base_row_from_message(account_id: str, message_rows: List[Dict[str, str]]) -> Dict[str, str]:
    latest = sorted(message_rows, key=sort_key)[-1]
    return {
        "来源产品": "Rockbase",
        "来源文件": "2026-03-17_last24h_recovery",
        "账号ID": account_id,
        "频道/作者名称": latest.get("频道/作者名称", ""),
        "平台": latest.get("平台", ""),
        "账号链接": "",
        "联系方式": latest.get("from_email", ""),
        "Greeting_Name": "",
        "Email_Subject": latest.get("subject", ""),
        "Email_Content V1": "",
    }


def main() -> None:
    args = parse_args()
    master_path = Path(args.master_csv)
    master_rows = read_rows(master_path)
    base_fieldnames = list(master_rows[0].keys()) if master_rows else []
    fieldnames = ensure_fieldnames(base_fieldnames)
    for row in master_rows:
        row.setdefault("Tier", "Tie2")
        for field in TARGET_FIELDS + WAVE_PRICING_FIELDS:
            row.setdefault(field, "")

    master_id_index, master_email_index = build_master_indexes(master_rows)
    supplement_index = build_supplement_index([Path(p) for p in args.supplement_csv])

    resolved_messages = []
    audit_rows = []
    for path in [Path(p) for p in args.messages_csv]:
        for row in read_rows(path):
            account_id, reason = resolve_account_id(row, master_email_index)
            row["_resolved_account_id"] = account_id
            row["_resolution_reason"] = reason
            resolved_messages.append(row)
            if not account_id:
                audit_rows.append(
                    {
                        "issue_type": "ambiguous_message" if "ambiguous" in reason else "unresolved_message",
                        "账号ID": row.get("账号ID", ""),
                        "频道/作者名称": row.get("频道/作者名称", ""),
                        "details": f"{reason} | from_email={row.get('from_email','')} | subject={row.get('subject','')}",
                    }
                )

    review_map = {}
    for path in [Path(p) for p in args.review_csv]:
        for row in read_rows(path):
            key = (
                (row.get("from_email") or "").strip().lower(),
                row.get("subject", ""),
                row.get("reply_at", ""),
            )
            review_map[key] = row

    messages_by_account = defaultdict(list)
    for row in resolved_messages:
        account_id = row.get("_resolved_account_id", "")
        if account_id:
            messages_by_account[account_id].append(row)

    payload_by_account = {
        account_id: aggregate_account_payload(account_id, rows, review_map, args.source_tag)
        for account_id, rows in messages_by_account.items()
    }

    preview_rows = []
    matched_ids = set(payload_by_account)
    tie1_rows = []
    kept_rows = []

    for row in master_rows:
        account_id = (row.get("账号ID") or "").strip()
        if account_id in payload_by_account:
            updated = dict(row)
            updated["Tier"] = "Tie1"
            previous_excerpt = (row.get("Reply_Pricing_Excerpt") or "").strip()
            previous_wave = (row.get("Pricing_Effective_Wave") or "").strip()
            for field, value in payload_by_account[account_id].items():
                updated[field] = value
            matched_wave = infer_matched_wave(updated, payload_by_account[account_id])
            apply_wave_pricing(updated, payload_by_account[account_id], matched_wave)
            if matched_wave:
                updated["Pricing_Effective_Wave"] = matched_wave
                updated["Pricing_Change_Type"] = infer_change_type(previous_excerpt, previous_wave, payload_by_account[account_id], matched_wave)
            if args.write_master and args.append_recovery_note:
                note = f"[recovery] source={args.source_tag}"
                if payload_by_account[account_id].get("Reply_Main_Dedicated_Rate", ""):
                    note += " | pricing updated"
                updated["Ops_Notes"] = append_note(updated.get("Ops_Notes", ""), note)
            tie1_rows.append(updated)
            diff_fields = [field for field in ["Tier"] + TARGET_FIELDS if (row.get(field, "") or "") != (updated.get(field, "") or "")]
            preview_rows.append(
                {
                    "账号ID": account_id,
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "action": "move_existing_to_tie1",
                    "changed_fields": " | ".join(diff_fields),
                }
            )
        else:
            kept = dict(row)
            kept.setdefault("Tier", "Tie2")
            kept_rows.append(kept)

    for account_id, payload in payload_by_account.items():
        if account_id in master_id_index:
            continue
        base = supplement_index.get(account_id) or base_row_from_message(account_id, messages_by_account[account_id])
        new_row = {field: "" for field in fieldnames}
        for key, value in base.items():
            if key in new_row:
                new_row[key] = value
        new_row["Tier"] = "Tie1"
        for field, value in payload.items():
            new_row[field] = value
        matched_wave = infer_matched_wave(new_row, payload)
        apply_wave_pricing(new_row, payload, matched_wave)
        if matched_wave:
            new_row["Pricing_Effective_Wave"] = matched_wave
            new_row["Pricing_Change_Type"] = infer_change_type("", "", payload, matched_wave)
        tie1_rows.append(new_row)
        preview_rows.append(
            {
                "账号ID": account_id,
                "频道/作者名称": new_row.get("频道/作者名称", ""),
                "action": "append_new_tie1",
                "changed_fields": "Tier | " + " | ".join(TARGET_FIELDS),
            }
        )
        audit_rows.append(
            {
                "issue_type": "append_new_tie1",
                "账号ID": account_id,
                "频道/作者名称": new_row.get("频道/作者名称", ""),
                "details": "Reply hit belongs to Rockbase but was not present in Rockbase-Replied-KOL; appended into Tie1 section.",
            }
        )

    final_rows = kept_rows + tie1_rows

    preview_fields = ["账号ID", "频道/作者名称", "action", "changed_fields"]
    audit_fields = ["issue_type", "账号ID", "频道/作者名称", "details"]
    write_rows(Path(args.preview_csv), preview_rows, preview_fields)
    write_rows(Path(args.audit_csv), audit_rows, audit_fields)
    if args.write_master:
        write_rows(master_path, final_rows, fieldnames)

    summary = {
        "source_tag": args.source_tag,
        "matched_existing_rows": sum(1 for row in preview_rows if row["action"] == "move_existing_to_tie1"),
        "appended_new_tie1_rows": sum(1 for row in preview_rows if row["action"] == "append_new_tie1"),
        "kept_tie2_rows": len(kept_rows),
        "final_rows": len(final_rows),
        "ambiguous_or_unresolved_messages": sum(1 for row in audit_rows if row["issue_type"] in {"ambiguous_message", "unresolved_message"}),
        "write_master": bool(args.write_master),
        "master_csv": str(master_path.resolve()),
        "preview_csv": str(Path(args.preview_csv).resolve()),
        "audit_csv": str(Path(args.audit_csv).resolve()),
    }
    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
