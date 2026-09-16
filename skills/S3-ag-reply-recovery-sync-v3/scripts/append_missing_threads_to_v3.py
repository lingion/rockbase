#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append missing preview thread rows into V3 master.")
    parser.add_argument("--master", required=True)
    parser.add_argument("--preview-csv", required=True)
    parser.add_argument("--message-evidence-csv", required=True)
    parser.add_argument("--source-corestar", required=True)
    parser.add_argument("--source-rockbase", required=True)
    parser.add_argument("--hub-root", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def clean_reply_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return ""
    text = re.sub(r"(?m)^\s*>.*$", "", text)
    cut_patterns = [
        r"(?im)^\s*on .+ wrote:\s*$",
        r"(?im)^\s*from:\s*.+$",
        r"(?im)^\s*sent:\s*.+$",
        r"(?im)^\s*to:\s*.+$",
        r"(?im)^\s*subject:\s*.+$",
        r"(?im)^[-_]{2,}\s*$",
    ]
    for pattern in cut_patterns:
        match = re.search(pattern, text)
        if match:
            text = text[: match.start()]
            break
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def parse_reply_at(value: str) -> float:
    raw = (value or "").strip()
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except Exception:
        return 0.0


def format_block(reply_at: str, body_text: str) -> str:
    body_text = (body_text or "").strip()
    if not body_text:
        return ""
    reply_at = (reply_at or "").strip()
    return f"[{reply_at}]\n{body_text}" if reply_at else body_text


def load_sources(corestar_path: Path, rockbase_path: Path) -> Dict[str, Dict[str, str]]:
    source_map: Dict[str, Dict[str, str]] = {}
    for tag, path in [("Corestar", corestar_path), ("Rockbase", rockbase_path)]:
        for row in read_rows(path):
            account_id = (row.get("账号ID") or "").strip()
            if not account_id:
                continue
            if account_id not in source_map:
                source_map[account_id] = {
                    "Source_Tag": tag,
                    "账号ID": account_id,
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "平台": row.get("平台", ""),
                    "多平台标记": row.get("多平台标记", ""),
                    "账号链接": row.get("账号链接", ""),
                    "语言": row.get("语言", ""),
                    "Reply_Contact_Email": row.get("联系方式", ""),
                }
    return source_map


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    preview_path = Path(args.preview_csv)
    evidence_path = Path(args.message_evidence_csv)
    output_dir = Path(args.output_dir)
    hub_root = Path(args.hub_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_rows = read_rows(master_path)
    preview_rows = read_rows(preview_path)
    evidence_rows = read_rows(evidence_path)
    source_map = load_sources(Path(args.source_corestar), Path(args.source_rockbase))
    ledger_path = hub_root / "06-ledgers" / "reply_message_ledger.csv"
    ledger_rows = read_rows(ledger_path) if ledger_path.exists() else []
    ledger_by_msg = {(r.get("message_id") or "").strip(): r for r in ledger_rows if (r.get("message_id") or "").strip()}

    fieldnames = list(master_rows[0].keys()) if master_rows else []
    for extra_field in [
        "Reply_Status",
        "Reply_Needs_Manual_Review",
        "Reply_Analysis",
        "Manual_Review_Reason",
        "Manual_Review_Focus",
    ]:
        if extra_field not in fieldnames:
            fieldnames.append(extra_field)
    master_threads = {r.get("Reply_Thread_ID", "").strip() for r in master_rows if r.get("Reply_Thread_ID", "").strip()}
    master_by_account = {r.get("账号ID", "").strip(): r for r in master_rows if r.get("账号ID", "").strip()}

    preview_new = [
        r for r in preview_rows
        if (r.get("Reply_Thread_ID") or "").strip() and (r.get("Reply_Thread_ID") or "").strip() not in master_threads
    ]
    preview_new_by_key = {
        ((r.get("账号ID") or "").strip(), (r.get("Reply_Thread_ID") or "").strip()): r
        for r in preview_new
        if (r.get("账号ID") or "").strip() and (r.get("Reply_Thread_ID") or "").strip()
    }

    evidence_by_key: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        key = ((row.get("账号ID") or "").strip(), (row.get("Reply_Thread_ID") or "").strip())
        if all(key):
            evidence_by_key[key].append(row)

    appended_rows: List[Dict[str, str]] = []
    audit_rows: List[Dict[str, str]] = []

    for key, preview in preview_new_by_key.items():
        account_id, thread_id = key
        existing = master_by_account.get(account_id)
        base = dict(existing) if existing else {k: "" for k in fieldnames}
        source = source_map.get(account_id, {})

        rows = sorted(
            evidence_by_key.get(key, []),
            key=lambda r: (parse_reply_at(r.get("reply_at") or ""), r.get("message_id") or ""),
        )
        if not rows:
            latest_msg = (preview.get("Latest_Inbound_Message_ID") or "").strip()
            ledger = ledger_by_msg.get(latest_msg, {})
            body_rel = (preview.get("Reply_Body_File") or "").strip()
            body_abs = hub_root / body_rel if body_rel else None
            body_text = ""
            if body_abs and body_abs.exists():
                body_text = clean_reply_text(body_abs.read_text(encoding="utf-8", errors="replace"))
            if not body_text:
                audit_rows.append(
                    {
                        "账号ID": account_id,
                        "Reply_Thread_ID": thread_id,
                        "action": "skipped_no_evidence",
                        "reason": "no unified evidence rows and no fallback body",
                    }
                )
                continue
            rows = [
                {
                    "账号ID": account_id,
                    "Reply_Thread_ID": thread_id,
                    "message_id": latest_msg,
                    "reply_at": ledger.get("reply_at", ""),
                    "from_email": ledger.get("from_email", ""),
                    "subject": "",
                    "body_text_clean": body_text,
                }
            ]

        latest = rows[-1]
        blocks = [""] * 5
        for idx, row in enumerate(rows[:5]):
            blocks[idx] = format_block(row.get("reply_at") or "", row.get("body_text_clean") or "")

        new_row = dict(base)
        for k in fieldnames:
            new_row.setdefault(k, "")

        for k in ["Source_Tag", "账号ID", "频道/作者名称", "平台", "多平台标记", "账号链接", "语言", "Reply_Contact_Email"]:
            if source.get(k):
                new_row[k] = source.get(k, "")

        if existing:
            for k in ["Source_Tag", "频道/作者名称", "平台", "多平台标记", "账号链接", "语言", "Reply_Contact_Email", "Owner", "Priority"]:
                if existing.get(k):
                    new_row[k] = existing.get(k, "")

        if not new_row.get("Reply_Contact_Email"):
            new_row["Reply_Contact_Email"] = latest.get("from_email", "")

        new_row["账号ID"] = account_id
        new_row["Reply_Thread_ID"] = thread_id
        new_row["Reply_Count"] = str(len(rows))
        for idx in range(5):
            new_row[f"mail{idx+1}_reply_block"] = blocks[idx]
        new_row["Reply_Last_At"] = latest.get("reply_at", "")
        new_row["Reply_Last_Message_ID"] = latest.get("message_id", "")
        new_row["Reply_Last_Subject"] = latest.get("subject", "")
        new_row["Latest_Inbound_Message_ID"] = preview.get("Latest_Inbound_Message_ID", "") or latest.get("message_id", "")
        new_row["Latest_Inbound_InReplyTo"] = preview.get("Latest_Inbound_InReplyTo", "")
        new_row["Reply_Stream"] = preview.get("Reply_Stream", "") or "Outreach"
        new_row["Reply_Stage"] = preview.get("Reply_Stage", "") or "manual_review"
        new_row["Reply_Analysis"] = preview.get("Reply_Analysis", "")
        new_row["Reply_Body_File"] = preview.get("Reply_Body_File", "")
        new_row["Pipeline_Stage"] = existing.get("Pipeline_Stage", "") if existing else "M1_3_Replied_Review"
        new_row["Sort_Bucket"] = existing.get("Sort_Bucket", "") if existing else "2_replied_need_review"
        new_row["Reply_Status"] = existing.get("Reply_Status", "") if existing else ""
        new_row["Reply_Needs_Manual_Review"] = "yes"
        if not new_row.get("Manual_Review_Reason"):
            new_row["Manual_Review_Reason"] = "new_thread_from_7d_recovery"
        if not new_row.get("Manual_Review_Focus"):
            new_row["Manual_Review_Focus"] = "reply_recovery_append"
        new_row["Capture_Run_ID"] = "2026-03-27_7d_segmented_recovery"
        new_row["Capture_At"] = "2026-03-27"

        appended_rows.append(new_row)
        audit_rows.append(
            {
                "账号ID": account_id,
                "Reply_Thread_ID": thread_id,
                "action": "appended",
                "reason": "missing_thread_in_master",
                "used_existing_account_template": "yes" if existing else "no",
                "used_source_bootstrap": "yes" if source else "no",
                "reply_count": str(len(rows)),
            }
        )

    section_rows = [r for r in master_rows if not (r.get("账号ID") or "").strip()]
    non_section_rows = [r for r in master_rows if (r.get("账号ID") or "").strip()]
    final_rows = non_section_rows + appended_rows + section_rows

    final_master_path = output_dir / "master_with_appended_threads_preview.csv"
    write_rows(final_master_path, final_rows, fieldnames)
    audit_path = output_dir / "append_missing_threads_audit.csv"
    audit_fields = []
    if audit_rows:
        seen_fields = set()
        for row in audit_rows:
            for key in row.keys():
                if key not in seen_fields:
                    seen_fields.add(key)
                    audit_fields.append(key)
    else:
        audit_fields = ["账号ID", "Reply_Thread_ID", "action", "reason"]
    write_rows(audit_path, audit_rows, audit_fields)

    summary = {
        "master_rows_before": len(master_rows),
        "preview_new_threads": len(preview_new_by_key),
        "appended_rows": len(appended_rows),
        "audit_rows": len(audit_rows),
        "master_rows_after_preview": len(final_rows),
        "final_preview_csv": str(final_master_path.resolve()),
        "audit_csv": str(audit_path.resolve()),
    }
    (output_dir / "append_missing_threads_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
