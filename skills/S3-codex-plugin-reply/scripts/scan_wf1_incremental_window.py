#!/usr/bin/env python3
"""Scan the latest WF-1 inbox window before any historical backfill."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


DEFAULT_TOKEN_PATH = Path(
    "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>"
)
DEFAULT_MASTER_PATH = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv"
)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
OUR_EMAIL = "<YOUR_ACCOUNT_EMAIL>"
METADATA_HEADERS = ["From", "To", "Subject", "Date"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan latest WF-1 inbox window by time, not historical page cursor.")
    parser.add_argument("--since", required=True, help="Inclusive window start in ISO format, e.g. 2026-06-01T00:00:00")
    parser.add_argument("--out-dir", required=True, help="Directory to write raw and CSV artifacts.")
    parser.add_argument("--token", default=str(DEFAULT_TOKEN_PATH), help="Path to Gmail OAuth token.")
    parser.add_argument("--master", default=str(DEFAULT_MASTER_PATH), help="Path to S3 ReplyOps master CSV.")
    parser.add_argument("--max-pages", type=int, default=10, help="Hard safety cap for inbox pages to scan.")
    return parser.parse_args()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def parse_email_dt(value: str) -> datetime:
    try:
        return parsedate_to_datetime(value).astimezone().replace(tzinfo=None)
    except Exception:
        return datetime.min


def get_service(token_path: Path):
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError(f"OAuth token invalid: {token_path}")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def read_master_index(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        thread_id = (row.get("Reply_Thread_ID") or "").strip()
        if thread_id and thread_id not in index:
            index[thread_id] = {
                "master_name": row.get("频道/作者名称", ""),
                "master_platform": row.get("平台", ""),
                "master_latest_inbound_message_id": row.get("Latest_Inbound_Message_ID", ""),
                "master_reply_status": row.get("Reply_Status", ""),
            }
    return index


def header_map(message: dict) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", []) or []
    return {h.get("name", ""): h.get("value", "") for h in headers}


def latest_inbound(messages: Iterable[dict]) -> dict | None:
    for msg in reversed(list(messages)):
        headers = header_map(msg)
        from_value = (headers.get("From", "") or "").lower()
        if OUR_EMAIL not in from_value:
            return msg
    return None


def latest_message(messages: list[dict]) -> dict:
    return messages[-1]


def main() -> None:
    args = parse_args()
    since_dt = parse_iso(args.since)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    service = get_service(Path(args.token))
    master_index = read_master_index(Path(args.master))

    page_token = None
    scanned_pages = 0
    stopped_on_older_page = False
    rows: list[dict[str, str]] = []
    raw_threads: list[dict] = []

    while scanned_pages < args.max_pages:
        payload = service.users().threads().list(
            userId="me",
            labelIds=["INBOX"],
            pageToken=page_token,
            maxResults=100,
        ).execute()
        page_threads = payload.get("threads", []) or []
        if not page_threads:
            break

        scanned_pages += 1
        page_had_older_boundary = False

        for thread_stub in page_threads:
            thread = service.users().threads().get(
                userId="me",
                id=thread_stub["id"],
                format="metadata",
                metadataHeaders=METADATA_HEADERS,
            ).execute()
            messages = thread.get("messages", []) or []
            if not messages:
                continue

            latest_msg = latest_message(messages)
            latest_headers = header_map(latest_msg)
            latest_dt = parse_email_dt(latest_headers.get("Date", ""))
            if latest_dt < since_dt:
                page_had_older_boundary = True
                break

            inbound_msg = latest_inbound(messages)
            inbound_headers = header_map(inbound_msg) if inbound_msg else {}
            inbound_dt = parse_email_dt(inbound_headers.get("Date", "")) if inbound_msg else datetime.min
            master = master_index.get(thread_stub["id"], {})
            latest_from = latest_headers.get("From", "")
            latest_speaker = "us" if OUR_EMAIL in latest_from.lower() else "them"

            row = {
                "thread_id": thread_stub["id"],
                "subject": latest_headers.get("Subject", ""),
                "latest_message_id": latest_msg.get("id", ""),
                "latest_message_at": latest_headers.get("Date", ""),
                "latest_message_speaker": latest_speaker,
                "latest_message_from": latest_from,
                "latest_inbound_message_id": inbound_msg.get("id", "") if inbound_msg else "",
                "latest_inbound_at": inbound_headers.get("Date", "") if inbound_msg else "",
                "latest_inbound_from": inbound_headers.get("From", "") if inbound_msg else "",
                "message_count": str(len(messages)),
                "has_attachment_on_latest": "yes" if latest_msg.get("payload", {}).get("parts") else "no",
                "in_master": "yes" if master else "no",
                "master_name": master.get("master_name", ""),
                "master_platform": master.get("master_platform", ""),
                "master_latest_inbound_message_id": master.get("master_latest_inbound_message_id", ""),
                "master_reply_status": master.get("master_reply_status", ""),
                "is_refresh_vs_master": (
                    "yes"
                    if master
                    and inbound_msg
                    and master.get("master_latest_inbound_message_id", "")
                    and master.get("master_latest_inbound_message_id", "") != inbound_msg.get("id", "")
                    else "no"
                ),
                "snippet": thread_stub.get("snippet", ""),
                "window_start_at": since_dt.isoformat(sep=" ", timespec="seconds"),
                "window_hit": "yes" if latest_dt >= since_dt else "no",
                "latest_inbound_within_window": "yes" if inbound_dt >= since_dt else "no",
            }
            rows.append(row)
            raw_threads.append(thread)

        if page_had_older_boundary:
            stopped_on_older_page = True
            break

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    csv_path = out_dir / "wf1_incremental_window_scan.csv"
    json_path = out_dir / "wf1_incremental_window_scan_raw.json"
    summary_path = out_dir / "wf1_incremental_window_summary.json"

    fieldnames = list(rows[0].keys()) if rows else [
        "thread_id",
        "subject",
        "latest_message_id",
        "latest_message_at",
        "latest_message_speaker",
        "latest_message_from",
        "latest_inbound_message_id",
        "latest_inbound_at",
        "latest_inbound_from",
        "message_count",
        "has_attachment_on_latest",
        "in_master",
        "master_name",
        "master_platform",
        "master_latest_inbound_message_id",
        "master_reply_status",
        "is_refresh_vs_master",
        "snippet",
        "window_start_at",
        "window_hit",
        "latest_inbound_within_window",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(raw_threads, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "scan_mode": "latest_time_window_incremental",
        "since": since_dt.isoformat(sep=" ", timespec="seconds"),
        "scanned_pages": scanned_pages,
        "captured_threads": len(rows),
        "stopped_on_older_page": stopped_on_older_page,
        "next_backfill_page_token": page_token,
        "artifacts": {
            "csv": str(csv_path),
            "raw_json": str(json_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
