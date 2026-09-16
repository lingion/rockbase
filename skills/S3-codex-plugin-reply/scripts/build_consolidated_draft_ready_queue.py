#!/usr/bin/env python3
"""Build a consolidated draft-ready queue from the live S3 ReplyOps master.

This script is intentionally conservative: the master may contain historical
rows from several workflows, so `Draft_Workflow_Status=draft_ready` is only the
first gate. The script rechecks manual-review, OCR, execution/no-draft, and
thread identity signals before allowing a row into the actionable draft queue.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path


BLOCKING_DRAFT_STATUSES = {
    "manual_review",
    "ocr_first",
    "no_draft",
    "no_draft_closed",
    "no_draft_execution",
    "no_draft_price_floor_too_high",
    "drafted",
    "sent",
}

BLOCKING_OCR_PREFIXES = (
    "needs_ocr",
    "ocr_pending",
    "ocr_review",
    "attachment_detected",
    "prior_pdf_rate_card_needs",
    "pdf_media_kit_attached_needs",
)

ALLOWED_DRAFT_STREAMS = {
    "",
    "outreach",
    "kol_outreach_reply",
    "outreach_pricing",
    "outreach_follow_up",
    "outreach_negotiation",
    "gmail_backfill",
    "creator_intro",
    "price_recovery_default",
    "wf1",
}

BLOCKING_ACTION_PREFIXES = (
    "manual_review",
    "ocr_first",
    "no_auto_reply",
    "no_reply",
)

PRIORITY_CAPTURE_RUNS = {
    "ocr_merge_batch_001": 0,
    "s3_codex_backfill_batch_018": 1,
    "s3_codex_backfill_batch_017": 2,
    "s3_codex_backfill_batch_016": 3,
    "s3_codex_backfill_batch_015": 4,
    "s3_codex_backfill_batch_014": 5,
    "s3_codex_backfill_batch_013": 6,
}

BUCKET_PRIORITY = {
    "0_quoted_mail2_plus": 0,
    "1_replied_clear_price": 1,
    "1_quoted_mail1": 2,
    "2_replied_no_quote": 3,
    "2_replied_need_review": 7,
    "3_contact_update": 8,
    "3_waiting": 8,
    "4_closed": 9,
}

OUTPUT_FIELDS = [
    "queue_rank",
    "queue_priority",
    "queue_reason",
    "频道/作者名称",
    "Reply_Contact_Email",
    "Reply_Thread_ID",
    "Reply_Last_Message_ID",
    "Reply_Last_At",
    "Reply_Last_Subject",
    "平台",
    "Sort_Bucket",
    "Pricing_Round",
    "latest_price_normalized",
    "current_price_summary",
    "latest_price_basis",
    "Current_Reply_Scenario",
    "Next_Reply_Action",
    "Attachment_OCR_Status",
    "Draft_Workflow_Status",
    "Reply_Needs_Manual_Review",
    "Manual_Review_Reason",
    "Manual_Review_Focus",
    "Capture_Run_ID",
    "Capture_At",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return (value or "").strip().lower()


def parse_dt(value: str | None) -> datetime:
    text = (value or "").strip()
    if not text:
        return datetime.min
    for parser in (
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None),
        lambda v: parsedate_to_datetime(v).replace(tzinfo=None),
    ):
        try:
            return parser(text)
        except Exception:
            continue
    return datetime.min


def is_yes(value: str | None) -> bool:
    return norm(value) in {"yes", "true", "1", "y"}


def has_blocking_ocr(value: str | None) -> bool:
    status = norm(value)
    return any(status.startswith(prefix) for prefix in BLOCKING_OCR_PREFIXES)


def has_blocking_action(value: str | None) -> bool:
    action = norm(value)
    return any(action.startswith(prefix) for prefix in BLOCKING_ACTION_PREFIXES)


def classify(row: dict[str, str]) -> tuple[str, str]:
    draft_status = norm(row.get("Draft_Workflow_Status"))
    if draft_status in BLOCKING_DRAFT_STATUSES:
        return "blocked", f"blocked_draft_status:{draft_status}"
    if draft_status != "draft_ready":
        return "excluded", "not_marked_draft_ready"
    if is_yes(row.get("Reply_Needs_Manual_Review")):
        return "blocked", "reply_needs_manual_review"
    if has_blocking_ocr(row.get("Attachment_OCR_Status")):
        return "blocked", f"attachment_not_ready:{row.get('Attachment_OCR_Status', '')}"
    if has_blocking_action(row.get("Next_Reply_Action")):
        return "blocked", f"blocking_next_action:{row.get('Next_Reply_Action', '')}"
    if norm(row.get("Reply_Stream")) not in ALLOWED_DRAFT_STREAMS:
        return "blocked", f"non_outreach_stream:{row.get('Reply_Stream', '')}"
    if norm(row.get("Sort_Bucket")) == "4_closed":
        return "blocked", "closed_bucket"
    if not (row.get("Reply_Contact_Email") or "").strip():
        return "blocked", "missing_reply_contact_email"
    if not (row.get("Reply_Thread_ID") or "").strip() and not (row.get("Reply_Last_Message_ID") or "").strip():
        return "blocked", "missing_thread_and_message_id"
    return "draft_ready", "passes_conservative_gate"


def priority(row: dict[str, str]) -> tuple[int, int, int, datetime, str]:
    capture = row.get("Capture_Run_ID", "")
    capture_score = PRIORITY_CAPTURE_RUNS.get(capture, 20)
    bucket_score = BUCKET_PRIORITY.get(row.get("Sort_Bucket", ""), 6)
    no_price_penalty = 1 if "no_price" in norm(row.get("latest_price_normalized")) else 0
    return (
        capture_score,
        bucket_score,
        no_price_penalty,
        parse_dt(row.get("Reply_Last_At")),
        row.get("频道/作者名称", ""),
    )


def build_output_row(row: dict[str, str], rank: int, reason: str) -> dict[str, str]:
    out = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    out["queue_rank"] = str(rank)
    out["queue_priority"] = f"{priority(row)[0]}:{priority(row)[1]}:{priority(row)[2]}"
    out["queue_reason"] = reason
    return out


def write_summary(
    path: Path,
    master: Path,
    draft_rows: list[dict[str, str]],
    blocked_rows: list[dict[str, str]],
    excluded_count: int,
    source_counts: Counter[str],
) -> None:
    lines = [
        "# Consolidated Draft Ready Queue Summary",
        "",
        f"- Built at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Live master: `{master}`",
        f"- Draft-ready rows: `{len(draft_rows)}`",
        f"- Blocked rows: `{len(blocked_rows)}`",
        f"- Excluded rows: `{excluded_count}`",
        "",
        "## Priority Sources",
    ]
    for source, count in source_counts.most_common(12):
        lines.append(f"- `{source or '(blank)'}`: {count}")

    lines.extend(["", "## First 10 Draft Candidates"])
    if not draft_rows:
        lines.append("- none")
    for row in draft_rows[:10]:
        lines.append(
            "- "
            f"`{row.get('queue_rank')}` "
            f"{row.get('频道/作者名称', '')} | "
            f"{row.get('Reply_Contact_Email', '')} | "
            f"{row.get('Sort_Bucket', '')} | "
            f"{row.get('Next_Reply_Action', '')}"
        )

    lines.extend(["", "## Blocked Reasons"])
    reason_counts = Counter(row.get("queue_reason", "") for row in blocked_rows)
    for reason, count in reason_counts.most_common(12):
        lines.append(f"- `{reason}`: {count}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=0, help="Optional max draft rows to write; 0 means all.")
    args = parser.parse_args()

    master = Path(args.master)
    out_dir = Path(args.out_dir)
    _, rows = read_csv(master)

    draft_candidates: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    excluded_count = 0

    for row in rows:
        status, reason = classify(row)
        if status == "draft_ready":
            draft_candidates.append((row, reason))  # type: ignore[arg-type]
        elif status == "blocked":
            blocked.append(build_output_row(row, 0, reason))
        else:
            excluded_count += 1

    draft_candidates.sort(key=lambda item: priority(item[0]), reverse=False)
    draft_rows = [
        build_output_row(row, rank, reason)
        for rank, (row, reason) in enumerate(draft_candidates, start=1)
    ]
    if args.limit > 0:
        draft_rows = draft_rows[: args.limit]

    source_counts = Counter(row.get("Capture_Run_ID", "") for row in draft_rows)

    write_csv(out_dir / "queue_draft_ready_consolidated.csv", OUTPUT_FIELDS, draft_rows)
    write_csv(out_dir / "queue_draft_blocked_consolidated.csv", OUTPUT_FIELDS, blocked)
    write_summary(
        out_dir / "summary_consolidated_draft_ready.md",
        master,
        draft_rows,
        blocked,
        excluded_count,
        source_counts,
    )

    print(f"draft_ready={len(draft_rows)} blocked={len(blocked)} excluded={excluded_count}")
    print(out_dir / "queue_draft_ready_consolidated.csv")


if __name__ == "__main__":
    main()
