#!/usr/bin/env python3
"""Build daily incremental execution queues from the shadow S3 master."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path


DRAFTABLE_ACTIONS = {
    "request_rate",
    "send_details",
    "push_agency_rate",
    "hold_warm",
    "draft_from_body_quote",
}

OWNERSHIP_EXCLUDED = {
    "steve_handle",
    "ignore",
    "workstream",
    "execution_only",
}

OWNERSHIP_MANUAL_REVIEW = {
    "manual_review",
    "unknown",
}

NO_REPLY_STATES = {
    "no_reply_needed",
    "no_reply_needed_latest_outbound_ours",
    "closed_no_reply_needed",
}

MISSED_REPLY_ACTIONS = {
    "stale_thread_refresh_required",
    "rebuild_from_latest_inbound",
}

BLOCKED_OCR_STATUSES = {
    "attachment_detected",
    "ocr_pending",
    "ocr_review_required",
}


@dataclass
class QueueRow:
    creator_name: str
    reply_contact_email: str
    reply_last_at: str
    pricing_round: str
    current_reply_scenario: str
    next_reply_action: str
    attachment_ocr_status: str
    reply_needs_manual_review: str
    draft_workflow_status: str
    current_price_summary: str
    latest_price_basis: str
    reply_thread_id: str
    pipeline_stage: str
    reply_ownership: str
    need_reply_state: str
    latest_thread_speaker: str
    queue_name: str
    queue_reason: str
    recommended_draft_status: str


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, rows: list[QueueRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(QueueRow.__annotations__.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def parse_dt(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.min
    for parser in (
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None),
        lambda v: parsedate_to_datetime(v).replace(tzinfo=None),
    ):
        try:
            return parser(value)
        except Exception:
            continue
    return datetime.min


def normalize_bool(value: str) -> str:
    value = (value or "").strip().lower()
    return "yes" if value in {"yes", "true", "1"} else "no"


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def classify_queue(row: dict[str, str]) -> tuple[str, str, str]:
    action = normalize_text(row.get("Next_Reply_Action", ""))
    manual = normalize_bool(row.get("Reply_Needs_Manual_Review", ""))
    attachment = normalize_text(row.get("Attachment_OCR_Status", "") or "none")
    stream = normalize_text(row.get("Reply_Stream", ""))
    ownership = normalize_text(row.get("Reply_Ownership", "") or "auto_reply")
    need_reply = normalize_text(row.get("Need_Reply_State", ""))
    latest_speaker = normalize_text(row.get("Latest_Thread_Speaker", ""))

    if stream != "outreach":
        return "excluded", "not_outreach_stream", "not_applicable"
    if ownership in OWNERSHIP_EXCLUDED:
        return "excluded", f"ownership_{ownership}", "not_applicable"
    if ownership in OWNERSHIP_MANUAL_REVIEW:
        return "manual_review", f"ownership_{ownership}", "blocked_manual_review"
    if need_reply in NO_REPLY_STATES:
        return "excluded", need_reply, "not_applicable"
    if need_reply == "contact_update_only" or action == "update_contact_only":
        return "contact_update_queue", "update_contact_only", "contact_update_only"
    if action in MISSED_REPLY_ACTIONS:
        return "missed_reply_queue", action, "needs_thread_refresh"
    if manual == "yes":
        return "manual_review", "reply_needs_manual_review", "blocked_manual_review"
    if action == "ocr_first" or attachment in BLOCKED_OCR_STATUSES:
        return "ocr_queue", "attachment_requires_ocr_before_draft", "blocked_ocr_first"
    if action in {"manual_review", "no_reply"}:
        status = {
            "manual_review": "blocked_manual_review",
            "no_reply": "not_applicable",
        }[action]
        return "manual_review" if action == "manual_review" else "excluded", action, status
    if latest_speaker == "us" and not need_reply:
        return "excluded", "latest_outbound_ours_default", "not_applicable"
    if action in DRAFTABLE_ACTIONS:
        return "draft_queue", "action_is_draftable", "draft_ready"
    return "manual_review", "unknown_action_fallback", "blocked_manual_review"


def build_row(row: dict[str, str], queue_name: str, queue_reason: str, recommended_status: str) -> QueueRow:
    return QueueRow(
        creator_name=row.get("频道/作者名称", ""),
        reply_contact_email=row.get("Reply_Contact_Email", ""),
        reply_last_at=row.get("Reply_Last_At", ""),
        pricing_round=row.get("Pricing_Round", ""),
        current_reply_scenario=row.get("Current_Reply_Scenario", ""),
        next_reply_action=row.get("Next_Reply_Action", ""),
        attachment_ocr_status=row.get("Attachment_OCR_Status", ""),
        reply_needs_manual_review=normalize_bool(row.get("Reply_Needs_Manual_Review", "")),
        draft_workflow_status=row.get("Draft_Workflow_Status", ""),
        current_price_summary=row.get("current_price_summary", ""),
        latest_price_basis=row.get("latest_price_basis", ""),
        reply_thread_id=row.get("Reply_Thread_ID", ""),
        pipeline_stage=row.get("Pipeline_Stage", ""),
        reply_ownership=row.get("Reply_Ownership", ""),
        need_reply_state=row.get("Need_Reply_State", ""),
        latest_thread_speaker=row.get("Latest_Thread_Speaker", ""),
        queue_name=queue_name,
        queue_reason=queue_reason,
        recommended_draft_status=recommended_status,
    )


def write_summary(
    path: Path,
    review_rows: list[QueueRow],
    draft_rows: list[QueueRow],
    ocr_rows: list[QueueRow],
    manual_rows: list[QueueRow],
    missed_rows: list[QueueRow],
    contact_rows: list[QueueRow],
    excluded_count: int,
    from_dt: datetime,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Daily Incremental Queue Summary",
        "",
        f"- scan window start: `{from_dt.isoformat(sep=' ', timespec='seconds')}`",
        f"- review candidates: `{len(review_rows)}`",
        f"- draft queue: `{len(draft_rows)}`",
        f"- OCR queue: `{len(ocr_rows)}`",
        f"- manual review queue: `{len(manual_rows)}`",
        f"- missed reply queue: `{len(missed_rows)}`",
        f"- contact update queue: `{len(contact_rows)}`",
        f"- excluded: `{excluded_count}`",
        "",
        "## Highlights",
    ]

    for label, rows in (
        ("Draft Queue", draft_rows[:5]),
        ("Missed Reply Queue", missed_rows[:5]),
        ("OCR Queue", ocr_rows[:5]),
        ("Manual Review Queue", manual_rows[:5]),
        ("Contact Update Queue", contact_rows[:5]),
    ):
        lines.append(f"### {label}")
        if not rows:
            lines.append("- none")
            continue
        for row in rows:
            lines.append(
                f"- `{row.creator_name}` | `{row.next_reply_action}` | `{row.pricing_round}` | `{row.attachment_ocr_status or 'none'}`"
            )
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--lookback-days", type=int, default=7)
    args = parser.parse_args()

    _, rows = read_csv(Path(args.shadow_csv))
    out_dir = Path(args.out_dir)
    from_dt = datetime.now() - timedelta(days=args.lookback_days)

    review_rows: list[QueueRow] = []
    draft_rows: list[QueueRow] = []
    ocr_rows: list[QueueRow] = []
    manual_rows: list[QueueRow] = []
    missed_rows: list[QueueRow] = []
    contact_rows: list[QueueRow] = []
    excluded_count = 0

    for row in rows:
        reply_dt = parse_dt(row.get("Reply_Last_At", ""))
        if reply_dt == datetime.min or reply_dt < from_dt:
            continue

        queue_name, queue_reason, recommended_status = classify_queue(row)
        if queue_name == "excluded":
            excluded_count += 1
            continue

        queue_row = build_row(row, queue_name, queue_reason, recommended_status)
        review_rows.append(queue_row)
        if queue_name == "draft_queue":
            draft_rows.append(queue_row)
        elif queue_name == "ocr_queue":
            ocr_rows.append(queue_row)
        elif queue_name == "manual_review":
            manual_rows.append(queue_row)
        elif queue_name == "missed_reply_queue":
            missed_rows.append(queue_row)
        elif queue_name == "contact_update_queue":
            contact_rows.append(queue_row)

    review_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)
    draft_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)
    ocr_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)
    manual_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)
    missed_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)
    contact_rows.sort(key=lambda r: parse_dt(r.reply_last_at), reverse=True)

    write_csv(out_dir / "review_table_daily_incremental_candidates.csv", review_rows)
    write_csv(out_dir / "queue_draft_ready.csv", draft_rows)
    write_csv(out_dir / "queue_ocr_first.csv", ocr_rows)
    write_csv(out_dir / "queue_manual_review.csv", manual_rows)
    write_csv(out_dir / "queue_missed_reply.csv", missed_rows)
    write_csv(out_dir / "queue_contact_update.csv", contact_rows)
    write_summary(
        out_dir / "summary_daily_incremental_queues.md",
        review_rows,
        draft_rows,
        ocr_rows,
        manual_rows,
        missed_rows,
        contact_rows,
        excluded_count,
        from_dt,
    )


if __name__ == "__main__":
    main()
