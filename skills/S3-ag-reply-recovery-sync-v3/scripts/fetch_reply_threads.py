#!/usr/bin/env python3
import argparse
import base64
import csv
import html
import json
import re
import time
from email.utils import parseaddr
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a small Gmail thread batch with full bodies and attachment inventory.")
    parser.add_argument("--master", required=True, help="Path to master CSV.")
    parser.add_argument("--thread-ids-json", required=True, help="Path to thread_ids.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for output files.")
    parser.add_argument("--limit", type=int, default=20, help="Number of thread ids to process from the list.")
    parser.add_argument("--sleep-seconds", type=float, default=0.35, help="Delay between Gmail API requests.")
    parser.add_argument("--token", default=str(TOKEN_PATH), help="Path to the Gmail OAuth token JSON.")
    return parser.parse_args()


def read_master_contacts(path: Path) -> Dict[str, List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    mapping: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        email = (
            row.get("Reply_Contact_Email")
            or row.get("联系方式")
            or row.get("联系邮箱")
            or ""
        ).strip().lower()
        if not email:
            continue
        mapping.setdefault(email, []).append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "平台": row.get("平台", ""),
            }
        )
    return mapping


def get_creds(token_path: Path) -> Credentials:
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        else:  # pragma: no cover - token state issue
            raise RuntimeError(f"OAuth token at {token_path} is invalid and cannot be refreshed.")
    return creds


def build_service(token_path: Path):
    creds = get_creds(token_path)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def gmail_execute(request_obj, sleep_seconds: float, retries: int = 6) -> dict:
    last_exc = None
    for attempt in range(retries):
        try:
            payload = request_obj.execute()
            time.sleep(sleep_seconds)
            return payload
        except HttpError as exc:  # pragma: no cover - network-dependent
            last_exc = exc
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status not in {403, 429, 500, 503} or attempt == retries - 1:
                break
            time.sleep((2 ** attempt) * 0.5)
        except Exception as exc:  # pragma: no cover - network-dependent
            last_exc = exc
            if attempt == retries - 1:
                break
            time.sleep((2 ** attempt) * 0.5)
    raise last_exc


def b64url_decode(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", text)
    text = re.sub(r"(?i)<br\\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_bodies(payload: dict) -> Tuple[str, str, List[dict]]:
    plain_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[dict] = []
    stack = [payload]
    while stack:
        part = stack.pop()
        if part.get("parts"):
            stack.extend(part["parts"])
        mime_type = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data", "")
        filename = (part.get("filename") or "").strip()
        attachment_id = body.get("attachmentId", "")
        if mime_type == "text/plain" and data:
            plain_parts.append(b64url_decode(data))
        elif mime_type == "text/html" and data:
            html_parts.append(b64url_decode(data))
        if filename or attachment_id:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": mime_type,
                    "attachment_id": attachment_id,
                    "size": body.get("size", 0) or 0,
                    "part_id": part.get("partId", ""),
                }
            )
    plain = "\n\n".join(p for p in plain_parts if p).strip()
    html_text = "\n\n".join(p for p in html_parts if p).strip()
    if not plain and html_text:
        plain = strip_html(html_text)
    return plain, html_text, attachments


def summarize_text(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[: limit - 3] + "..." if len(text) > limit else text


def write_csv(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    thread_ids_path = Path(args.thread_ids_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    master_contacts = read_master_contacts(master_path)
    with thread_ids_path.open("r", encoding="utf-8") as fh:
        thread_ids = json.load(fh)[: args.limit]

    service = build_service(Path(args.token))
    profile = gmail_execute(service.users().getProfile(userId="me"), args.sleep_seconds)

    rows_out: List[Dict[str, str]] = []
    attachments_out: List[Dict[str, str]] = []
    raw_jsonl_path = output_dir / f"reply_batch_full_first{args.limit}.jsonl"
    errors: List[Dict[str, str]] = []

    with raw_jsonl_path.open("w", encoding="utf-8") as raw_fh:
        for thread_id in thread_ids:
            try:
                thread = gmail_execute(
                    service.users().threads().get(userId="me", id=thread_id, format="full"),
                    args.sleep_seconds,
                )
            except Exception as exc:  # pragma: no cover - network-dependent
                errors.append({"thread_id": thread_id, "error": str(exc)})
                continue

            for msg in thread.get("messages", []):
                payload = msg.get("payload", {}) or {}
                headers_map = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
                from_email = parseaddr(headers_map.get("from", ""))[1].strip().lower()
                if from_email not in master_contacts:
                    continue

                body_text, body_html, attachments = extract_bodies(payload)
                attachment_names = [a["filename"] for a in attachments if a["filename"]]
                attachment_mimes = [a["mime_type"] for a in attachments if a["mime_type"]]
                has_pdf = any(
                    a["filename"].lower().endswith(".pdf") or a["mime_type"] == "application/pdf"
                    for a in attachments
                )
                has_image = any(a["mime_type"].startswith("image/") for a in attachments if a["mime_type"])
                has_doc = any(
                    a["filename"].lower().endswith((".doc", ".docx")) or "word" in a["mime_type"]
                    for a in attachments
                )
                body_path = output_dir / "bodies" / f"{msg.get('id','')}.txt"
                body_path.parent.mkdir(parents=True, exist_ok=True)
                body_path.write_text(body_text, encoding="utf-8")
                if body_html:
                    html_path = output_dir / "bodies" / f"{msg.get('id','')}.html"
                    html_path.write_text(body_html, encoding="utf-8")
                    body_html_rel = str(html_path.relative_to(output_dir))
                else:
                    body_html_rel = ""

                contact_rows = master_contacts[from_email]
                row = {
                    "message_id": msg.get("id", ""),
                    "thread_id": thread_id,
                    "internal_date": msg.get("internalDate", ""),
                    "reply_at": headers_map.get("date", ""),
                    "from_email": from_email,
                    "to_email": parseaddr(headers_map.get("to", ""))[1].strip().lower(),
                    "subject": headers_map.get("subject", ""),
                    "in_reply_to": headers_map.get("in-reply-to", ""),
                    "body_text": body_text,
                    "body_text_preview": summarize_text(body_text, limit=280),
                    "body_length": str(len(body_text)),
                    "body_file": str(body_path.relative_to(output_dir)),
                    "body_html_file": body_html_rel,
                    "attachment_count": str(len(attachments)),
                    "attachment_names": "; ".join(attachment_names),
                    "attachment_mime_types": "; ".join(attachment_mimes),
                    "has_pdf": "yes" if has_pdf else "no",
                    "has_image": "yes" if has_image else "no",
                    "has_doc": "yes" if has_doc else "no",
                    "needs_manual_review": "yes" if attachments else "no",
                    "账号ID": "|".join(sorted({r["账号ID"] for r in contact_rows})),
                    "频道/作者名称": "|".join(sorted({r["频道/作者名称"] for r in contact_rows if r["频道/作者名称"]})),
                    "平台": "|".join(sorted({r["平台"] for r in contact_rows if r["平台"]})),
                }
                rows_out.append(row)
                raw_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

                for idx, attachment in enumerate(attachments, start=1):
                    attachments_out.append(
                        {
                            "message_id": msg.get("id", ""),
                            "thread_id": thread_id,
                            "from_email": from_email,
                            "filename": attachment["filename"],
                            "mime_type": attachment["mime_type"],
                            "attachment_id": attachment["attachment_id"],
                            "size": str(attachment["size"]),
                            "part_id": attachment["part_id"],
                            "local_path": str(attachments_dir / f"{msg.get('id','')}_{idx}_{attachment['filename']}") if attachment["filename"] else "",
                        }
                    )

    rows_out.sort(key=lambda x: int(x["internal_date"] or "0"), reverse=True)

    csv_fields = [
        "message_id",
        "thread_id",
        "internal_date",
        "reply_at",
        "from_email",
        "to_email",
        "subject",
        "in_reply_to",
        "body_text",
        "body_text_preview",
        "body_length",
        "body_file",
        "body_html_file",
        "attachment_count",
        "attachment_names",
        "attachment_mime_types",
        "has_pdf",
        "has_image",
        "has_doc",
        "needs_manual_review",
        "账号ID",
        "频道/作者名称",
        "平台",
    ]
    write_csv(output_dir / f"reply_batch_full_first{args.limit}.csv", rows_out, csv_fields)

    attachment_fields = [
        "message_id",
        "thread_id",
        "from_email",
        "filename",
        "mime_type",
        "attachment_id",
        "size",
        "part_id",
        "local_path",
    ]
    write_csv(output_dir / f"reply_batch_attachments_first{args.limit}.csv", attachments_out, attachment_fields)

    summary = {
        "profile_email": profile.get("emailAddress"),
        "threads_requested": len(thread_ids),
        "matched_messages": len(rows_out),
        "matched_unique_threads": len({r["thread_id"] for r in rows_out}),
        "matched_unique_contacts": len({r["from_email"] for r in rows_out}),
        "messages_with_body": sum(1 for r in rows_out if int(r["body_length"]) > 0),
        "attachment_messages": sum(1 for r in rows_out if int(r["attachment_count"]) > 0),
        "pdf_messages": sum(1 for r in rows_out if r["has_pdf"] == "yes"),
        "thread_fetch_errors": len(errors),
        "output_csv": str((output_dir / f"reply_batch_full_first{args.limit}.csv").resolve()),
        "output_jsonl": str(raw_jsonl_path.resolve()),
        "attachments_csv": str((output_dir / f"reply_batch_attachments_first{args.limit}.csv").resolve()),
    }
    (output_dir / f"reply_batch_full_first{args.limit}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if errors:
        (output_dir / f"reply_batch_full_first{args.limit}_errors.json").write_text(
            json.dumps(errors, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
