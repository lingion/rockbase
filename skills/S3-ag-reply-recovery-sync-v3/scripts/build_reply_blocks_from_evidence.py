#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V3 reply block preview from unified evidence layer.")
    parser.add_argument("--master", required=True, help="Path to V3 master CSV.")
    parser.add_argument("--message-evidence-csv", required=True, help="Unified message evidence CSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for preview and summary outputs.")
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


def parse_reply_at(value: str) -> Tuple[float, str]:
    raw = (value or "").strip()
    if not raw:
        return 0.0, ""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.timestamp(), raw
    except Exception:
        return 0.0, raw


def format_block(reply_at: str, body_text: str) -> str:
    body_text = (body_text or "").strip()
    reply_at = (reply_at or "").strip()
    if not body_text:
        return ""
    if reply_at:
        return f"[{reply_at}]\n{body_text}"
    return body_text


def clean_for_block(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    evidence_path = Path(args.message_evidence_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_rows = read_rows(master_path)
    evidence_rows = read_rows(evidence_path)

    by_account: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        account_id = (row.get("账号ID") or "").strip()
        if not account_id:
            continue
        cleaned = clean_for_block(row.get("body_text_clean") or "")
        if not cleaned:
            continue
        row = dict(row)
        row["_cleaned"] = cleaned
        row["_ts"] = str(parse_reply_at(row.get("reply_at") or "")[0])
        by_account[account_id].append(row)

    preview_rows: List[Dict[str, str]] = []
    changed_rows = 0

    for row in master_rows:
        account_id = (row.get("账号ID") or "").strip()
        if not account_id:
            preview_rows.append(dict(row))
            continue

        candidates = sorted(
            by_account.get(account_id, []),
            key=lambda item: (float(item.get("_ts") or 0.0), item.get("message_id") or ""),
        )

        new_row = dict(row)
        reply_count = len(candidates)
        if "Reply_Count" not in new_row:
            new_row["Reply_Count"] = ""
        new_row["Reply_Count"] = str(reply_count) if reply_count else ""

        blocks = [""] * 5
        for idx, item in enumerate(candidates[:5]):
            blocks[idx] = format_block(item.get("reply_at") or "", item.get("_cleaned") or "")

        for idx in range(5):
            key = f"mail{idx+1}_reply_block"
            old = (row.get(key) or "").strip()
            new = (blocks[idx] or "").strip()
            new_row[key] = new
            if old != new:
                changed_rows += 1

        if candidates:
            latest = candidates[-1]
            latest_reply_at = latest.get("reply_at") or ""
            if latest_reply_at:
                new_row["Reply_Last_At"] = latest_reply_at
            if latest.get("message_id"):
                new_row["Reply_Last_Message_ID"] = latest.get("message_id") or row.get("Reply_Last_Message_ID", "")
            if latest.get("subject"):
                new_row["Reply_Last_Subject"] = latest.get("subject") or row.get("Reply_Last_Subject", "")

        preview_rows.append(new_row)

    fieldnames = list(preview_rows[0].keys()) if preview_rows else []
    if "Reply_Count" not in fieldnames:
        insert_at = fieldnames.index("Reply_Thread_ID") if "Reply_Thread_ID" in fieldnames else len(fieldnames)
        fieldnames.insert(insert_at, "Reply_Count")

    preview_csv = output_dir / "reply_blocks_rebuild_preview.csv"
    write_rows(preview_csv, preview_rows, fieldnames)

    summary = {
        "master_rows": len(master_rows),
        "evidence_rows": len(evidence_rows),
        "accounts_with_evidence": len(by_account),
        "rows_with_reply_count": sum(1 for row in preview_rows if (row.get("Reply_Count") or "").strip()),
        "mail1_filled": sum(1 for row in preview_rows if (row.get("mail1_reply_block") or "").strip()),
        "mail2_filled": sum(1 for row in preview_rows if (row.get("mail2_reply_block") or "").strip()),
        "mail3_filled": sum(1 for row in preview_rows if (row.get("mail3_reply_block") or "").strip()),
        "mail4_filled": sum(1 for row in preview_rows if (row.get("mail4_reply_block") or "").strip()),
        "mail5_filled": sum(1 for row in preview_rows if (row.get("mail5_reply_block") or "").strip()),
        "changed_cells_estimate": changed_rows,
        "preview_csv": str(preview_csv.resolve()),
    }
    (output_dir / "reply_blocks_rebuild_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
