#!/usr/bin/env python3
"""Merge OCR attachment decisions into a shadow S3 master."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def match_decision(row: dict[str, str], decisions: list[dict[str, str]]) -> dict[str, str] | None:
    row_email = row.get("Reply_Contact_Email", "").strip().lower()
    row_name = row.get("频道/作者名称", "").strip().lower()
    for decision in decisions:
        email = decision.get("reply_contact_email", "").strip().lower()
        name = decision.get("creator_name", "").strip().lower()
        if email and row_email and email == row_email:
            return decision
        if name and row_name and name == row_name:
            return decision
    return None


def append_basis(existing: str, extra: str) -> str:
    existing = (existing or "").strip()
    extra = (extra or "").strip()
    if not extra:
        return existing
    if not existing:
        return extra
    if extra in existing:
        return existing
    return f"{existing} + {extra}"


def merge_row(row: dict[str, str], decision: dict[str, str]) -> None:
    status = decision.get("attachment_ocr_status", "").strip()
    if status:
      row["Attachment_OCR_Status"] = status

    basis_append = decision.get("latest_price_basis_append", "").strip()
    if basis_append:
        row["latest_price_basis"] = append_basis(row.get("latest_price_basis", ""), basis_append)

    next_action = decision.get("next_reply_action", "").strip()
    if next_action:
        row["Next_Reply_Action"] = next_action

    manual_review = decision.get("manual_review_needed", "").strip().lower()
    if manual_review in {"yes", "true", "1"}:
        row["Reply_Needs_Manual_Review"] = "yes"

    manual_reason = decision.get("manual_review_reason", "").strip()
    if manual_reason:
        row["Manual_Review_Reason"] = manual_reason

    analysis = decision.get("reply_analysis_append", "").strip()
    if analysis:
        existing = (row.get("Reply_Analysis", "") or "").strip()
        row["Reply_Analysis"] = f"{existing}\n{analysis}".strip() if existing else analysis

    row["Capture_Run_ID"] = "shadow_ocr_merge_2026-05-08"
    row["Capture_At"] = datetime.now().isoformat(timespec="seconds")


def write_summary(path: Path, merged: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Shadow OCR Merge Summary",
        "",
        f"- merged cases: `{len(merged)}`",
        "",
        "## Cases",
    ]
    for item in merged:
        lines.extend(
            [
                f"- `{item['creator_name']}`",
                f"  - status: `{item['attachment_ocr_status']}`",
                f"  - next action: `{item['next_reply_action']}`",
                f"  - basis append: `{item['latest_price_basis_append']}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow-csv", required=True)
    parser.add_argument("--decisions-csv", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    fieldnames, rows = read_csv(Path(args.shadow_csv))
    _, decisions = read_csv(Path(args.decisions_csv))

    merged: list[dict[str, str]] = []
    for row in rows:
        decision = match_decision(row, decisions)
        if decision is None:
            continue
        merge_row(row, decision)
        merged.append(decision)

    write_csv(Path(args.out_csv), fieldnames, rows)
    write_summary(Path(args.summary_md), merged)


if __name__ == "__main__":
    main()
