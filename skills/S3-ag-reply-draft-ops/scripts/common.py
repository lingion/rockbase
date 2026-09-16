import argparse
import base64
import csv
import hashlib
import json
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error, request

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


STATUS_PENDING = "pending"
STATUS_SAMPLED = "sampled"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

DEFAULT_TOKEN_FILE = "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>"


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, [{k: (v or "") for k, v in row.items()} for row in reader]


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def infer_manifest_fieldnames(rows: Sequence[Dict[str, str]]) -> List[str]:
    base = [
        "job_id",
        "row_id",
        "account_id",
        "reply_wave",
        "template_code",
        "template_name",
        "to",
        "subject",
        "body",
        "thread_id",
        "latest_message_id",
        "status",
        "draft_id",
        "attempt_count",
        "error",
        "created_at",
        "updated_at",
    ]
    extra = []
    for row in rows:
        for key in row:
            if key not in base and key not in extra:
                extra.append(key)
    return base + extra


def load_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    _, rows = read_csv_rows(path)
    return rows


def save_manifest(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    write_csv_rows(path, infer_manifest_fieldnames(rows), rows)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_job_id(row_id: str, thread_id: str, template_code: str) -> str:
    return sha256_text(f"{row_id}|{thread_id}|{template_code}")[:20]


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


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


def gmail_request(access_token: str, method: str, path: str, body: Optional[dict] = None, timeout: int = 30) -> dict:
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/{path.lstrip('/')}"
    data = None
    headers = {"Authorization": f"Bearer {access_token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gmail API {exc.code}: {detail}") from exc
    return json.loads(payload.decode("utf-8")) if payload else {}


def gmail_get_profile(access_token: str) -> dict:
    return gmail_request(access_token, "GET", "profile")


def gmail_get_message_headers(access_token: str, message_id: str) -> dict:
    payload = gmail_request(
        access_token,
        "GET",
        f"messages/{message_id}?format=metadata&metadataHeaders=Message-ID&metadataHeaders=References&metadataHeaders=Subject&metadataHeaders=To",
    )
    headers = payload.get("payload", {}).get("headers", [])
    out = {}
    for header in headers:
        name = header.get("name", "").lower()
        if name:
            out[name] = header.get("value", "")
    return out


def build_reply_raw(to_value: str, subject: str, body: str, headers: dict[str, str]) -> str:
    msg = EmailMessage()
    msg["To"] = to_value
    msg["Subject"] = subject
    original_msg_id = headers.get("message-id", "").strip()
    original_refs = headers.get("references", "").strip()
    if original_msg_id:
        msg["In-Reply-To"] = original_msg_id
        msg["References"] = f"{original_refs} {original_msg_id}".strip() if original_refs else original_msg_id
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail_create_reply_draft(access_token: str, to_value: str, subject: str, body: str, thread_id: str, latest_message_id: str) -> dict:
    headers = gmail_get_message_headers(access_token, latest_message_id)
    raw = build_reply_raw(to_value, subject, body, headers)
    return gmail_request(
        access_token,
        "POST",
        "drafts",
        body={"message": {"raw": raw, "threadId": thread_id}},
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--access-token", default=os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", ""))
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-csv", default="")
