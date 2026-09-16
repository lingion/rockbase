#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import (
    STATUS_PENDING,
    build_job_id,
    clean_recipient_value,
    normalize_row_id,
    normalize_recipients,
    now_iso,
    print_json,
    read_csv_rows,
    save_manifest,
    sha256_text,
)


def normalize_body_text(text: str) -> str:
    return " ".join((text or "").replace("\r", "\n").split())


def is_mail1_coherent(row: dict) -> tuple[bool, str]:
    greeting = row.get("Mail1_Greeting_Name", "").strip()
    hook = row.get("Mail1_Hook", "").strip()
    body = row.get("Mail1_Content V1", "")
    subject = row.get("Mail1_Subject", "").strip()
    if not greeting or not hook or not body or not subject:
        return False, "missing_mail1_fields"
    first_line = body.replace("\r", "\n").split("\n", 1)[0].strip()
    expected_greeting_line = f"Hi {greeting},"
    if first_line != expected_greeting_line:
        return False, f"greeting_mismatch:first_line={first_line}"
    normalized_body = normalize_body_text(body)
    normalized_hook = normalize_body_text(hook)
    if normalized_hook not in normalized_body:
        return False, "hook_not_found_in_body"
    return True, ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a normalized draft job manifest from a CSV source.")
    parser.add_argument("--input", required=True, help="Source CSV path.")
    parser.add_argument("--output", required=True, help="Manifest CSV path.")
    parser.add_argument("--to-field", required=True, help="Recipient field name in source CSV.")
    parser.add_argument("--subject-field", required=True, help="Subject field name in source CSV.")
    parser.add_argument("--body-field", required=True, help="Body field name in source CSV.")
    parser.add_argument("--row-id-field", default="", help="Optional source row id field.")
    parser.add_argument(
        "--recipient-mode",
        choices=["strict", "split"],
        default="strict",
        help="Use strict mode for one row -> one draft, split mode to split multiple emails into multiple jobs.",
    )
    parser.add_argument(
        "--status",
        default=STATUS_PENDING,
        help="Initial job status, default pending.",
    )
    parser.add_argument(
        "--skip-mail1-coherence-check",
        action="store_true",
        help="Disable Mail1 coherence validation between greeting, hook, subject, and body.",
    )
    parser.add_argument(
        "--fail-on-incoherent",
        action="store_true",
        help="Abort if any rows fail the Mail1 coherence check instead of skipping them.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    _, source_rows = read_csv_rows(input_path)

    manifest_rows = []
    skipped_invalid_recipients = []
    skipped_incoherent_rows = []
    for idx, row in enumerate(source_rows, start=2):
        if row.get("manual_clean_decision", "").strip().lower() == "drop":
            continue
        if row.get("email_qc_flag", "").strip().lower() in {"dirty", "invalid", "suspect"}:
            continue
        row_id = normalize_row_id(idx, row.get(args.row_id_field, "") if args.row_id_field else "")
        raw_to = row.get(args.to_field, "")
        recipients = normalize_recipients(raw_to, args.recipient_mode)
        subject = row.get(args.subject_field, "").strip()
        body = row.get(args.body_field, "")
        if not recipients and clean_recipient_value(raw_to) == [] and raw_to.strip():
            skipped_invalid_recipients.append({"row_id": row_id, "raw_to": raw_to})
        if not recipients or not subject or not body:
            continue
        if not args.skip_mail1_coherence_check:
            coherent, reason = is_mail1_coherent(row)
            if not coherent:
                skipped_incoherent_rows.append(
                    {
                        "row_id": row_id,
                        "display_name": row.get("频道/作者名称", "").strip(),
                        "reason": reason,
                    }
                )
                continue
        for recipient in recipients:
            manifest_rows.append(
                {
                    "job_id": build_job_id(row_id, recipient, subject),
                    "row_id": row_id,
                    "source_ref": str(input_path),
                    "upstream_source_ref": row.get("source_ref", "").strip(),
                    "upstream_row_number": row.get("source_row_number", "").strip(),
                    "to": recipient,
                    "subject": subject,
                    "body": body,
                    "body_hash": sha256_text(body),
                    "status": args.status,
                    "draft_id": "",
                    "attempt_count": "0",
                    "error": "",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "display_name": row.get("频道/作者名称", "").strip(),
                    "mail1_greeting_name": row.get("Mail1_Greeting_Name", "").strip(),
                    "mail1_hook": row.get("Mail1_Hook", "").strip(),
                    "mail1_variant": row.get("Mail1_Variant", "").strip(),
                    "body_preview": body[:240],
                }
            )

    if args.fail_on_incoherent and skipped_incoherent_rows:
        print_json(
            {
                "source": str(input_path),
                "incoherent_rows": skipped_incoherent_rows,
                "incoherent_count": len(skipped_incoherent_rows),
            }
        )
        raise SystemExit("mail1 coherence check failed")

    save_manifest(output_path, manifest_rows)
    print_json(
        {
            "manifest": str(output_path),
            "source": str(input_path),
            "jobs_created": len(manifest_rows),
            "recipient_mode": args.recipient_mode,
            "skipped_invalid_recipients": len(skipped_invalid_recipients),
            "skipped_incoherent_rows": len(skipped_incoherent_rows),
            "incoherent_details": skipped_incoherent_rows[:20],
        }
    )


if __name__ == "__main__":
    main()
