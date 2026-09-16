#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ANNABEL_HINTS = [
    "i'm annabel from rockbase agency",
    "we are currently finalizing our premium creator shortlist",
    "current rates for all channels",
    "thank you for sharing your rates",
    "we do see a strong fit",
    "would you be open to sharing your best agency rate",
    "budget can vary depending on the format",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified cleaned evidence layer from recovery preview + fetched threads + attachment extraction.")
    parser.add_argument("--preview-csv", required=True)
    parser.add_argument("--hub-root", required=True)
    parser.add_argument("--attachment-root", required=True)
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


def normalize_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()


def clean_reply_text(text: str) -> Tuple[str, str]:
    original = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not original.strip():
        return "", "empty"

    text = original
    text = re.sub(r"(?m)^\s*>.*$", "", text)

    cut_patterns = [
        r"(?im)^\s*on .+ wrote:\s*$",
        r"(?im)^\s*from:\s*.+$",
        r"(?im)^\s*sent:\s*.+$",
        r"(?im)^\s*to:\s*.+$",
        r"(?im)^\s*subject:\s*.+$",
        r"(?im)^\s*20\d{2}.+<steven\.li2009@gmail\.com>:\s*$",
        r"(?im)^\s*steven\.li2009@gmail\.com\s*$",
        r"(?im)^\s*rockbase agency\s*$",
        r"(?im)^[-_]{2,}\s*$",
    ]
    cut_reason = "kept"
    for pattern in cut_patterns:
        match = re.search(pattern, text)
        if match:
            text = text[: match.start()]
            cut_reason = f"cut:{pattern}"
            break

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    lowered = text.lower()
    if any(hint in lowered for hint in ANNABEL_HINTS) and len(text.splitlines()) <= 18:
        return "", "filtered_outbound_like"

    return text, cut_reason


def summarize_text(text: str, limit: int = 280) -> str:
    text = normalize_ws(text)
    return text[: limit - 3] + "..." if len(text) > limit else text


def load_attachment_reports(root: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for report in sorted(root.glob("chunk_*/pipeline/attachment_extract/attachment_extraction_report.csv")):
        rows.extend(read_rows(report))
    return rows


def load_thread_fetch_rows(root: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for report in sorted(root.glob("chunk_*/pipeline/thread_fetch/reply_batch_full_first*.csv")):
        rows.extend(read_rows(report))
    return rows


def main() -> None:
    args = parse_args()
    preview_csv = Path(args.preview_csv)
    hub_root = Path(args.hub_root)
    attachment_root = Path(args.attachment_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    preview_rows = read_rows(preview_csv)
    fetch_rows = load_thread_fetch_rows(attachment_root)
    attachment_rows = load_attachment_reports(attachment_root)

    preview_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in preview_rows:
        key = ((row.get("账号ID") or "").strip(), (row.get("Reply_Thread_ID") or "").strip())
        if all(key):
            preview_by_key[key] = row

    attachment_by_message: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in attachment_rows:
        attachment_by_message[(row.get("message_id") or "").strip()].append(row)

    message_rows: List[Dict[str, str]] = []
    seen_message_keys: set[Tuple[str, str, str]] = set()
    contact_rollups: Dict[str, Dict[str, object]] = {}

    def append_message_row(payload: Dict[str, str]) -> None:
        account_id = (payload.get("账号ID") or "").strip()
        thread_id = (payload.get("Reply_Thread_ID") or payload.get("thread_id") or "").strip()
        message_id = (payload.get("message_id") or "").strip()
        dedupe_key = (account_id, thread_id, message_id or payload.get("reply_at", ""))
        if dedupe_key in seen_message_keys:
            return
        seen_message_keys.add(dedupe_key)

        body_text = payload.get("body_text_raw") or ""
        cleaned_body, clean_reason = clean_reply_text(body_text)
        attachment_excerpt = payload.get("attachment_evidence_excerpt") or ""
        attachment_names = payload.get("attachment_names") or ""
        attachment_count = payload.get("attachment_count") or "0"
        attachment_text_count = payload.get("attachment_text_count") or "0"
        body_file_fetch = payload.get("body_file_fetch") or ""
        body_file_recovery = payload.get("body_file_recovery") or ""
        subject = (payload.get("subject") or "").strip()
        reply_at = (payload.get("reply_at") or "").strip()
        from_email = (payload.get("from_email") or "").strip()

        message_rows.append(
            {
                "账号ID": account_id,
                "Reply_Thread_ID": thread_id,
                "message_id": message_id,
                "reply_at": reply_at,
                "from_email": from_email,
                "subject": subject,
                "body_file_fetch": body_file_fetch,
                "body_file_recovery": body_file_recovery,
                "body_length_raw": str(len(body_text)),
                "body_length_clean": str(len(cleaned_body)),
                "body_clean_reason": clean_reason,
                "body_text_clean": cleaned_body,
                "body_text_preview_clean": summarize_text(cleaned_body),
                "attachment_count": str(attachment_count),
                "attachment_names": attachment_names,
                "attachment_text_count": str(attachment_text_count),
                "attachment_evidence_excerpt": attachment_excerpt,
            }
        )

        rollup = contact_rollups.setdefault(
            account_id,
            {
                "账号ID": account_id,
                "Reply_Thread_IDs": set(),
                "messages_total": 0,
                "messages_with_clean_body": 0,
                "attachment_items_total": 0,
                "attachment_messages_total": 0,
                "latest_reply_at": "",
                "latest_subject": "",
                "latest_body_clean": "",
                "attachment_evidence_excerpt": [],
            },
        )
        rollup["Reply_Thread_IDs"].add(thread_id)
        rollup["messages_total"] += 1
        if cleaned_body.strip():
            rollup["messages_with_clean_body"] += 1
            if not rollup["latest_body_clean"]:
                rollup["latest_body_clean"] = cleaned_body
        if int(str(attachment_count or "0") or "0") > 0:
            rollup["attachment_items_total"] += int(str(attachment_count or "0") or "0")
            rollup["attachment_messages_total"] += 1
        if attachment_excerpt:
            rollup["attachment_evidence_excerpt"].append(attachment_excerpt)
        if reply_at > (rollup["latest_reply_at"] or ""):
            rollup["latest_reply_at"] = reply_at
            rollup["latest_subject"] = subject
            if cleaned_body.strip():
                rollup["latest_body_clean"] = cleaned_body

    for row in fetch_rows:
        account_id = (row.get("账号ID") or "").strip()
        thread_id = (row.get("thread_id") or "").strip()
        message_id = (row.get("message_id") or "").strip()
        body_rel = (row.get("body_file") or "").strip()
        body_path = (attachment_root / "chunk_001").parent  # normalized root
        body_abs = (Path(args.attachment_root) / "chunk_001").parent  # placeholder to satisfy linter-like intent
        del body_path, body_abs
        current_fetch_dir = None
        # Reconstruct absolute body path from row-local relative path by searching chunk dirs.
        body_file_abs = ""
        if body_rel:
            candidates = list(attachment_root.glob(f"chunk_*/pipeline/thread_fetch/{body_rel}"))
            if candidates:
                body_file_abs = str(candidates[0].resolve())
        body_text = ""
        if body_file_abs:
            try:
                body_text = Path(body_file_abs).read_text(encoding="utf-8", errors="replace")
            except Exception:
                body_text = ""

        cleaned_body, clean_reason = clean_reply_text(body_text)
        latest_preview = preview_by_key.get((account_id, thread_id), {})
        recovery_body_rel = (latest_preview.get("Reply_Body_File") or "").strip()
        recovery_body_abs = str((hub_root / recovery_body_rel).resolve()) if recovery_body_rel else ""

        attachment_items = attachment_by_message.get(message_id, [])
        attachment_texts = []
        attachment_names = []
        for item in attachment_items:
            text_file = (item.get("text_file") or "").strip()
            if text_file:
                try:
                    attachment_text = Path(text_file).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    attachment_text = ""
                if attachment_text.strip():
                    attachment_texts.append(attachment_text.strip())
            if (item.get("filename") or "").strip():
                attachment_names.append((item.get("filename") or "").strip())

        attachment_excerpt = summarize_text("\n\n".join(attachment_texts), limit=360)
        append_message_row(
            {
                "账号ID": account_id,
                "Reply_Thread_ID": thread_id,
                "message_id": message_id,
                "reply_at": (row.get("reply_at") or "").strip(),
                "from_email": (row.get("from_email") or "").strip(),
                "subject": (row.get("subject") or "").strip(),
                "body_file_fetch": body_file_abs,
                "body_file_recovery": recovery_body_abs,
                "body_text_raw": body_text,
                "attachment_count": str(len(attachment_items)),
                "attachment_names": " | ".join(attachment_names),
                "attachment_text_count": str(len(attachment_texts)),
                "attachment_evidence_excerpt": attachment_excerpt,
            }
        )

    # Backfill evidence directly from Hub body files referenced by preview/master rows.
    for row in preview_rows:
        account_id = (row.get("账号ID") or "").strip()
        thread_id = (row.get("Reply_Thread_ID") or "").strip()
        body_rel = (row.get("Reply_Body_File") or "").strip()
        if not (account_id and thread_id and body_rel):
            continue
        body_abs = hub_root / body_rel
        if not body_abs.exists():
            continue
        try:
            body_text = body_abs.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        append_message_row(
            {
                "账号ID": account_id,
                "Reply_Thread_ID": thread_id,
                "message_id": (row.get("Latest_Inbound_Message_ID") or "").strip(),
                "reply_at": (row.get("Reply_Last_At") or "").strip(),
                "from_email": (row.get("Reply_Contact_Email") or "").strip(),
                "subject": (row.get("Reply_Last_Subject") or "").strip(),
                "body_file_fetch": "",
                "body_file_recovery": str(body_abs.resolve()),
                "body_text_raw": body_text,
                "attachment_count": "0",
                "attachment_names": "",
                "attachment_text_count": "0",
                "attachment_evidence_excerpt": "",
            }
        )

    contact_rows: List[Dict[str, str]] = []
    for account_id, item in sorted(contact_rollups.items()):
        excerpts = item["attachment_evidence_excerpt"][:3]
        contact_rows.append(
            {
                "账号ID": account_id,
                "thread_count": str(len(item["Reply_Thread_IDs"])),
                "messages_total": str(item["messages_total"]),
                "messages_with_clean_body": str(item["messages_with_clean_body"]),
                "attachment_messages_total": str(item["attachment_messages_total"]),
                "attachment_items_total": str(item["attachment_items_total"]),
                "latest_reply_at": item["latest_reply_at"],
                "latest_subject": item["latest_subject"],
                "latest_body_clean_preview": summarize_text(item["latest_body_clean"], limit=360),
                "attachment_evidence_excerpt": " || ".join(excerpts),
            }
        )

    message_fields = list(message_rows[0].keys()) if message_rows else []
    contact_fields = list(contact_rows[0].keys()) if contact_rows else []

    message_csv = output_dir / "unified_message_evidence.csv"
    contact_csv = output_dir / "unified_contact_evidence.csv"
    write_rows(message_csv, message_rows, message_fields)
    write_rows(contact_csv, contact_rows, contact_fields)

    summary = {
        "preview_rows": len(preview_rows),
        "fetch_message_rows": len(fetch_rows),
        "attachment_report_rows": len(attachment_rows),
        "message_evidence_rows": len(message_rows),
        "contact_evidence_rows": len(contact_rows),
        "messages_with_attachments": sum(1 for row in message_rows if int(row["attachment_count"] or "0") > 0),
        "messages_with_clean_body": sum(1 for row in message_rows if (row["body_text_clean"] or "").strip()),
        "output_message_csv": str(message_csv.resolve()),
        "output_contact_csv": str(contact_csv.resolve()),
    }
    (output_dir / "unified_evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
