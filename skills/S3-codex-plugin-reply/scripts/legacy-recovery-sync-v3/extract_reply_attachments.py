#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from gmail_requests_transport import build_gmail_service
from ocr_dual_engine import merge_candidate_texts, run_dual_image_ocr, run_pdf_dual_ocr, score_extracted_text

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional local dependency
    pdfplumber = None


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>")
PRICE_HINT_RE = re.compile(
    r"(?i)(?:"
    r"(US?\$|USD|EUR|€|£|GBP|\$)\s*(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)"
    r"|"
    r"(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)\s*(US?\$|USD|EUR|€|£|GBP|\$|dollars?|euros?|pounds?)"
    r")"
)
CHANNEL_HINT_RE = re.compile(
    r"(?i)\b("
    r"youtube|yt|tiktok|instagram|insta|ig|twitter|x\.com|shorts?|reels?|story|post|video|integration|dedicated|bundle|package|cross[\s-]?post"
    r")\b"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Gmail attachments listed in a CSV and extract text where possible.")
    parser.add_argument("--attachments-csv", required=True, help="Attachment inventory CSV from fetch_reply_batch_full.py.")
    parser.add_argument("--output-dir", required=True, help="Base output directory for downloaded files and extracted text.")
    parser.add_argument("--sleep-seconds", type=float, default=0.35, help="Delay between Gmail API requests.")
    parser.add_argument("--token", default=str(TOKEN_PATH), help="Path to the Gmail OAuth token JSON.")
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


def safe_filename(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "attachment.bin"
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    return name[:180]


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
    return build_gmail_service(creds)


def api_get_attachment(service, message_id: str, attachment_id: str, sleep_seconds: float, retries: int = 6) -> dict:
    last_exc = None
    for attempt in range(retries):
        try:
            payload = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
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


def decode_attachment_data(data: str) -> bytes:
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def run_pdftotext(pdf_path: Path, txt_path: Path) -> str:
    subprocess.run(
        ["pdftotext", str(pdf_path), str(txt_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return txt_path.read_text(encoding="utf-8", errors="replace")


def run_pdfplumber(pdf_path: Path, txt_path: Path) -> str:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber not installed")
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text = "\n\n".join(page for page in pages if page.strip())
    txt_path.write_text(text, encoding="utf-8")
    return text


def run_tesseract(image_path: Path, txt_base_path: Path, lang: str = "eng+chi_sim", psm: int = 6) -> str:
    subprocess.run(
        ["tesseract", str(image_path), str(txt_base_path), "-l", lang, "--psm", str(psm)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Tesseract appends ".txt" to the provided output base path verbatim.
    txt_path = Path(f"{txt_base_path}.txt")
    return txt_path.read_text(encoding="utf-8", errors="replace")


def run_textutil(doc_path: Path, txt_path: Path) -> str:
    subprocess.run(
        ["textutil", "-convert", "txt", "-output", str(txt_path), str(doc_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return txt_path.read_text(encoding="utf-8", errors="replace")


def summarize_text(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[: limit - 3] + "..." if len(text) > limit else text


def normalized_text_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def run_strings(file_path: Path, txt_path: Path) -> str:
    result = subprocess.run(
        ["strings", "-n", "6", str(file_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    txt_path.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def write_placeholder_text(txt_path: Path, row: Dict[str, str], note: str) -> str:
    placeholder = (
        f"[Attachment extracted without readable pricing text]\n"
        f"filename: {row.get('filename', '')}\n"
        f"mime_type: {row.get('mime_type', '')}\n"
        f"note: {note}\n"
    )
    txt_path.write_text(placeholder, encoding="utf-8")
    return placeholder


def main() -> None:
    args = parse_args()
    attachments_csv = Path(args.attachments_csv)
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "attachments" / "raw"
    text_dir = output_dir / "attachments" / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(attachments_csv)
    service = build_service(Path(args.token))

    extracted_rows: List[Dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        message_id = row.get("message_id", "")
        attachment_id = row.get("attachment_id", "")
        filename = safe_filename(row.get("filename", ""))
        mime_type = row.get("mime_type", "")
        prefix = f"{message_id}_{idx}"
        raw_path = raw_dir / f"{prefix}_{filename}"
        text_path = text_dir / f"{prefix}_{Path(filename).stem}.txt"

        status = "downloaded"
        extract_method = ""
        extracted_text = ""
        ocr_strategy = ""
        ocr_score = "0"
        ocr_candidates = ""
        error = ""
        try:
            payload = api_get_attachment(service, message_id, attachment_id, args.sleep_seconds)
            raw_bytes = decode_attachment_data(payload.get("data", ""))
            raw_path.write_bytes(raw_bytes)

            lower_name = filename.lower()
            if lower_name.endswith(".pdf") or mime_type == "application/pdf":
                try:
                    native_candidates = []
                    if shutil.which("pdftotext"):
                        extract_method = "pdftotext"
                        native_text = run_pdftotext(raw_path, text_path)
                    else:
                        extract_method = "pdfplumber"
                        native_text = run_pdfplumber(raw_path, text_path)
                    native_candidates.append((extract_method, native_text, score_extracted_text(native_text)))
                    extracted_text = native_text
                    if shutil.which("pdftoppm") and shutil.which("tesseract"):
                        ocr_text, ocr_meta = run_pdf_dual_ocr(raw_path, text_path)
                        ocr_strategy = ocr_meta.get("ocr_strategy", "")
                        ocr_score = ocr_meta.get("ocr_score", "0")
                        ocr_candidates = ocr_meta.get("ocr_candidates", "")
                        native_candidates.append((ocr_strategy or "pdf_dual_ocr", ocr_text, score_extracted_text(ocr_text)))
                        ranked = sorted(native_candidates, key=lambda item: (item[2], normalized_text_length(item[1])), reverse=True)
                        merged_text, merged_label = merge_candidate_texts([(label, text) for label, text, _ in ranked[:2]])
                        merged_score = score_extracted_text(merged_text)
                        extracted_text = merged_text if merged_score >= ranked[0][2] else ranked[0][1]
                        extract_method = f"{extract_method}+{merged_label}" if merged_score >= ranked[0][2] else ranked[0][0]
                        if merged_score >= ranked[0][2]:
                            ocr_strategy = f"merged:{merged_label}"
                    status = "downloaded_extracted"
                except Exception as exc:
                    status = "downloaded_extract_failed"
                    error = f"pdf extraction failed: {exc}"
            elif mime_type.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif")):
                extract_method = "dual_ocr"
                try:
                    extracted_text, ocr_meta = run_dual_image_ocr(raw_path, text_path)
                    ocr_strategy = ocr_meta.get("ocr_strategy", "")
                    ocr_score = ocr_meta.get("ocr_score", "0")
                    ocr_candidates = ocr_meta.get("ocr_candidates", "")
                    status = "downloaded_extracted"
                except Exception as exc:
                    status = "downloaded_extract_failed"
                    error = f"dual ocr failed: {exc}"
            elif lower_name.endswith((".doc", ".docx")) or "wordprocessingml.document" in mime_type or mime_type == "application/msword":
                extract_method = "textutil"
                try:
                    extracted_text = run_textutil(raw_path, text_path)
                    status = "downloaded_extracted"
                except Exception as exc:
                    status = "downloaded_extract_failed"
                    error = f"textutil failed: {exc}"
            else:
                extract_method = "strings"
                try:
                    extracted_text = run_strings(raw_path, text_path)
                    status = "downloaded_extracted" if normalized_text_length(extracted_text) >= 12 else "downloaded_unparsed"
                except Exception as exc:
                    status = "downloaded_extract_failed"
                    error = f"strings failed: {exc}"
        except Exception as exc:  # pragma: no cover - network-dependent
            status = "download_failed"
            error = str(exc)

        if extracted_text and not text_path.exists():
            text_path.write_text(extracted_text, encoding="utf-8")
        if not text_path.exists():
            extracted_text = write_placeholder_text(text_path, row, error or status)

        extracted_rows.append(
            {
                **row,
                "download_status": status,
                "raw_file": str(raw_path),
                "text_file": str(text_path) if text_path.exists() else "",
                "extract_method": extract_method,
                "text_preview": summarize_text(extracted_text),
                "text_length": str(len(extracted_text)),
                "ocr_strategy": ocr_strategy,
                "ocr_score": ocr_score,
                "ocr_candidates": ocr_candidates,
                "error": error,
            }
        )

    fieldnames = list(extracted_rows[0].keys()) if extracted_rows else []
    write_rows(output_dir / "attachment_extraction_report.csv", extracted_rows, fieldnames)

    summary = {
        "attachments_total": len(extracted_rows),
        "downloaded_count": sum(1 for row in extracted_rows if row["download_status"].startswith("downloaded")),
        "extracted_count": sum(1 for row in extracted_rows if row["download_status"] == "downloaded_extracted"),
        "pdf_count": sum(1 for row in extracted_rows if row.get("mime_type") == "application/pdf" or row.get("filename", "").lower().endswith(".pdf")),
        "image_count": sum(1 for row in extracted_rows if row.get("mime_type", "").startswith("image/")),
        "failed_count": sum(1 for row in extracted_rows if "failed" in row["download_status"]),
        "report_csv": str((output_dir / "attachment_extraction_report.csv").resolve()),
    }
    (output_dir / "attachment_extraction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
