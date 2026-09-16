#!/usr/bin/env python3
"""Build a preview-only S3 master backfill table from curated thread analyses.

This script does not mutate the live master CSV. It only:
1. loads a curated JSON file describing candidate Gmail threads
2. tries to match each case against the current V3 master
3. emits a preview CSV and a short Markdown summary
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of case objects.")
    return data


def normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def match_master_row(case: dict, master_rows: list[dict[str, str]]) -> dict[str, str]:
    email = normalize(case.get("reply_contact_email", ""))
    creator = normalize(case.get("creator_name", ""))
    platform = normalize(case.get("platform", ""))

    candidates: list[tuple[int, dict[str, str], str]] = []

    for line_no, row in enumerate(master_rows, start=2):
        row_email = normalize(row.get("Reply_Contact_Email", ""))
        row_contact = normalize(row.get("联系方式", ""))
        row_name = normalize(row.get("频道/作者名称", ""))
        row_platform = normalize(row.get("平台", ""))

        if email and (email == row_email or email == row_contact):
            return {
                "match_status": "matched_by_email",
                "matched_line": str(line_no),
                "matched_creator_name": row.get("频道/作者名称", ""),
                "matched_reply_contact_email": row.get("Reply_Contact_Email", ""),
                "matched_platform": row.get("平台", ""),
            }

        if creator and creator == row_name:
            candidates.append((line_no, row, "matched_by_name"))
        elif creator and creator in row_name and row_name:
            candidates.append((line_no, row, "fuzzy_name_match"))

        if platform and row_platform and platform != row_platform:
            continue

    if candidates:
        line_no, row, status = candidates[0]
        return {
            "match_status": status,
            "matched_line": str(line_no),
            "matched_creator_name": row.get("频道/作者名称", ""),
            "matched_reply_contact_email": row.get("Reply_Contact_Email", ""),
            "matched_platform": row.get("平台", ""),
        }

    return {
        "match_status": "append_new",
        "matched_line": "",
        "matched_creator_name": "",
        "matched_reply_contact_email": "",
        "matched_platform": "",
    }


def build_preview_rows(cases: list[dict], master_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    preview_rows: list[dict[str, str]] = []
    for case in cases:
        match_info = match_master_row(case, master_rows)
        outbound_ids = case.get("outbound_message_ids", [])
        if isinstance(outbound_ids, list):
            outbound_ids_str = " | ".join(outbound_ids)
        else:
            outbound_ids_str = str(outbound_ids or "")

        preview_rows.append(
            {
                "case_id": case.get("case_id", ""),
                "creator_name": case.get("creator_name", ""),
                "platform": case.get("platform", ""),
                "reply_contact_email": case.get("reply_contact_email", ""),
                "current_price_summary": case.get("current_price_summary", ""),
                "latest_price_normalized": case.get("latest_price_normalized", ""),
                "latest_price_raw": case.get("latest_price_raw", ""),
                "latest_price_basis": case.get("latest_price_basis", ""),
                "thread_id": case.get("thread_id", ""),
                "latest_inbound_message_id": case.get("latest_inbound_message_id", ""),
                "latest_inbound_at": case.get("latest_inbound_at", ""),
                "source_subject": case.get("source_subject", ""),
                "reply_stream": case.get("reply_stream", ""),
                "pricing_effective_wave": case.get("pricing_effective_wave", ""),
                "pricing_round": case.get("pricing_round", ""),
                "pricing_change_type": case.get("pricing_change_type", ""),
                "mail1_reply_block": case.get("mail1_reply_block", ""),
                "mail2_reply_block": case.get("mail2_reply_block", ""),
                "current_reply_scenario": case.get("current_reply_scenario", ""),
                "next_reply_action": case.get("next_reply_action", ""),
                "attachment_ocr_status": case.get("attachment_ocr_status", ""),
                "pipeline_stage": case.get("pipeline_stage", ""),
                "sort_bucket": case.get("sort_bucket", ""),
                "reply_needs_manual_review": "yes" if case.get("reply_needs_manual_review") else "no",
                "manual_review_reason": case.get("manual_review_reason", ""),
                "outbound_message_ids": outbound_ids_str,
                "match_status": match_info["match_status"],
                "matched_line": match_info["matched_line"],
                "matched_creator_name": match_info["matched_creator_name"],
                "matched_reply_contact_email": match_info["matched_reply_contact_email"],
                "matched_platform": match_info["matched_platform"],
                "writeback_mode": "preview_only",
            }
        )
    return preview_rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict[str, str]], input_path: Path, master_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(row["match_status"] for row in rows)
    stages = Counter(row["pipeline_stage"] for row in rows)
    ocr = Counter(row["attachment_ocr_status"] for row in rows)
    pricing = Counter(row["pricing_round"] for row in rows)
    actions = Counter(row["next_reply_action"] for row in rows)

    def bullet_counter(counter: Counter) -> str:
        return "\n".join(f"- `{k}`: `{v}`" for k, v in counter.items() if k)

    lines = [
        "# Master Backfill Preview",
        "",
        f"- Input JSON: `{input_path}`",
        f"- Master CSV: `{master_path}`",
        f"- Cases: `{len(rows)}`",
        "",
        "## Match Status",
        bullet_counter(counts) or "- none",
        "",
        "## Pipeline Stage",
        bullet_counter(stages) or "- none",
        "",
        "## Pricing Round",
        bullet_counter(pricing) or "- none",
        "",
        "## Next Reply Action",
        bullet_counter(actions) or "- none",
        "",
        "## Attachment OCR Status",
        bullet_counter(ocr) or "- none",
        "",
        "## Cases",
    ]

    for row in rows:
        lines.extend(
            [
                "",
                f"### {row['creator_name']}",
                f"- `reply_contact_email`: `{row['reply_contact_email']}`",
                f"- `current_price_summary`: `{row['current_price_summary']}`",
                f"- `pricing_round`: `{row['pricing_round']}`",
                f"- `latest_price_normalized`: `{row['latest_price_normalized']}`",
                f"- `current_reply_scenario`: `{row['current_reply_scenario']}`",
                f"- `next_reply_action`: `{row['next_reply_action']}`",
                f"- `attachment_ocr_status`: `{row['attachment_ocr_status']}`",
                f"- `match_status`: `{row['match_status']}`",
                f"- `matched_line`: `{row['matched_line']}`",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    input_path = Path(args.input_json)
    master_path = Path(args.master_csv)
    output_csv = Path(args.output_csv)
    summary_md = Path(args.summary_md)

    cases = load_cases(input_path)
    master_rows = load_csv_rows(master_path)
    preview_rows = build_preview_rows(cases, master_rows)
    write_csv(output_csv, preview_rows)
    write_summary(summary_md, preview_rows, input_path, master_path)


if __name__ == "__main__":
    main()
