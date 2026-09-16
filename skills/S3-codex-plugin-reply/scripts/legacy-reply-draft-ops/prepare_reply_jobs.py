#!/usr/bin/env python3
import argparse
from pathlib import Path

from common import STATUS_PENDING, build_job_id, now_iso, read_csv_rows, save_manifest


def split_template(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    if "|" not in text:
        return text, ""
    left, right = text.split("|", 1)
    return left.strip(), right.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reply draft manifest from replied master.")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--wave", choices=["mail2", "mail3", "all"], default="all")
    args = parser.parse_args()

    _, rows = read_csv_rows(Path(args.source_csv))
    manifest_rows = []
    for idx, row in enumerate(rows, start=2):
        candidates = []
        if args.wave in {"mail2", "all"}:
            candidates.append(("mail2", "Mail2_Reply_Template", "Mail2_Body_Final", "Mail2_Draft_ID", "Mail2_Status"))
        if args.wave in {"mail3", "all"}:
            candidates.append(("mail3", "Mail3_Reply_Template", "Mail3_Body_Final", "Mail3_Draft_ID", "Mail3_Status"))

        for wave, template_field, body_field, draft_field, status_field in candidates:
            template_value = (row.get(template_field) or "").strip()
            body = (row.get(body_field) or "").strip()
            if not template_value or not body:
                continue
            if template_value.startswith("RX1") or template_value.startswith("RX2"):
                continue
            if not (row.get("Reply_Thread_ID") or "").strip():
                continue
            if not (row.get("Reply_Last_Message_ID") or "").strip():
                continue
            code, name = split_template(template_value)
            manifest_rows.append(
                {
                    "job_id": build_job_id(str(idx), row.get("Reply_Thread_ID", ""), code),
                    "row_id": str(idx),
                    "account_id": row.get("账号ID", ""),
                    "reply_wave": wave,
                    "template_code": code,
                    "template_name": name,
                    "to": row.get("Reply_Contact_Email", ""),
                    "subject": row.get("Reply_Last_Subject", ""),
                    "body": body,
                    "thread_id": row.get("Reply_Thread_ID", ""),
                    "latest_message_id": row.get("Reply_Last_Message_ID", ""),
                    "status": STATUS_PENDING,
                    "draft_id": row.get(draft_field, ""),
                    "attempt_count": "0",
                    "error": "",
                    "created_at": now_iso(),
                    "updated_at": "",
                }
            )

    save_manifest(Path(args.output_manifest), manifest_rows)
    print(Path(args.output_manifest).resolve())
    print(f"jobs={len(manifest_rows)}")


if __name__ == "__main__":
    main()
