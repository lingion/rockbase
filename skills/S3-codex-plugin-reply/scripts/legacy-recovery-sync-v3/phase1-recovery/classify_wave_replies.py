#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

TOKEN_PATH = Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>")
WORKBENCH_ROOT = Path("${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify inbound replies back to a target outbound wave (mail1/mail2/mail3).")
    parser.add_argument("--master", required=True, help="Path to replied master CSV.")
    parser.add_argument("--capture-run-id", required=True, help="Capture run id to inspect.")
    parser.add_argument("--wave", required=True, choices=["mail1", "mail2", "mail3"], help="Outbound wave to classify against.")
    parser.add_argument("--limit", type=int, default=9999, help="Max rows to test.")
    parser.add_argument("--output-json", required=True, help="Path to result JSON.")
    parser.add_argument("--write-master", action="store_true", help="Write classified reply fields back to master.")
    parser.add_argument("--token", default=str(TOKEN_PATH), help="Path to Gmail OAuth token.")
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_service(token_path: Path):
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def get_message_headers(service, message_id: str) -> Dict[str, str]:
    payload = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["Message-ID", "Subject", "From", "To", "Date"],
        )
        .execute()
    )
    headers = payload.get("payload", {}).get("headers", [])
    out: Dict[str, str] = {}
    for h in headers:
        name = h.get("name", "").lower()
        if name:
            out[name] = h.get("value", "")
    return out


def parse_outbound_ids(raw: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in (raw or "").split("|"):
        part = part.strip()
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def normalize_msgid(value: str) -> str:
    return (value or "").strip()


def clean_reply_text(text: str) -> str:
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: List[str] = []
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if stripped.startswith(">"):
            break
        if lower.startswith("on ") and " wrote:" in lower:
            break
        if lower.startswith("from:"):
            break
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned


def load_reply_text(row: Dict[str, str]) -> str:
    raw = row.get("Reply_Body_File", "") or ""
    if not raw:
        return ""
    path = Path(raw)
    candidates: List[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend(WORKBENCH_ROOT.glob(f"**/{raw}"))
        if row.get("Latest_Inbound_Message_ID"):
            candidates.extend(WORKBENCH_ROOT.glob(f"**/{row['Latest_Inbound_Message_ID']}.txt"))
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
        except Exception:
            continue
    return raw


def current_reply_value(row: Dict[str, str], wave: str) -> str:
    col = f"{wave.capitalize()}_Reply"
    value = row.get(col, "") or ""
    if value.startswith("bodies/") and value.endswith(".txt"):
        return ""
    return value


def reply_columns(wave: str) -> Dict[str, str]:
    prefix = wave.capitalize()
    return {
        "at": f"{prefix}_Reply_At",
        "summary": f"{prefix}_Reply_Summary",
        "category": f"{prefix}_Reply_Category",
        "next_action": f"{prefix}_Reply_Next_Action",
        "reply": f"{prefix}_Reply",
        "draft_id": f"{prefix}_Draft_ID",
    }


def classify_row(service, row: Dict[str, str], target_wave: str) -> Dict[str, str]:
    outbound_ids = parse_outbound_ids(row.get("Outbound_Message_IDs", ""))
    outbound_rfc_ids: Dict[str, str] = {}
    for wave, gmail_message_id in outbound_ids.items():
        if not gmail_message_id:
            continue
        try:
            headers = get_message_headers(service, gmail_message_id)
            outbound_rfc_ids[wave] = normalize_msgid(headers.get("message-id", ""))
        except Exception:
            outbound_rfc_ids[wave] = ""

    inbound_in_reply_to = normalize_msgid(row.get("Latest_Inbound_InReplyTo", ""))
    matched_wave = ""
    for wave, rfc_id in outbound_rfc_ids.items():
        if rfc_id and inbound_in_reply_to == rfc_id:
            matched_wave = wave
            break

    cols = reply_columns(target_wave)
    target_category = f"{target_wave}_reply"
    if matched_wave == target_wave:
        category = target_category
        next_action = f"review_{target_wave}_reply"
        summary = row.get("Reply_Analysis", "") or f"{target_wave} reply captured"
    elif matched_wave:
        category = f"{matched_wave}_reply"
        next_action = "not_target_wave"
        summary = row.get("Reply_Analysis", "") or f"{matched_wave} reply captured"
    else:
        category = "manual_review"
        next_action = "manual_review"
        summary = row.get("Reply_Analysis", "") or "Could not map inbound reply to outbound wave"

    return {
        "账号ID": row.get("账号ID", ""),
        "Reply_Thread_ID": row.get("Reply_Thread_ID", ""),
        "Latest_Inbound_Message_ID": row.get("Latest_Inbound_Message_ID", ""),
        "Latest_Inbound_InReplyTo": inbound_in_reply_to,
        "matched_wave": matched_wave,
        "mail1_rfc_message_id": outbound_rfc_ids.get("mail1", ""),
        "mail2_rfc_message_id": outbound_rfc_ids.get("mail2", ""),
        "mail3_rfc_message_id": outbound_rfc_ids.get("mail3", ""),
        cols["at"]: row.get("Reply_Last_At", "") if matched_wave == target_wave else row.get(cols["at"], ""),
        cols["summary"]: summary if matched_wave == target_wave else row.get(cols["summary"], ""),
        cols["category"]: category if matched_wave == target_wave else row.get(cols["category"], ""),
        cols["next_action"]: next_action if matched_wave == target_wave else row.get(cols["next_action"], ""),
        cols["reply"]: clean_reply_text(current_reply_value(row, target_wave) or load_reply_text(row)) if matched_wave == target_wave else row.get(cols["reply"], ""),
    }


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    rows = read_rows(master_path)
    fieldnames = list(rows[0].keys()) if rows else []
    service = get_service(Path(args.token))
    cols = reply_columns(args.wave)

    candidates = [
        row
        for row in rows
        if (row.get("Capture_Run_ID") or "").strip() == args.capture_run_id
        and (row.get(cols["draft_id"]) or "").strip()
    ][: args.limit]

    results = [classify_row(service, row, args.wave) for row in candidates]

    if args.write_master:
        by_thread = {r["Reply_Thread_ID"]: r for r in results if r.get("matched_wave") == args.wave}
        for row in rows:
            hit = by_thread.get(row.get("Reply_Thread_ID", ""))
            if not hit:
                continue
            row[cols["at"]] = hit[cols["at"]]
            row[cols["summary"]] = hit[cols["summary"]]
            row[cols["category"]] = hit[cols["category"]]
            row[cols["next_action"]] = hit[cols["next_action"]]
            row[cols["reply"]] = hit[cols["reply"]]
        write_rows(master_path, rows, fieldnames)

    summary = {
        "capture_run_id": args.capture_run_id,
        "wave": args.wave,
        "tested_rows": len(results),
        "matched_target_wave": sum(1 for r in results if r.get("matched_wave") == args.wave),
        "matched_mail1": sum(1 for r in results if r.get("matched_wave") == "mail1"),
        "matched_mail2": sum(1 for r in results if r.get("matched_wave") == "mail2"),
        "matched_mail3": sum(1 for r in results if r.get("matched_wave") == "mail3"),
        "manual_review": sum(1 for r in results if not r.get("matched_wave")),
        "results": results,
    }
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
