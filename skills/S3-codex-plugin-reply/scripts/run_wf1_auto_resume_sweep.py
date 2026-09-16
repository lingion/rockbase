#!/usr/bin/env python3
"""Run a latest-first WF-1 resume sweep until a lower boundary date.

This script is execution-first:
- scan inbox latest-first until a configured lower boundary
- detect threads that already have Gmail drafts and pass them
- auto OCR attachments for quote recovery candidates
- auto build/apply a local writeback manifest for in-master priced threads
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
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
DEFAULT_CHECKPOINT_PATH = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S3-codex-plugin-reply/output/wf1_latest_checkpoint.json"
)
DEFAULT_EXTRACT_SCRIPT = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S3-codex-plugin-reply/scripts/legacy-recovery-sync-v3/extract_reply_attachments.py"
)
DEFAULT_APPLY_SCRIPT = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S3-codex-plugin-reply/scripts/apply_manifest_to_live_master.py"
)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
OUR_EMAIL = "<YOUR_ACCOUNT_EMAIL>"
METADATA_HEADERS = ["From", "To", "Subject", "Date"]
PRICE_RE = re.compile(
    r"(?i)(USD|US\$|USO|\$|GBP|£|EUR|€|THB|THP)\s*([0-9][0-9,]{1,8}(?:\.[0-9]{1,2})?(?:[Kk])?)"
    r"|([0-9][0-9,]{1,8}(?:\.[0-9]{1,2})?(?:[Kk])?)\s*(USD|US\$|USO|\$|GBP|£|EUR|€|THB|THP)"
)
CHANNEL_RE = re.compile(
    r"(?i)\b(instagram|ig|tiktok|youtube|shorts|reel|reels|story|stories|post|integration|dedicated|ugc|bundle|package)\b"
)
SYSTEM_FROM_HINTS = [
    "mailer-daemon",
    "mail delivery subsystem",
    "google one",
    "no-reply",
    "noreply",
    "support@luma",
    "collabstr <<YOUR_ACCOUNT_EMAIL>>",
]
CURRENCY_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "USO": "USD",
    "£": "GBP",
    "GBP": "GBP",
    "€": "EUR",
    "EUR": "EUR",
    "THB": "THB",
    "THP": "THB",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--lower-bound", required=True, help="Stop scanning once latest message date is older than this ISO datetime.")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--master", default=str(DEFAULT_MASTER_PATH))
    parser.add_argument("--token", default=str(DEFAULT_TOKEN_PATH))
    parser.add_argument("--extract-script", default=str(DEFAULT_EXTRACT_SCRIPT))
    parser.add_argument("--apply-script", default=str(DEFAULT_APPLY_SCRIPT))
    parser.add_argument("--min-pages", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--apply-live-writeback", action="store_true")
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


def read_master_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def read_master_index(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_master_rows(path)
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        thread_id = (row.get("Reply_Thread_ID") or "").strip()
        if thread_id and thread_id not in index:
            index[thread_id] = row
    return index


def read_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def header_map(message: dict) -> dict[str, str]:
    return {h.get("name", ""): h.get("value", "") for h in message.get("payload", {}).get("headers", []) or []}


def iter_parts(part: dict) -> Iterable[dict]:
    yield part
    for child in part.get("parts", []) or []:
        yield from iter_parts(child)


def decode_body_data(data: str) -> str:
    import base64

    padded = data + "=" * ((4 - len(data) % 4) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return raw.decode("utf-8", errors="replace")


def body_text(message: dict) -> str:
    payload = message.get("payload", {}) or {}
    parts = list(iter_parts(payload))
    texts: list[str] = []
    for part in parts:
        mime = (part.get("mimeType") or "").lower()
        data = (((part.get("body") or {}).get("data")) or "")
        if mime == "text/plain" and data:
            texts.append(decode_body_data(data))
    if texts:
        return "\n".join(t.strip() for t in texts if t.strip()).strip()
    data = ((payload.get("body") or {}).get("data")) or ""
    return decode_body_data(data).strip() if data else ""


def latest_inbound(messages: list[dict]) -> dict | None:
    for msg in reversed(messages):
        from_value = (header_map(msg).get("From", "") or "").lower()
        if OUR_EMAIL not in from_value:
            return msg
    return None


def collect_attachments(messages: list[dict], thread_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for msg in messages:
        headers = header_map(msg)
        from_value = headers.get("From", "")
        if OUR_EMAIL in from_value.lower():
            continue
        for part in iter_parts(msg.get("payload", {}) or {}):
            filename = (part.get("filename") or "").strip()
            body = part.get("body", {}) or {}
            attachment_id = body.get("attachmentId", "")
            if not filename or not attachment_id:
                continue
            rows.append(
                {
                    "message_id": msg.get("id", ""),
                    "thread_id": thread_id,
                    "from_email": from_value,
                    "filename": filename,
                    "mime_type": part.get("mimeType", ""),
                    "attachment_id": attachment_id,
                    "size": str(body.get("size", "")),
                    "part_id": part.get("partId", ""),
                    "local_path": "",
                }
            )
    return rows


def meaningful_attachments(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    for row in rows:
        name = (row.get("filename") or "").strip().lower()
        mime = (row.get("mime_type") or "").strip().lower()
        try:
            size = int((row.get("size") or "0").strip() or "0")
        except Exception:
            size = 0
        if name in {"icon.png", "warning_triangle.png"}:
            continue
        if size and size < 8000 and mime.startswith("image/"):
            continue
        if not (mime.startswith("image/") or mime == "application/pdf"):
            continue
        filtered.append(row)
    return filtered


def extract_price_hits(text: str) -> list[str]:
    hits: list[str] = []
    for match in PRICE_RE.finditer(text or ""):
        token = next((group for group in match.groups() if group and any(ch.isdigit() for ch in group)), "")
        full = match.group(0).strip()
        if full and full not in hits:
            hits.append(full)
        if token and token not in hits:
            hits.append(token)
    return hits[:12]


def extract_channel_hits(text: str) -> list[str]:
    seen: list[str] = []
    for match in CHANNEL_RE.finditer(text or ""):
        value = match.group(1).lower()
        if value not in seen:
            seen.append(value)
    return seen[:8]


def normalize_currency_token(token: str) -> str:
    return CURRENCY_MAP.get((token or "").strip().upper(), (token or "").strip().upper())


def normalize_amount_token(value: str) -> str:
    text = (value or "").strip().rstrip(".,:;")
    is_k = text.lower().endswith("k")
    if is_k:
        text = text[:-1]
    number = float(text.replace(",", ""))
    if is_k:
        number *= 1000
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def normalize_price_match(match: re.Match) -> str:
    currency = match.group(1) or match.group(4) or ""
    amount = match.group(2) or match.group(3) or ""
    return f"{normalize_amount_token(amount)} {normalize_currency_token(currency)}"


def collect_price_evidence_lines(text: str) -> list[str]:
    cleaned = (text or "").replace("\r", "\n").replace("USO", "USD").replace("THP", "THB")
    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = re.sub(r"\s+", " ", raw_line.strip().lstrip(">")).strip()
        if not line:
            continue
        if PRICE_RE.search(line):
            if line not in lines:
                lines.append(line)
    return lines


def infer_platform_label(line: str, fallback: str = "") -> str:
    lowered = line.lower()
    for token, label in (
        ("instagram", "Instagram"),
        ("tiktok", "TikTok"),
        ("youtube short", "YouTube"),
        ("youtube shorts", "YouTube"),
        ("youtube", "YouTube"),
        ("linkedin", "LinkedIn"),
    ):
        if token in lowered:
            return label
    return fallback


def infer_deliverable_label(line: str, platform: str) -> str:
    text = re.sub(r"\s+", " ", line).strip().strip("•-*")
    text = PRICE_RE.sub("", text)
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    for token in [platform, "USD", "GBP", "EUR", "THB", "USO", "THP"]:
        if token:
            text = re.sub(re.escape(token), "", text, flags=re.I)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:,/")
    return text or "Price"


def build_price_fields(text: str, default_platform: str = "") -> tuple[str, str]:
    evidence_lines = collect_price_evidence_lines(text)
    if not evidence_lines:
        return "", ""
    normalized_lines: list[str] = []
    platform_hint = default_platform
    for line in evidence_lines:
        platform = infer_platform_label(line, platform_hint) or "Unknown Platform"
        platform_hint = platform
        deliverable = infer_deliverable_label(line, platform)
        prices = [normalize_price_match(match) for match in PRICE_RE.finditer(line)]
        if not prices:
            continue
        price_text = " / ".join(dict.fromkeys(prices))
        normalized_lines.append(f"· {platform}: {deliverable} = {price_text}")
    return "\n".join(evidence_lines), "\n".join(dict.fromkeys(normalized_lines))


def is_system_thread(subject: str, from_value: str) -> bool:
    lowered = f"{subject} {from_value}".lower()
    return any(hint in lowered for hint in SYSTEM_FROM_HINTS)


def classify_candidate(row: dict[str, str]) -> str:
    if row["is_system_thread"] == "yes":
        return "non_wf1_system"
    if row["latest_message_speaker"] != "them":
        return "latest_outbound_ours"
    if row["thread_has_draft"] == "yes":
        if row["price_source"] in {"body_quote", "ocr_quote"}:
            return "pass_existing_draft_writeback_only"
        return "pass_existing_draft"
    if row["price_source"] in {"body_quote", "ocr_quote"}:
        return "new_price_and_new_draft"
    if row["attachment_requires_ocr"] == "yes":
        return "ocr_first"
    return "draft_needed_no_price"


def subject_looks_wf1(subject: str) -> bool:
    lowered = (subject or "").lower()
    if any(token in lowered for token in ["termination", "refund request", "customer success", "automatic reply"]):
        return False
    return any(
        token in lowered
        for token in [
            "rockbase agency",
            " x rockbase agency",
            "potential ai campaign fit:",
            "paid collaboration:",
            "paid collab:",
            "airtap x",
        ]
    )


def inferred_platform(row: dict[str, str]) -> str:
    if row["master_platform"]:
        return row["master_platform"]
    merged = " | ".join(
        item for item in [row.get("body_channel_hits", ""), row.get("ocr_channel_hits", "")] if item.strip()
    ).lower()
    platform_tokens: list[str] = []
    for token, label in (
        ("instagram", "Instagram"),
        ("ig", "Instagram"),
        ("tiktok", "TikTok"),
        ("youtube", "YouTube"),
        ("shorts", "YouTube"),
        ("reel", "Instagram"),
        ("reels", "Instagram"),
        ("story", "Instagram"),
        ("stories", "Instagram"),
    ):
        if token in merged and label not in platform_tokens:
            platform_tokens.append(label)
    return "/".join(platform_tokens)


def build_manifest_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    stamp = datetime.now().isoformat(timespec="seconds")
    for row in rows:
        if row["price_source"] not in {"body_quote", "ocr_quote"}:
            continue
        if row["is_system_thread"] == "yes":
            continue
        if not subject_looks_wf1(row["subject"]):
            continue
        creator_name = row["master_name"] or row["creator_name_guess"]
        if not creator_name and not row["reply_contact_email"]:
            continue
        manifest_action = "update" if row["in_master"] == "yes" else "append"
        match_basis = "thread_id" if row["in_master"] == "yes" else "new_thread_id"
        basis = "OCR quote recovered from inbound attachment." if row["price_source"] == "ocr_quote" else "Inbound body quote recovered from latest thread review."
        manifest.append(
            {
                "manifest_status": "approved",
                "manifest_action": manifest_action,
                "match_basis": match_basis,
                "备注": f"WF-1 auto resume sweep writeback on {stamp}.",
                "Source_Tag": "wf1_auto_resume_sweep",
                "频道/作者名称": creator_name,
                "平台": inferred_platform(row),
                "联系方式": row["reply_contact_email"],
                "Reply_Contact_Email": row["reply_contact_email"],
                "latest_price_raw": row["price_raw"],
                "latest_price_normalized": row["price_normalized"],
                "latest_price_basis": basis,
                "Sort_Bucket": "1_replied_clear_price",
                "Reply_Count": row["message_count"],
                "Reply_Thread_ID": row["thread_id"],
                "Reply_Last_Message_ID": row["latest_inbound_message_id"],
                "Reply_Last_Subject": row["subject"],
                "Reply_Last_At": row["latest_inbound_at"],
                "Latest_Inbound_Message_ID": row["latest_inbound_message_id"],
                "Reply_Stage": "reply",
                "Reply_Stream": "outreach",
                "Pipeline_Stage": "reply_ops",
                "Capture_Run_ID": "wf1_auto_resume_sweep",
                "Capture_At": stamp,
                "Reply_Status": "wf1_auto_resume_writeback_applied",
                "Reply_Needs_Manual_Review": "no",
                "Reply_Analysis": row["queue_reason"],
                "Manual_Review_Reason": "",
                "Manual_Review_Focus": "",
                "current_price_summary": row["current_price_summary"],
                "Pricing_Effective_Wave": datetime.now().date().isoformat(),
                "Pricing_Change_Type": "refresh_quote" if row["is_refresh_vs_master"] == "yes" else "new_quote",
                "Pricing_Round": "wf1_auto_resume_quote",
                "Current_Reply_Scenario": "wf1_price_recovered",
                "Next_Reply_Action": "pass_existing_draft" if row["thread_has_draft"] == "yes" else "draft_from_body_quote",
                "Attachment_OCR_Status": row["attachment_ocr_status"],
                "Draft_Workflow_Status": "draft_exists_skip" if row["thread_has_draft"] == "yes" else "not_started",
                "audit_note": row["queue_name"],
            }
        )
    return manifest


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_field(row: dict[str, str], key: str) -> int:
    try:
        return int((row.get(key) or "0").strip() or "0")
    except Exception:
        return 0


def build_rollup_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "thread_count": len(rows),
        "message_total_seen": 0,
        "price_signal_threads": 0,
        "new_price_threads": 0,
        "refreshed_price_threads": 0,
        "reply_needed_threads": 0,
        "existing_draft_threads": 0,
        "non_wf1_threads": 0,
        "manual_review_threads": 0,
        "latest_message_from_them_threads": 0,
    }
    for row in rows:
        counts["message_total_seen"] += int_field(row, "message_count")
        queue_name = row.get("queue_name", "")
        if row.get("latest_message_speaker") == "them":
            counts["latest_message_from_them_threads"] += 1
        if row.get("thread_has_draft") == "yes":
            counts["existing_draft_threads"] += 1
        if row.get("is_system_thread") == "yes" or queue_name.startswith("non_wf1"):
            counts["non_wf1_threads"] += 1
        if row.get("price_source") in {"body_quote", "ocr_quote"}:
            counts["price_signal_threads"] += 1
            if row.get("queue_name") == "price_signal_existing_no_update":
                pass
            elif row.get("in_master") == "yes" and row.get("is_refresh_vs_master") == "yes":
                counts["refreshed_price_threads"] += 1
            else:
                counts["new_price_threads"] += 1
        if queue_name == "draft_needed_no_price":
            counts["reply_needed_threads"] += 1
        if queue_name in {"ocr_first", "manual_review"}:
            counts["manual_review_threads"] += 1
    counts["needs_reply_threads"] = counts["reply_needed_threads"]
    return counts


def build_thread_triage_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    triage_rows: list[dict[str, str]] = []
    for row in rows:
        if row.get("is_system_thread") == "yes" or row.get("queue_name", "").startswith("non_wf1"):
            action_bucket = "excluded_non_wf1"
        elif row.get("price_source") in {"body_quote", "ocr_quote"} and row.get("in_master") == "yes" and row.get("is_refresh_vs_master") == "yes":
            action_bucket = "price_refresh_candidate"
        elif row.get("queue_name") == "price_signal_existing_no_update":
            action_bucket = "price_signal_existing_no_update"
        elif row.get("price_source") in {"body_quote", "ocr_quote"}:
            action_bucket = "new_price_candidate"
        elif row.get("queue_name") == "draft_needed_no_price":
            action_bucket = "reply_needed_no_price"
        elif row.get("thread_has_draft") == "yes":
            action_bucket = "existing_draft_hold"
        else:
            action_bucket = "manual_review_or_other"
        triage_rows.append(
            {
                "thread_id": row.get("thread_id", ""),
                "subject": row.get("subject", ""),
                "latest_message_at": row.get("latest_message_at", ""),
                "latest_inbound_at": row.get("latest_inbound_at", ""),
                "latest_message_speaker": row.get("latest_message_speaker", ""),
                "message_count": row.get("message_count", ""),
                "in_master": row.get("in_master", ""),
                "is_refresh_vs_master": row.get("is_refresh_vs_master", ""),
                "thread_has_draft": row.get("thread_has_draft", ""),
                "price_source": row.get("price_source", ""),
                "queue_name": row.get("queue_name", ""),
                "action_bucket": action_bucket,
                "reply_contact_email": row.get("reply_contact_email", ""),
                "creator_name_guess": row.get("creator_name_guess", ""),
            }
        )
    return triage_rows


def build_summary(
    *,
    scan_rows: list[dict[str, str]],
    checkpoint: dict,
    lower_bound: datetime,
    scanned_pages: int,
    stopped_on_lower_bound: bool,
    newest_seen_at: str,
    oldest_seen_at: str,
    attachment_count: int,
    manifest_rows: list[dict[str, str]],
    artifact_paths: dict[str, str],
    boundary_thread: dict[str, str] | None,
    mode: str,
) -> dict:
    counts = build_rollup_counts(scan_rows)
    queue_counts: dict[str, int] = {}
    for row in scan_rows:
        queue_name = row.get("queue_name", "") or "unclassified"
        queue_counts[queue_name] = queue_counts.get(queue_name, 0) + 1
    return {
        "scan_mode": "wf1_auto_resume_sweep",
        "execution_mode": mode,
        "scan_direction_rule": "always start from current INBOX top, move backward, and stop at the last confirmed stop point",
        "boundary_target_from_checkpoint": checkpoint.get("last_window_end_at") or checkpoint.get("resume_boundary_lower_date") or "",
        "resume_boundary_lower_date": checkpoint.get("resume_boundary_lower_date", ""),
        "lower_bound": lower_bound.isoformat(sep=" ", timespec="seconds"),
        "scanned_pages": scanned_pages,
        "thread_count": counts["thread_count"],
        "message_total_seen": counts["message_total_seen"],
        "latest_message_from_them_thread_count": counts["latest_message_from_them_threads"],
        "price_signal_thread_count": counts["price_signal_threads"],
        "new_price_thread_count": counts["new_price_threads"],
        "refreshed_price_thread_count": counts["refreshed_price_threads"],
        "reply_needed_thread_count": counts["reply_needed_threads"],
        "existing_draft_thread_count": counts["existing_draft_threads"],
        "non_wf1_thread_count": counts["non_wf1_threads"],
        "manual_review_thread_count": counts["manual_review_threads"],
        "attachments_total": attachment_count,
        "writeback_ready_count": len(manifest_rows),
        "connected_to_previous_stop": stopped_on_lower_bound,
        "boundary_hit_thread": boundary_thread or {},
        "newest_seen_at": newest_seen_at,
        "oldest_seen_at": oldest_seen_at,
        "queue_counts": queue_counts,
        "artifacts": artifact_paths,
    }


def write_markdown_summary(path: Path, summary: dict) -> None:
    boundary = summary.get("boundary_hit_thread") or {}
    lines = [
        "# WF-1 Resume Sweep Dry Run Summary",
        "",
        f"- execution_mode: `{summary.get('execution_mode', '')}`",
        f"- scan_direction_rule: `{summary.get('scan_direction_rule', '')}`",
        f"- boundary_target_from_checkpoint: `{summary.get('boundary_target_from_checkpoint', '')}`",
        f"- lower_bound: `{summary.get('lower_bound', '')}`",
        f"- connected_to_previous_stop: `{summary.get('connected_to_previous_stop', False)}`",
        f"- scanned_pages: `{summary.get('scanned_pages', 0)}`",
        f"- thread_count: `{summary.get('thread_count', 0)}`",
        f"- message_total_seen: `{summary.get('message_total_seen', 0)}`",
        f"- price_signal_thread_count: `{summary.get('price_signal_thread_count', 0)}`",
        f"- new_price_thread_count: `{summary.get('new_price_thread_count', 0)}`",
        f"- refreshed_price_thread_count: `{summary.get('refreshed_price_thread_count', 0)}`",
        f"- reply_needed_thread_count: `{summary.get('reply_needed_thread_count', 0)}`",
        f"- existing_draft_thread_count: `{summary.get('existing_draft_thread_count', 0)}`",
        f"- writeback_ready_count: `{summary.get('writeback_ready_count', 0)}`",
    ]
    if boundary:
        lines.extend(
            [
                "",
                "## Boundary Proof",
                "",
                f"- thread_id: `{boundary.get('thread_id', '')}`",
                f"- latest_message_at: `{boundary.get('latest_message_at', '')}`",
                f"- subject: `{boundary.get('subject', '')}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def thread_creator_guess(master_row: dict[str, str], subject: str, from_value: str) -> str:
    if master_row.get("频道/作者名称", "").strip():
        return master_row["频道/作者名称"].strip()
    cleaned = (subject or "").replace("Re:", "").strip()
    if " x Rockbase Agency" in cleaned:
        prefix = cleaned.split(" x Rockbase Agency", 1)[0]
        if ": " in prefix:
            prefix = prefix.split(": ", 1)[1]
        return prefix.strip()
    for token in ["Potential AI Campaign Fit:", "Paid Collaboration:", "Paid Collab:"]:
        if token.lower() in cleaned.lower():
            return cleaned.split(":", 1)[1].strip()
    if "<" in from_value:
        return from_value.split("<", 1)[0].strip().strip('"')
    return from_value.strip()


def reply_email(from_value: str) -> str:
    match = re.search(r"<([^>]+)>", from_value or "")
    return match.group(1).strip() if match else (from_value or "").strip()


def ocr_merge(scan_rows: list[dict[str, str]], report_csv: Path) -> None:
    if not report_csv.exists():
        return
    by_thread: dict[str, list[dict[str, str]]] = {}
    with report_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            by_thread.setdefault(row.get("thread_id", ""), []).append(row)
    for row in scan_rows:
        reports = by_thread.get(row["thread_id"], [])
        if not reports:
            continue
        chunks: list[str] = []
        for item in reports:
            text_file = Path(item.get("text_file", ""))
            if text_file.exists():
                chunks.append(text_file.read_text(encoding="utf-8", errors="replace"))
            else:
                chunks.append(item.get("text_preview", ""))
        merged_text = " ".join(chunks)
        price_hits = extract_price_hits(merged_text)
        channel_hits = extract_channel_hits(merged_text)
        row["ocr_attachment_count"] = str(len(reports))
        row["ocr_price_hits"] = " | ".join(price_hits)
        row["ocr_channel_hits"] = " | ".join(channel_hits)
        if price_hits:
            price_raw, price_normalized = build_price_fields(merged_text, row.get("master_platform", ""))
            row["price_source"] = "ocr_quote"
            row["attachment_ocr_status"] = "ocr_price_recovered"
            row["price_raw"] = price_raw or " | ".join(price_hits)
            row["price_normalized"] = price_normalized or " | ".join(price_hits)
            row["current_price_summary"] = "OCR recovered structured pricing." if price_normalized else f"OCR recovered price signals: {' | '.join(price_hits)}"


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lower_bound = parse_iso(args.lower_bound)
    mode = "apply" if args.apply_live_writeback or args.mode == "apply" else "dry-run"
    master_path = Path(args.master)
    checkpoint = read_checkpoint(Path(args.checkpoint))
    service = get_service(Path(args.token))
    master_index = read_master_index(master_path)

    scan_rows: list[dict[str, str]] = []
    attachment_rows: list[dict[str, str]] = []
    raw_threads: list[dict] = []

    page_token = None
    scanned_pages = 0
    stopped_on_lower_bound = False
    newest_seen_at = ""
    oldest_seen_at = ""
    boundary_thread: dict[str, str] | None = None

    while scanned_pages < args.max_pages:
        payload = service.users().threads().list(userId="me", labelIds=["INBOX"], pageToken=page_token, maxResults=100).execute()
        threads = payload.get("threads", []) or []
        if not threads:
            break
        scanned_pages += 1
        page_has_recent = False
        for stub in threads:
            meta_thread = service.users().threads().get(
                userId="me",
                id=stub["id"],
                format="metadata",
                metadataHeaders=METADATA_HEADERS,
            ).execute()
            meta_messages = meta_thread.get("messages", []) or []
            if not meta_messages:
                continue
            latest_meta_msg = meta_messages[-1]
            latest_meta_headers = header_map(latest_meta_msg)
            latest_dt = parse_email_dt(latest_meta_headers.get("Date", ""))
            if latest_dt >= lower_bound:
                page_has_recent = True
            elif boundary_thread is None:
                boundary_thread = {
                    "thread_id": stub["id"],
                    "subject": latest_meta_headers.get("Subject", ""),
                    "latest_message_at": latest_meta_headers.get("Date", ""),
                }
            if latest_dt < lower_bound and scanned_pages >= args.min_pages:
                stopped_on_lower_bound = True
                page_has_recent = False
                break
            thread = service.users().threads().get(userId="me", id=stub["id"], format="full").execute()
            raw_threads.append(thread)
            messages = thread.get("messages", []) or []
            if not messages:
                continue
            latest_msg = messages[-1]
            latest_headers = header_map(latest_msg)
            latest_inbound_msg = latest_inbound(messages)
            inbound_headers = header_map(latest_inbound_msg) if latest_inbound_msg else {}
            inbound_body = body_text(latest_inbound_msg) if latest_inbound_msg else ""
            price_hits = extract_price_hits(inbound_body)
            channel_hits = extract_channel_hits(inbound_body)
            master_row = master_index.get(stub["id"], {})
            price_raw, price_normalized = build_price_fields(inbound_body, master_row.get("平台", ""))
            latest_from = latest_headers.get("From", "")
            latest_speaker = "us" if OUR_EMAIL in latest_from.lower() else "them"
            has_draft = any("DRAFT" in (msg.get("labelIds") or []) for msg in messages)
            attachments = meaningful_attachments(collect_attachments(messages, stub["id"]))

            if not newest_seen_at:
                newest_seen_at = latest_headers.get("Date", "")
            oldest_seen_at = latest_headers.get("Date", "")

            row = {
                "thread_id": stub["id"],
                "subject": latest_headers.get("Subject", ""),
                "latest_message_id": latest_msg.get("id", ""),
                "latest_message_at": latest_headers.get("Date", ""),
                "latest_message_speaker": latest_speaker,
                "latest_message_from": latest_from,
                "latest_inbound_message_id": latest_inbound_msg.get("id", "") if latest_inbound_msg else "",
                "latest_inbound_at": inbound_headers.get("Date", "") if latest_inbound_msg else "",
                "latest_inbound_from": inbound_headers.get("From", "") if latest_inbound_msg else "",
                "latest_inbound_body_preview": re.sub(r"\\s+", " ", inbound_body)[:360],
                "message_count": str(len(messages)),
                "thread_has_draft": "yes" if has_draft else "no",
                "attachment_count": str(len(attachments)),
                "attachment_requires_ocr": "yes" if attachments and not price_hits else "no",
                "attachment_ocr_status": "ocr_pending" if attachments and not price_hits else ("not_needed" if not attachments else "body_quote_sufficient"),
                "in_master": "yes" if master_row else "no",
                "master_name": master_row.get("频道/作者名称", ""),
                "master_platform": master_row.get("平台", ""),
                "master_latest_inbound_message_id": master_row.get("Latest_Inbound_Message_ID", ""),
                "is_refresh_vs_master": (
                    "yes"
                    if master_row
                    and latest_inbound_msg
                    and master_row.get("Latest_Inbound_Message_ID", "").strip()
                    and master_row.get("Latest_Inbound_Message_ID", "").strip() != latest_inbound_msg.get("id", "")
                    else "no"
                ),
                "reply_contact_email": reply_email(inbound_headers.get("From", "") or latest_from),
                "creator_name_guess": thread_creator_guess(master_row, latest_headers.get("Subject", ""), inbound_headers.get("From", "") or latest_from),
                "is_system_thread": "yes" if is_system_thread(latest_headers.get("Subject", ""), latest_from) else "no",
                "price_source": "body_quote" if price_hits else "",
                "price_raw": price_raw or " | ".join(price_hits),
                "price_normalized": price_normalized or " | ".join(price_hits),
                "body_channel_hits": " | ".join(channel_hits),
                "ocr_price_hits": "",
                "ocr_channel_hits": "",
                "ocr_attachment_count": "0",
                "current_price_summary": ("Body quote recovered with structured pricing." if price_normalized else f"Body quote signals: {' | '.join(price_hits)}") if price_hits else "",
                "queue_name": "",
                "queue_reason": "",
                "checkpoint_last_window_end_at": checkpoint.get("last_window_end_at", ""),
            }
            row["queue_name"] = classify_candidate(row)
            row["queue_reason"] = row["queue_name"]
            scan_rows.append(row)
            if row["attachment_requires_ocr"] == "yes" and row["is_system_thread"] != "yes":
                attachment_rows.extend(attachments)
        if scanned_pages >= args.min_pages and not page_has_recent:
            stopped_on_lower_bound = True
            break
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    attachments_csv = out_dir / "wf1_resume_sweep_attachments.csv"
    scan_csv = out_dir / "wf1_resume_sweep_scan.csv"
    raw_json = out_dir / "wf1_resume_sweep_raw.json"
    if attachment_rows:
        write_csv(attachments_csv, attachment_rows)
    else:
        write_csv(attachments_csv, [], ["message_id", "thread_id", "from_email", "filename", "mime_type", "attachment_id", "size", "part_id", "local_path"])
    write_csv(scan_csv, scan_rows)
    raw_json.write_text(json.dumps(raw_threads, ensure_ascii=False, indent=2), encoding="utf-8")

    report_csv = out_dir / "ocr" / "attachment_extraction_report.csv"
    if attachment_rows:
        subprocess.run(
            [
                "python3",
                str(Path(args.extract_script)),
                "--attachments-csv",
                str(attachments_csv),
                "--output-dir",
                str(out_dir / "ocr"),
                "--token",
                str(Path(args.token)),
            ],
            check=True,
        )
        ocr_merge(scan_rows, report_csv)
        for row in scan_rows:
            row["queue_name"] = classify_candidate(row)
            row["queue_reason"] = row["queue_name"]
        write_csv(scan_csv, scan_rows)

    manifest_rows = build_manifest_rows(scan_rows)
    manifest_csv = out_dir / "writeback_manifest_auto_resume.csv"
    write_csv(
        manifest_csv,
        manifest_rows,
        [
            "manifest_status",
            "manifest_action",
            "match_basis",
            "备注",
            "Source_Tag",
            "频道/作者名称",
            "平台",
            "联系方式",
            "Reply_Contact_Email",
            "latest_price_raw",
            "latest_price_normalized",
            "latest_price_basis",
            "Sort_Bucket",
            "Reply_Count",
            "Reply_Thread_ID",
            "Reply_Last_Message_ID",
            "Reply_Last_Subject",
            "Reply_Last_At",
            "Latest_Inbound_Message_ID",
            "Reply_Stage",
            "Reply_Stream",
            "Pipeline_Stage",
            "Capture_Run_ID",
            "Capture_At",
            "Reply_Status",
            "Reply_Needs_Manual_Review",
            "Reply_Analysis",
            "Manual_Review_Reason",
            "Manual_Review_Focus",
            "current_price_summary",
            "Pricing_Effective_Wave",
            "Pricing_Change_Type",
            "Pricing_Round",
            "Current_Reply_Scenario",
            "Next_Reply_Action",
            "Attachment_OCR_Status",
            "Draft_Workflow_Status",
            "audit_note",
        ],
    )

    if mode == "apply" and manifest_rows:
        (out_dir / "writeback_apply").mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "python3",
                str(Path(args.apply_script)),
                "--master",
                str(master_path),
                "--manifest",
                str(manifest_csv),
                "--batch-dir",
                str(out_dir / "writeback_apply"),
            ],
            check=True,
        )

    triage_rows = build_thread_triage_rows(scan_rows)
    triage_csv = out_dir / "wf1_resume_sweep_triage.csv"
    inventory_csv = out_dir / "wf1_resume_sweep_thread_inventory.csv"
    checkpoint_preview_json = out_dir / "wf1_resume_sweep_checkpoint_preview.json"
    write_csv(triage_csv, triage_rows)
    write_csv(inventory_csv, scan_rows)
    artifact_paths = {
        "scan_csv": str(scan_csv),
        "inventory_csv": str(inventory_csv),
        "triage_csv": str(triage_csv),
        "attachments_csv": str(attachments_csv),
        "raw_json": str(raw_json),
        "manifest_csv": str(manifest_csv),
        "ocr_report_csv": str(report_csv) if report_csv.exists() else "",
        "checkpoint_preview_json": str(checkpoint_preview_json),
    }
    summary = build_summary(
        scan_rows=scan_rows,
        checkpoint=checkpoint,
        lower_bound=lower_bound,
        scanned_pages=scanned_pages,
        stopped_on_lower_bound=stopped_on_lower_bound,
        newest_seen_at=newest_seen_at,
        oldest_seen_at=oldest_seen_at,
        attachment_count=len(attachment_rows),
        manifest_rows=manifest_rows,
        artifact_paths=artifact_paths,
        boundary_thread=boundary_thread,
        mode=mode,
    )
    checkpoint_preview = {
        "workflow": "WF-1",
        "execution_mode": mode,
        "scan_mode": "inbox_latest_to_previous_stop",
        "scan_direction_rule": "always start from current INBOX top, move backward, and stop at the last confirmed stop point",
        "last_window_start_at": newest_seen_at,
        "last_window_end_at": oldest_seen_at,
        "resume_boundary_lower_date": lower_bound.isoformat(sep=" ", timespec="seconds"),
        "connected_to_previous_stop": stopped_on_lower_bound,
        "candidate_threads_seen": summary["thread_count"],
        "message_total_seen": summary["message_total_seen"],
        "latest_price_signal_thread_count": summary["price_signal_thread_count"],
        "new_priced_thread_count": summary["new_price_thread_count"],
        "updated_priced_thread_count": summary["refreshed_price_thread_count"],
        "reply_needed_thread_count": summary["reply_needed_thread_count"],
        "processed_thread_ids": [row.get("thread_id", "") for row in scan_rows],
        "latest_inbound_message_ids": [row.get("latest_inbound_message_id", "") for row in scan_rows if row.get("latest_inbound_message_id", "")],
        "artifact_paths": artifact_paths,
    }
    checkpoint_preview_json.write_text(json.dumps(checkpoint_preview, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "wf1_resume_sweep_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_summary(out_dir / "wf1_resume_sweep_summary.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
