import argparse
import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error, parse, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


STATUS_PENDING = "pending"
STATUS_SAMPLED = "sampled"
STATUS_DONE = "done"
STATUS_SENT = "sent"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"
STATUS_DUPLICATE = "duplicate"
STATUS_DELETED = "deleted"

DEFAULT_TOKEN_FILE = "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>"


@dataclass
class GmailConfig:
    access_token: str
    user_id: str = "me"


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = []
        for row in reader:
            rows.append({k: (v or "") for k, v in row.items()})
    return fieldnames, rows


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_job_id(row_id: str, to_value: str, subject: str) -> str:
    raw = f"{row_id}|{to_value.strip()}|{subject.strip()}"
    return sha256_text(raw)[:20]


def normalize_row_id(index_1_based: int, raw_row_id: str = "") -> str:
    raw = raw_row_id.strip()
    return raw or str(index_1_based)


def split_recipients(value: str, mode: str) -> List[str]:
    text = (value or "").strip()
    if not text:
        return []
    if mode == "strict":
        return [text]
    parts = [p.strip() for p in text.replace(";", ",").replace("/", ",").split(",")]
    return [p for p in parts if p]


EMAIL_RE = re.compile(r"[A-Z0-9][A-Z0-9._%+-]*@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
BLOCKED_EMAIL_DOMAINS = {
    "sentry.io",
    "wixpress.com",
}
BLOCKED_TLDS = {
    "avif",
    "gif",
    "jpeg",
    "jpg",
    "png",
    "svg",
    "webp",
}


def clean_recipient_value(value: str) -> List[str]:
    text = (value or "").strip()
    if not text:
        return []
    cleaned = []
    for match in EMAIL_RE.finditer(text):
        email = match.group(0)
        domain = email.split("@", 1)[1].lower()
        suffix = domain.rsplit(".", 1)[-1]
        if suffix in BLOCKED_TLDS:
            continue
        if domain in BLOCKED_EMAIL_DOMAINS or domain.endswith(".sentry.io"):
            continue
        cleaned.append(email)
    return cleaned


def normalize_recipients(value: str, mode: str) -> List[str]:
    recipients = split_recipients(value, mode)
    cleaned: List[str] = []
    for recipient in recipients:
        cleaned.extend(clean_recipient_value(recipient))
    seen = set()
    normalized = []
    for recipient in cleaned:
        key = recipient.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(recipient)
    return normalized


def infer_manifest_fieldnames(rows: Sequence[Dict[str, str]]) -> List[str]:
    base = [
        "job_id",
        "row_id",
        "source_ref",
        "to",
        "subject",
        "body",
        "body_hash",
        "status",
        "draft_id",
        "attempt_count",
        "error",
        "created_at",
        "updated_at",
    ]
    extra = []
    for row in rows:
        for key in row.keys():
            if key not in base and key not in extra:
                extra.append(key)
    return base + extra


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    _, rows = read_csv_rows(path)
    return rows


def save_manifest(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    fieldnames = infer_manifest_fieldnames(rows)
    write_csv_rows(path, fieldnames, rows)


def get_token_file_access_token(token_file: str) -> str:
    creds = Credentials.from_authorized_user_file(
        token_file,
        scopes=[
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.readonly",
        ],
    )
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(token_file).write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(f"Token file is invalid and cannot refresh: {token_file}")
    if not creds.token:
        raise RuntimeError(f"Token file did not yield an access token: {token_file}")
    return creds.token


def build_gmail_config(access_token: Optional[str], user_id: str, token_file: str) -> GmailConfig:
    token = access_token or get_token_file_access_token(token_file)
    return GmailConfig(access_token=token, user_id=user_id)


def _direct_env() -> Dict[str, str]:
    env = os.environ.copy()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    return env


def _direct_urlopen(req: request.Request, timeout: int) -> bytes:
    opener = request.build_opener(request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def gmail_request(
    config: GmailConfig,
    method: str,
    path: str,
    body: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    timeout = int(os.environ.get("GMAIL_REQUEST_TIMEOUT", str(timeout)) or timeout)
    url = f"https://gmail.googleapis.com/gmail/v1/users/{config.user_id}/{path.lstrip('/')}"
    data = None
    headers = {"Authorization": f"Bearer {config.access_token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    def run_curl() -> bytes:
        curl_cmd = [
            "curl",
            "--http1.1",
            "-sS",
            "--connect-timeout",
            str(min(timeout, 10)),
            "--max-time",
            str(timeout),
            "-X",
            method.upper(),
            url,
            "-H",
            f"Authorization: Bearer {config.access_token}",
        ]
        if body is not None:
            curl_cmd.extend(
                [
                    "-H",
                    "Content-Type: application/json",
                    "--data-binary",
                    json.dumps(body, ensure_ascii=False),
                ]
            )
        proc = subprocess.run(
            curl_cmd,
            capture_output=True,
            text=False,
            timeout=timeout + 2,
            env=_direct_env(),
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"gmail_request curl failed ({proc.returncode}): {stderr}")
        return proc.stdout

    try:
        # Prefer direct curl over HTTP/1.1 without inheriting proxy env.
        # In this workspace, POST /drafts may hang when local proxy vars leak into urllib/httplib2.
        payload = run_curl()
        if not payload:
            req = request.Request(url, data=data, headers=headers, method=method.upper())
            payload = _direct_urlopen(req, timeout=timeout)
    except Exception:
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        payload = _direct_urlopen(req, timeout=timeout)
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def gmail_get_profile(config: GmailConfig) -> dict:
    return gmail_request(config, "GET", "profile")


def email_to_raw(to_value: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["To"] = to_value
    msg["Subject"] = subject
    msg.set_content(body)

    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail_create_draft(config: GmailConfig, to_value: str, subject: str, body: str) -> dict:
    return gmail_request(
        config,
        "POST",
        "drafts",
        body={"message": {"raw": email_to_raw(to_value, subject, body)}},
    )


def gmail_delete_draft(config: GmailConfig, draft_id: str) -> None:
    gmail_request(config, "DELETE", f"drafts/{draft_id}")


def gmail_send_draft(config: GmailConfig, draft_id: str) -> dict:
    payload = gmail_request(
        config,
        "POST",
        "drafts/send",
        body={"id": draft_id},
    )
    if not payload or not payload.get("id"):
        raise RuntimeError(f"gmail_send_draft returned empty payload for draft_id={draft_id}")
    return payload


def gmail_list_drafts(config: GmailConfig) -> List[dict]:
    drafts: List[dict] = []
    page_token: Optional[str] = None
    while True:
        query = "drafts?maxResults=500"
        if page_token:
            query += f"&pageToken={parse.quote(page_token)}"
        payload = gmail_request(config, "GET", query)
        drafts.extend(payload.get("drafts", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return drafts


def gmail_get_subject_only(config: GmailConfig, draft_id: str) -> Tuple[str, int]:
    payload = gmail_request(
        config,
        "GET",
        f"drafts/{draft_id}?format=metadata&metadataHeaders=Subject&metadataHeaders=To",
    )
    message = payload.get("message", {})
    headers = message.get("payload", {}).get("headers", [])
    subject = ""
    to_value = ""
    for header in headers:
        name = header.get("name", "").lower()
        if name == "subject":
            subject = header.get("value", "").strip()
        elif name == "to":
            to_value = header.get("value", "").strip()
    internal_date = int(message.get("internalDate", "0") or "0")
    return f"{to_value}|||{subject}", internal_date


def _b64url_decode(data: str) -> bytes:
    if not data:
        return b""
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\r\n", "\n").replace("\r", "\n").strip())


def _extract_body_text(msg) -> str:
    if msg.is_multipart():
        plain_parts: List[str] = []
        html_parts: List[str] = []
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            ctype = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                plain_parts.append(str(content))
            elif ctype == "text/html":
                html_parts.append(str(content))
        return "\n".join(plain_parts or html_parts)
    try:
        return str(msg.get_content())
    except Exception:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def gmail_get_draft_signature(config: GmailConfig, draft_id: str) -> Tuple[str, int]:
    payload = gmail_request(config, "GET", f"drafts/{draft_id}?format=raw")
    message = payload.get("message", {})
    raw = message.get("raw", "")
    parsed = BytesParser(policy=policy.default).parsebytes(_b64url_decode(raw))
    to_value = _normalize_text(parsed.get("To", ""))
    subject = _normalize_text(parsed.get("Subject", ""))
    body_hash = sha256_text(_normalize_text(_extract_body_text(parsed)))
    internal_date = int(message.get("internalDate", "0") or "0")
    return f"{to_value}|||{subject}|||{body_hash}", internal_date


def summarize_manifest(rows: Sequence[Dict[str, str]]) -> dict:
    counter = Counter(row.get("status", "") for row in rows)
    return {
        "total_jobs": len(rows),
        "completed_jobs": counter.get(STATUS_DONE, 0),
        "sampled_jobs": counter.get(STATUS_SAMPLED, 0),
        "sent_jobs": counter.get(STATUS_SENT, 0),
        "failed_jobs": counter.get(STATUS_FAILED, 0),
        "duplicate_jobs": counter.get(STATUS_DUPLICATE, 0),
        "deleted_jobs": counter.get(STATUS_DELETED, 0),
        "pending_jobs": counter.get(STATUS_PENDING, 0),
    }


def print_json(data: dict) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


def add_common_gmail_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user-id", default="me", help="Gmail user id, default 'me'.")
    parser.add_argument(
        "--access-token",
        default=os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", ""),
        help="Optional access token override. Default uses the Gmail OAuth token file.",
    )
    parser.add_argument(
        "--token-file",
        default=DEFAULT_TOKEN_FILE,
        help="Path to the Gmail OAuth token JSON file.",
    )


def add_manifest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="Path to the manifest CSV.")


def add_source_writeback_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-csv",
        default="",
        help="Optional source CSV path for writeback after draft creation.",
    )
    parser.add_argument(
        "--source-status-field",
        default="Mail1发出状态",
        help="Source status field name used for writeback.",
    )
    parser.add_argument(
        "--source-drafted-value",
        default="drafted",
        help="Value written back to source status field after draft creation.",
    )


def writeback_source_status(
    source_csv: str,
    row_ids: Sequence[str],
    status_field: str,
    status_value: str,
) -> int:
    if not source_csv or not row_ids:
        return 0
    path = Path(source_csv)
    fieldnames, rows = read_csv_rows(path)
    updated = 0
    target_ids = {str(row_id) for row_id in row_ids}
    for index_1_based, row in enumerate(rows, start=2):
        row_account_id = str(row.get("账号ID", "")).strip()
        row_source_number = str(row.get("Source_Row_Number", "")).strip()
        if str(index_1_based) in target_ids or row_account_id in target_ids or row_source_number in target_ids:
            row[status_field] = status_value
            updated += 1
    write_csv_rows(path, fieldnames, rows)
    return updated
