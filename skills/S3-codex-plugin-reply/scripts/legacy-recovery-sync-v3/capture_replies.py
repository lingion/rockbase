#!/usr/bin/env python3
import argparse
import csv
import json
import re
import shutil
import time
from base64 import urlsafe_b64decode
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from http.client import IncompleteRead
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

TOKEN_PATH = Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>")
DEFAULT_HUB_ROOT = Path("${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3")
OUTREACH_FINGERPRINTS = [
    # Mail1 initial outreach
    "i'm annabel from rockbase agency.",
    "we are currently finalizing our premium creator shortlist",
    "links to all your active social channels",
    "current rates for all channels",
    "we have delivered high-impact campaigns for leading brands",
    "we’ve been closely following your content",
    "we would love to officially include your profile in our upcoming proposals",
    # Mail2-4 shared reply templates from S3-ag-reply-draft-ops/references/reply_templates.md
    "thank you for sharing your rates.",
    "thank you for sharing the adjusted rate for a first collaboration",
    "i've noted everything on my side, and i do think there’s real potential for us to work together",
    "we may not move immediately from this thread",
    "thank you for your interest.",
    "to help us assess fit internally, could you please share your current rates",
    "thank you for sending the additional details. we’ve received them on our side.",
    "to help us continue the review efficiently, could you also share your current rates",
    "we do see a strong fit with the types of ai / tech campaigns we are currently reviewing",
    "would you be open to sharing your best agency rate",
    "at this stage, we are reviewing creators for upcoming ai/tech campaigns",
    "budget can vary depending on the format",
    "we are first mapping creator rates before locking final allocations",
    "for now, i’d prefer not to send over partial materials too early while we’re still narrowing campaigns internally",
    "if useful for our internal review in the meantime, you’re also very welcome to share your current rates",
]
SYSTEM_SENDER_PATTERNS = [
    "mailer-daemon@",
    "postmaster@",
    "noreply@",
    "no-reply@",
    "newsletter@",
    "notifications@",
]
SYSTEM_SUBJECT_PATTERNS = [
    "delivery status notification",
    "undeliverable",
    "mail delivery subsystem",
    "returned mail",
    "failure notice",
]

S2_MASTER_FILENAMES = [
    ("Corestar", "【S2 Cold】Corestar-1000-KOL.csv"),
    ("Rockbase", "【S2 Cold】Rockbase-580-KOL.csv"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture recent Gmail replies and sync them into the replied master.")
    parser.add_argument("--master", required=True, help="Path to the replied master CSV.")
    parser.add_argument("--hours", type=int, default=36, help="Fallback lookback window in hours when no checkpoint is available.")
    parser.add_argument("--after-epoch", type=int, default=0, help="Optional explicit lower-bound Unix epoch (seconds). Overrides checkpoint/hours logic.")
    parser.add_argument("--before-epoch", type=int, default=0, help="Optional explicit upper-bound Unix epoch (seconds). When set, only messages before this instant are queried.")
    parser.add_argument("--output-dir", default="", help="Optional explicit run output directory.")
    parser.add_argument("--hub-root", default=str(DEFAULT_HUB_ROOT), help="Long-term reply recovery hub root.")
    parser.add_argument("--overlap-hours", type=int, default=6, help="Overlap hours when resuming from checkpoint.")
    parser.add_argument("--ignore-checkpoint", action="store_true", help="Ignore checkpoint and use the explicit --hours window.")
    parser.add_argument("--write-master", action="store_true", help="Write the updated master back to disk.")
    parser.add_argument("--token", default=str(TOKEN_PATH), help="Path to the Gmail OAuth token JSON.")
    return parser.parse_args()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv_rows(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def decode_b64url(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    raw = urlsafe_b64decode(padded.encode("utf-8"))
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_text(payload: dict) -> Tuple[str, str]:
    plain_parts: List[str] = []
    html_parts: List[str] = []
    stack = [payload]
    while stack:
        part = stack.pop()
        if part.get("parts"):
            stack.extend(part["parts"])
        mime_type = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data", "")
        if mime_type == "text/plain" and data:
            plain_parts.append(decode_b64url(data))
        elif mime_type == "text/html" and data:
            html_parts.append(decode_b64url(data))
    plain = "\n\n".join(p for p in plain_parts if p).strip()
    html = "\n\n".join(p for p in html_parts if p).strip()
    if not plain and html:
        plain = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
        plain = re.sub(r"(?i)<br\\s*/?>", "\n", plain)
        plain = re.sub(r"(?i)</p>", "\n", plain)
        plain = re.sub(r"(?s)<.*?>", " ", plain)
        plain = re.sub(r"\s+", " ", plain)
        plain = plain.strip()
    return plain, html


def parse_headers(message: dict) -> Dict[str, str]:
    payload = message.get("payload", {}) or {}
    return {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}


def parse_dt(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def next_run_id(runs_dir: Path) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    existing = []
    if runs_dir.exists():
        for path in runs_dir.iterdir():
            name = path.name
            if path.is_dir() and name.startswith(f"{today}_run-"):
                suffix = name.split("_run-")[-1]
                if suffix.isdigit():
                    existing.append(int(suffix))
    return f"{today}_run-{max(existing, default=0) + 1:03d}"


def load_checkpoint(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_checkpoint(path: Path, payload: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_creds(token_path: Path) -> Credentials:
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(token_path: Path):
    creds = get_creds(token_path)
    return build("gmail", "v1", credentials=creds), creds


def execute_with_retry(request, *, attempts: int = 4, base_sleep: float = 1.5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return request.execute()
        except (IncompleteRead, HttpError) as exc:
            retryable = isinstance(exc, IncompleteRead)
            if isinstance(exc, HttpError):
                retryable = exc.resp is not None and exc.resp.status in {429, 500, 502, 503, 504}
            last_error = exc
            if not retryable or attempt == attempts:
                raise
            time.sleep(base_sleep * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("request execution failed without a captured error")


def list_messages(service, query: str) -> List[dict]:
    results: List[dict] = []
    page_token = None
    while True:
        payload = execute_with_retry(
            service.users().messages().list(userId="me", q=query, pageToken=page_token, maxResults=500)
        )
        results.extend(payload.get("messages", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return results


def get_thread(service, thread_id: str) -> dict:
    return execute_with_retry(service.users().threads().get(userId="me", id=thread_id, format="full"))


def normalize_email(raw: str) -> str:
    raw = re.sub(r"^[^A-Za-z0-9._%+-]+", "", raw or "")
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw)
    if match:
        return match.group(0).strip().lower()
    return parseaddr(raw or "")[1].strip().lower()


def normalize_subject(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^(?:(?:re|fw|fwd|aw|sv)\s*:\s*)+", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def compact_preview(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[: limit - 3] + "..." if len(text) > limit else text


def is_ignored_system_reply(from_email: str, subject: str) -> bool:
    from_email = (from_email or "").strip().lower()
    subject = (subject or "").strip().lower()
    if any(from_email.startswith(pattern) for pattern in SYSTEM_SENDER_PATTERNS):
        return True
    if any(pattern in subject for pattern in SYSTEM_SUBJECT_PATTERNS):
        return True
    return False


def ensure_columns(rows: List[Dict[str, str]], fieldnames: List[str], required: List[str]) -> List[str]:
    for field in required:
        if field not in fieldnames:
            fieldnames.append(field)
            for row in rows:
                row[field] = row.get(field, "")
    return fieldnames


def collect_seen_message_ids(rows: List[Dict[str, str]]) -> Set[str]:
    seen: Set[str] = set()
    interesting_fields = [c for c in rows[0].keys()] if rows else []
    for row in rows:
        for key, value in row.items():
            if not value:
                continue
            if "message_id" in key.lower():
                for token in re.split(r"[|;,\\s]+", value):
                    token = token.strip()
                    if token:
                        seen.add(token)
    return seen


def build_outbound_map(messages: List[dict], our_email: str) -> Tuple[str, Dict[str, str]]:
    outbound_msgs = []
    for msg in messages:
        headers = parse_headers(msg)
        from_email = normalize_email(headers.get("from", ""))
        if from_email == our_email:
            outbound_msgs.append(msg)
    outbound_msgs.sort(key=lambda m: int(m.get("internalDate", "0")))
    mapping = {}
    parts = []
    for idx, msg in enumerate(outbound_msgs, start=1):
        mid = msg.get("id", "")
        mapping[f"mail{idx}"] = mid
        parts.append(f"mail{idx}:{mid}")
    return "|".join(parts), mapping


def classify_reply_stream(
    messages: List[dict],
    our_email: str,
    latest_in_reply_to: str,
    outbound_map: Dict[str, str],
) -> str:
    for outbound_id in outbound_map.values():
        if outbound_id and latest_in_reply_to and latest_in_reply_to == outbound_id:
            return "Outreach"

    outbound_bodies = []
    has_outbound = False
    for msg in messages:
        headers = parse_headers(msg)
        from_email = normalize_email(headers.get("from", ""))
        if from_email != our_email:
            continue
        has_outbound = True
        body_text, _ = extract_text(msg.get("payload", {}) or {})
        outbound_bodies.append((body_text or "").lower())

    if any(fp in body for body in outbound_bodies for fp in OUTREACH_FINGERPRINTS):
        return "Outreach"
    if has_outbound:
        return "Workstream"
    return "Manual_Review"


def map_reply_stage_to_pipeline_stage(reply_stage: str) -> str:
    mapping = {
        "mail1_waiting_reply": "M1_2_Waiting",
        "mail1_replied_waiting_mail2": "M1_3_Replied_Review",
        "mail2_waiting_reply": "M2_2_Waiting",
        "mail2_replied": "M2_3_Replied_Review",
        "mail3_waiting_reply": "M3_2_Waiting",
        "mail3_replied": "M3_3_Replied_Review",
        "closed": "D1_Done",
        "manual_review": "Z_Manual_Review",
    }
    return mapping.get(reply_stage, "")


def should_update_pipeline_stage(current: str) -> bool:
    current = (current or "").strip()
    if not current:
        return True
    return current in {
        "M1_1_Drafted",
        "M1_2_Waiting",
        "M2_1_Drafted",
        "M2_2_Waiting",
        "M3_1_Drafted",
        "M3_2_Waiting",
        "Z_Manual_Review",
    }


def update_wave_specific_fields(row: Dict[str, str], matched_wave: str, latest_inbound: Dict[str, str], next_action: str) -> None:
    if not matched_wave.startswith("mail"):
        return
    wave_num = matched_wave.removeprefix("mail")
    if not wave_num.isdigit():
        return
    prefix = f"Mail{wave_num}"
    reply_at_field = f"{prefix}_Reply_At"
    summary_field = f"{prefix}_Reply_Summary"
    category_field = f"{prefix}_Reply_Category"
    next_action_field = f"{prefix}_Reply_Next_Action"
    reply_field = f"{prefix}_Reply"
    if reply_at_field in row:
        row[reply_at_field] = latest_inbound.get("reply_at", "")
    if summary_field in row:
        row[summary_field] = compact_preview(latest_inbound.get("body_text", ""))
    if category_field in row:
        row[category_field] = f"{matched_wave}_reply"
    if next_action_field in row:
        row[next_action_field] = next_action
    if reply_field in row:
        row[reply_field] = (latest_inbound.get("body_text", "") or "").strip()
    current_status = (row.get(f"{prefix}_Status", "") or "").strip().lower()
    if current_status in {"", "drafted", "sent", "waiting"}:
        row[f"{prefix}_Status"] = "replied"


def collect_seen_message_ids_from_ledger(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {(row.get("message_id") or "").strip() for row in csv.DictReader(fh) if (row.get("message_id") or "").strip()}


def find_thread_row(rows: List[Dict[str, str]], thread_id: str) -> Optional[Dict[str, str]]:
    for row in rows:
        if (row.get("Reply_Thread_ID") or "").strip() == thread_id:
            return row
    return None


def find_contact_row(rows: List[Dict[str, str]], contact_email: str) -> Optional[Dict[str, str]]:
    for row in rows:
        if (row.get("Reply_Contact_Email") or "").strip().lower() == contact_email:
            return row
    return None


def load_s2_candidates(list_master_dir: Path) -> Dict[str, List[Dict[str, str]]]:
    candidates = []
    for source_tag, filename in S2_MASTER_FILENAMES:
        path = list_master_dir / filename
        if not path.exists():
            continue
        for idx, row in enumerate(read_csv_rows(path), start=2):
            candidate = dict(row)
            candidate["Source_Tag"] = source_tag
            candidate["contact_email"] = normalize_email(candidate.get("联系方式", ""))
            candidate["subject_norm"] = normalize_subject(candidate.get("Mail1_Subject", ""))
            candidate["_source_rownum"] = str(idx)
            candidates.append(candidate)
    by_subject: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in candidates:
        if row["subject_norm"]:
            by_subject[row["subject_norm"]].append(row)
    by_subject["_all"] = candidates
    return by_subject


def collapse_bootstrap_candidates(candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not candidates:
        return None
    emails = {c.get("contact_email", "") for c in candidates if c.get("contact_email", "")}
    account_ids = {re.sub(r"\s+", " ", (c.get("账号ID", "") or "").strip()).lower() for c in candidates if c.get("账号ID", "")}
    creators = {re.sub(r"\s+", " ", (c.get("频道/作者名称", "") or "").strip()).lower() for c in candidates if c.get("频道/作者名称", "")}
    same_contact = (len(emails) == 1 and len(emails) > 0) or (len(account_ids) == 1 and len(account_ids) > 0) or (len(creators) == 1 and len(creators) > 0)
    if not same_contact:
        return None

    platform_rank = {"youtube": 0, "tiktok": 1, "instagram": 2, "x": 3, "twitter": 3}
    status_rank = {"sent": 0, "drafted": 1, "": 2}

    def sort_key(candidate: Dict[str, str]) -> Tuple[int, int, int]:
        status = (candidate.get("Mail1发出状态", "") or "").strip().lower()
        platform = (candidate.get("平台", "") or "").strip().lower()
        return (
            status_rank.get(status, 9),
            platform_rank.get(platform, 9),
            int(candidate.get("_source_rownum", "999999") or "999999"),
        )

    return sorted(candidates, key=sort_key)[0]


def find_s2_bootstrap_candidate(
    s2_candidates: Dict[str, List[Dict[str, str]]],
    latest_inbound: Dict[str, str],
) -> Tuple[Optional[Dict[str, str]], str]:
    from_email = normalize_email(latest_inbound.get("from_email", ""))
    subject_norm = normalize_subject(latest_inbound.get("subject", ""))
    candidates = s2_candidates.get(subject_norm, [])
    email_candidates = [c for c in candidates if c.get("contact_email", "") and c.get("contact_email", "") == from_email]

    if len(email_candidates) == 1:
        return email_candidates[0], "subject_email_unique"
    if len(email_candidates) > 1:
        collapsed = collapse_bootstrap_candidates(email_candidates)
        if collapsed is not None:
            return collapsed, "subject_email_ambiguous_collapsed"
        return None, "subject_email_ambiguous"
    if len(candidates) == 1:
        return candidates[0], "subject_unique"
    if len(candidates) > 1:
        collapsed = collapse_bootstrap_candidates(candidates)
        if collapsed is not None:
            return collapsed, "subject_ambiguous_collapsed"
        return None, "subject_ambiguous"

    same_email = [c for c in s2_candidates.get("_all", []) if c.get("contact_email", "") and c.get("contact_email", "") == from_email]
    if len(same_email) == 1:
        return same_email[0], "email_unique_only"
    if len(same_email) > 1:
        collapsed = collapse_bootstrap_candidates(same_email)
        if collapsed is not None:
            return collapsed, "email_ambiguous_collapsed"
        return None, "email_ambiguous_only"
    return None, "no_match"


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    hub_root = Path(args.hub_root)
    hub_root.mkdir(parents=True, exist_ok=True)
    runs_dir = hub_root / "01-runs"
    bodies_root = hub_root / "04-bodies"
    ledgers_root = hub_root / "06-ledgers"
    state_root = hub_root / "00-state"
    checkpoint_path = state_root / "reply_recovery_checkpoint.json"
    message_ledger_path = ledgers_root / "reply_message_ledger.csv"

    run_id = next_run_id(runs_dir)
    output_dir = Path(args.output_dir) if args.output_dir else (runs_dir / run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    bodies_root.mkdir(parents=True, exist_ok=True)
    ledgers_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    master_rows = read_csv_rows(master_path)
    if not master_rows:
        raise SystemExit("master CSV is empty")

    fieldnames = list(master_rows[0].keys())
    s2_candidates = load_s2_candidates(master_path.parent)
    required_columns = [
        "Reply_Status",
        "Reply_Needs_Manual_Review",
        "Ops_Notes",
        "Outbound_Message_IDs",
        "Latest_Inbound_Message_ID",
        "Latest_Inbound_InReplyTo",
        "Reply_Last_Message_ID",
        "Reply_Body_File",
        "Reply_Stream",
        "Pipeline_Stage",
        "Capture_Run_ID",
        "Capture_At",
        "Reply_Stage",
        "Reply_Analysis",
        "Mail1_Pricing_Excerpt",
        "Mail1_Reply_At",
        "Mail1_Reply_Summary",
        "Mail1_Reply_Category",
        "Mail1_Reply_Next_Action",
        "Mail1_Reply",
        "Mail2_Pricing_Excerpt",
        "Mail2_Reply_At",
        "Mail2_Reply_Summary",
        "Mail2_Reply_Category",
        "Mail2_Reply_Next_Action",
        "Mail2_Reply",
        "Mail3_Pricing_Excerpt",
        "Mail3_Reply_At",
        "Mail3_Reply_Summary",
        "Mail3_Reply_Category",
        "Mail3_Reply_Next_Action",
        "Mail3_Reply",
        "Pricing_Effective_Wave",
        "Pricing_Change_Type",
    ]
    fieldnames = ensure_columns(master_rows, fieldnames, required_columns)

    token_path = Path(args.token)
    if not token_path.exists():
        raise SystemExit(f"token not found: {token_path}")

    service, creds = build_service(token_path)
    profile = service.users().getProfile(userId="me").execute()
    our_email = normalize_email(profile.get("emailAddress", ""))

    capture_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    checkpoint = {} if args.ignore_checkpoint else load_checkpoint(checkpoint_path)
    if args.after_epoch:
        cutoff_dt = datetime.fromtimestamp(args.after_epoch, tz=timezone.utc)
        cutoff_source = "explicit_after_epoch"
    elif checkpoint.get("last_success_reply_at"):
        cutoff_dt = parse_dt(checkpoint["last_success_reply_at"]) - timedelta(hours=args.overlap_hours)
        cutoff_source = "checkpoint_overlap"
    else:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        cutoff_source = "hours_fallback"
    capture_run_id = run_id
    cutoff_epoch = int(cutoff_dt.timestamp())
    before_epoch = int(args.before_epoch) if args.before_epoch else 0

    query_parts = [f"after:{cutoff_epoch}"]
    if before_epoch:
        query_parts.append(f"before:{before_epoch}")
    query = " ".join(query_parts)
    message_summaries = list_messages(service, query)
    thread_ids = sorted({m.get("threadId", "") for m in message_summaries if m.get("threadId")})

    seen_message_ids = collect_seen_message_ids(master_rows) | collect_seen_message_ids_from_ledger(message_ledger_path)
    updates: List[Dict[str, str]] = []
    audit_rows: List[Dict[str, str]] = []
    ledger_rows: List[Dict[str, str]] = []
    thread_stats = {
        "threads_found": len(thread_ids),
        "threads_updated": 0,
        "threads_manual_review": 0,
        "threads_ignored": 0,
        "messages_seen": len(message_summaries),
        "messages_skipped_duplicate": 0,
        "rows_updated": 0,
    }

    for thread_id in thread_ids:
        thread = get_thread(service, thread_id)
        messages = thread.get("messages", [])
        messages.sort(key=lambda m: int(m.get("internalDate", "0")))

        thread_messages = []
        for msg in messages:
            headers = parse_headers(msg)
            from_email = normalize_email(headers.get("from", ""))
            to_email = normalize_email(headers.get("to", ""))
            message_id = msg.get("id", "")
            internal_dt = datetime.fromtimestamp(int(msg.get("internalDate", "0")) / 1000, tz=timezone.utc)
            if internal_dt < cutoff_dt:
                continue
            if message_id in seen_message_ids:
                thread_stats["messages_skipped_duplicate"] += 1
                continue
            body_text, _ = extract_text(msg.get("payload", {}) or {})
            thread_messages.append(
                {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "internal_dt": internal_dt,
                    "reply_at": headers.get("date", ""),
                    "from_email": from_email,
                    "to_email": to_email,
                    "subject": headers.get("subject", ""),
                    "in_reply_to": headers.get("in-reply-to", ""),
                    "body_text": body_text,
                }
            )

        inbound_messages = [m for m in thread_messages if m["from_email"] and m["from_email"] != our_email]
        if not inbound_messages:
            continue

        latest_inbound = max(inbound_messages, key=lambda m: (m["internal_dt"], m["message_id"]))
        latest_inbound_id = latest_inbound["message_id"]
        latest_in_reply_to = latest_inbound["in_reply_to"].strip()
        latest_inbound_dt = latest_inbound["internal_dt"]

        if is_ignored_system_reply(latest_inbound["from_email"], latest_inbound["subject"]):
            audit_rows.append(
                {
                    "issue_type": "ignored_system_reply",
                    "thread_id": thread_id,
                    "message_id": latest_inbound_id,
                    "from_email": latest_inbound["from_email"],
                    "details": f"subject={latest_inbound['subject']}",
                }
            )
            thread_stats["threads_ignored"] += 1
            continue

        outbound_map_text, outbound_map = build_outbound_map(messages, our_email)
        reply_stream = classify_reply_stream(messages, our_email, latest_in_reply_to, outbound_map)
        reply_stage = "manual_review"
        reply_category = "manual_review"
        next_action = "manual_review"
        matched_wave = ""
        for wave_name, outbound_id in outbound_map.items():
            if outbound_id and latest_in_reply_to and latest_in_reply_to == outbound_id:
                matched_wave = wave_name
                break
        if matched_wave == "mail1":
            reply_stage = "mail1_replied_waiting_mail2"
            reply_category = "mail1_reply"
            next_action = "prepare_mail2"
        elif matched_wave == "mail2":
            reply_stage = "mail2_replied"
            reply_category = "mail2_reply"
            next_action = "review_mail2_reply"
        elif matched_wave == "mail3":
            reply_stage = "mail3_replied"
            reply_category = "mail3_reply"
            next_action = "review_and_close"
        elif matched_wave.startswith("mail") and matched_wave[4:].isdigit():
            reply_stage = f"{matched_wave}_replied"
            reply_category = f"{matched_wave}_reply"
            next_action = "review_followup_reply"

        analysis = f"category={reply_category} | summary={compact_preview(latest_inbound['body_text'])} | next={next_action}"

        body_file = bodies_root / f"{latest_inbound_id}.txt"
        body_file.write_text(latest_inbound["body_text"] or "", encoding="utf-8")

        ledger_rows.append(
            {
                "message_id": latest_inbound_id,
                "thread_id": thread_id,
                "reply_at": latest_inbound["reply_at"],
                "from_email": latest_inbound["from_email"],
                "capture_run_id": capture_run_id,
                "account_id": "",
                "reply_stream": reply_stream,
            }
        )

        if reply_stream != "Outreach":
            audit_rows.append(
                {
                    "issue_type": "non_outreach_reply",
                    "thread_id": thread_id,
                    "message_id": latest_inbound_id,
                    "from_email": latest_inbound["from_email"],
                    "details": f"reply_stream={reply_stream} | subject={latest_inbound['subject']}",
                }
            )
            if reply_stream == "Manual_Review":
                thread_stats["threads_manual_review"] += 1
            continue

        row = find_thread_row(master_rows, thread_id)
        sync_action = "updated"
        template_row = None
        if row is None:
            template_row = find_contact_row(master_rows, latest_inbound["from_email"])
            if template_row is None:
                bootstrap_row, bootstrap_match = find_s2_bootstrap_candidate(s2_candidates, latest_inbound)
                subject_norm = normalize_subject(latest_inbound["subject"])
                if bootstrap_row is None:
                    issue_type = "no_master_match"
                    details = f"bootstrap_match={bootstrap_match} | subject={subject_norm}"
                    if is_ignored_system_reply(latest_inbound["from_email"], latest_inbound["subject"]):
                        issue_type = "ignored_bounce_or_system_reply"
                        details = f"bootstrap_match={bootstrap_match} | subject={subject_norm}"
                    audit_rows.append(
                        {
                            "issue_type": issue_type,
                            "thread_id": thread_id,
                            "message_id": latest_inbound_id,
                            "from_email": latest_inbound["from_email"],
                            "details": details,
                        }
                    )
                    if issue_type.startswith("ignored_"):
                        thread_stats["threads_ignored"] += 1
                    else:
                        thread_stats["threads_manual_review"] += 1
                    continue
                template_row = bootstrap_row
            row = {field: template_row.get(field, "") for field in fieldnames}
            master_rows.append(row)
            sync_action = "appended"

        row["账号ID"] = row.get("账号ID", "") or (template_row.get("账号ID", "") if template_row else "")
        row["Reply_Thread_ID"] = thread_id
        row["Reply_Contact_Email"] = latest_inbound["from_email"]

        row["Outbound_Message_IDs"] = outbound_map_text
        row["Latest_Inbound_Message_ID"] = latest_inbound_id
        row["Latest_Inbound_InReplyTo"] = latest_in_reply_to
        row["Capture_Run_ID"] = capture_run_id
        row["Capture_At"] = capture_at
        row["Reply_Stage"] = reply_stage
        row["Reply_Analysis"] = analysis
        row["Reply_Status"] = "replied"
        row["Reply_Stream"] = reply_stream
        row["Reply_Last_Message_ID"] = latest_inbound_id
        row["Reply_Last_At"] = latest_inbound["reply_at"]
        row["Reply_Last_Subject"] = latest_inbound["subject"]
        row["Reply_Body_File"] = str(body_file.relative_to(hub_root))
        if sync_action == "appended" and template_row is not None and template_row.get("_source_rownum"):
            bootstrap_match = find_s2_bootstrap_candidate(s2_candidates, latest_inbound)[1]
            row["Ops_Notes"] = (row.get("Ops_Notes", "") + ("\n" if row.get("Ops_Notes", "") else "") + f"[bootstrap] matched_by={bootstrap_match} | source={template_row.get('Source_Tag', '')} row={template_row.get('_source_rownum', '')}").strip()
            if bootstrap_match.endswith("_collapsed"):
                row["Reply_Needs_Manual_Review"] = "yes"
        if "Reply_Category" in row:
            row["Reply_Category"] = reply_category
        update_wave_specific_fields(row, matched_wave, latest_inbound, next_action)
        proposed_pipeline = map_reply_stage_to_pipeline_stage(reply_stage)
        if proposed_pipeline and should_update_pipeline_stage(row.get("Pipeline_Stage", "")):
            row["Pipeline_Stage"] = proposed_pipeline

        seen_message_ids.add(latest_inbound_id)
        ledger_rows[-1]["account_id"] = row.get("账号ID", "")
        updates.append(
            {
                "账号ID": row.get("账号ID", ""),
                "Reply_Thread_ID": thread_id,
                "Latest_Inbound_Message_ID": latest_inbound_id,
                "Latest_Inbound_InReplyTo": latest_in_reply_to,
                "Reply_Stream": reply_stream,
                "Reply_Stage": reply_stage,
                "Reply_Analysis": analysis,
                "Reply_Body_File": row.get("Reply_Body_File", ""),
                "Sync_Action": sync_action,
            }
        )
        thread_stats["threads_updated"] += 1
        thread_stats["rows_updated"] += 1

    preview_path = output_dir / "recent_reply_window_preview.csv"
    audit_path = output_dir / "recent_reply_window_audit.csv"
    summary_path = output_dir / "recent_reply_window_summary.json"
    write_csv(preview_path, updates, ["账号ID", "Reply_Thread_ID", "Latest_Inbound_Message_ID", "Latest_Inbound_InReplyTo", "Reply_Stream", "Reply_Stage", "Reply_Analysis", "Reply_Body_File", "Sync_Action"])
    write_csv(audit_path, audit_rows, ["issue_type", "thread_id", "message_id", "from_email", "details"])

    summary = {
        "capture_run_id": capture_run_id,
        "capture_at": capture_at,
        "hours": args.hours,
        "after_epoch": cutoff_epoch,
        "before_epoch": before_epoch,
        "cutoff_source": cutoff_source,
        "cutoff_at": cutoff_dt.isoformat(),
        "hub_root": str(hub_root.resolve()),
        "profile_email": profile.get("emailAddress", ""),
        **thread_stats,
        "preview_csv": str(preview_path.resolve()),
        "audit_csv": str(audit_path.resolve()),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_csv_rows(
        message_ledger_path,
        ledger_rows,
        ["message_id", "thread_id", "reply_at", "from_email", "capture_run_id", "account_id", "reply_stream"],
    )

    if args.write_master:
        write_csv(master_path, master_rows, fieldnames)
        latest_reply_at = ""
        latest_message_id = ""
        latest_thread_id = ""
        if ledger_rows:
            latest = max(ledger_rows, key=lambda row: parse_dt(row.get("reply_at", "")))
            latest_reply_at = latest.get("reply_at", "")
            latest_message_id = latest.get("message_id", "")
            latest_thread_id = latest.get("thread_id", "")
        save_checkpoint(
            checkpoint_path,
            {
                "last_run_id": capture_run_id,
                "last_sync_started_at": capture_at,
                "last_sync_completed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "last_success_reply_at": latest_reply_at,
                "last_success_message_id": latest_message_id,
                "last_success_thread_id": latest_thread_id,
            },
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
