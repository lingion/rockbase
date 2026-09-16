#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


QUOTE_PATTERN = re.compile(
    r"(?i)(?:US?\$|USD\s*|£\s*|\$\s*)(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact review table from recovered reply bodies and attachment text.")
    parser.add_argument("--messages-csv", required=True, help="reply_batch_full_first20.csv path.")
    parser.add_argument("--attachments-report-csv", required=True, help="attachment_extraction_report.csv path.")
    parser.add_argument("--output-csv", required=True, help="Review table CSV output path.")
    parser.add_argument("--output-json", required=True, help="Review table summary JSON output path.")
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


def clean_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def short_text(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", clean_text(text))
    return text[: limit - 3] + "..." if len(text) > limit else text


def extract_quotes(text: str) -> List[Tuple[str, str]]:
    found = []
    for match in QUOTE_PATTERN.finditer(text or ""):
        full = match.group(0)
        amount = match.group(1).replace(",", "")
        currency = "USD"
        if "£" in full:
            currency = "GBP"
        found.append((currency, amount))
    deduped = []
    seen = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def infer_intent(body_text: str, attachment_count: int, quotes: List[Tuple[str, str]]) -> str:
    body = (body_text or "").lower()
    if quotes:
        return "rate_shared"
    if "would love to hear more" in body or "next steps" in body:
        return "interested_need_brief"
    if "interested" in body or "happy to collaborate" in body or "we’d be happy" in body or "we'd be happy" in body:
        return "interested"
    if attachment_count > 0:
        return "attachment_only"
    return "other"


def infer_next_action(intent: str, needs_manual_review: str) -> str:
    if needs_manual_review == "yes":
        return "review_attachment"
    if intent == "rate_shared":
        return "evaluate_rate"
    if intent == "interested_need_brief":
        return "send_brief"
    if intent == "interested":
        return "reply_and_probe_rate"
    if intent == "attachment_only":
        return "inspect_attachment"
    return "manual_triage"


def aggregate_attachments(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("message_id", "")].append(row)
    return grouped


def main() -> None:
    args = parse_args()
    message_rows = read_rows(Path(args.messages_csv))
    attachment_rows = read_rows(Path(args.attachments_report_csv))
    attachments_by_message = aggregate_attachments(attachment_rows)

    review_rows: List[Dict[str, str]] = []
    for row in message_rows:
        message_id = row.get("message_id", "")
        body_text = clean_text(row.get("body_text", ""))
        attachments = attachments_by_message.get(message_id, [])
        body_quotes = extract_quotes(body_text)

        attachment_previews = []
        attachment_quotes: List[Tuple[str, str]] = []
        low_quality_attachment = False
        for attachment in attachments:
            preview = short_text(attachment.get("text_preview", ""), limit=180)
            if preview:
                attachment_previews.append(f"{attachment.get('filename', '')}: {preview}")
            text_length = int(attachment.get("text_length", "0") or "0")
            if attachment.get("mime_type") == "application/pdf" and text_length < 50:
                low_quality_attachment = True
            text_file = attachment.get("text_file", "")
            if text_file and Path(text_file).exists():
                attachment_text = Path(text_file).read_text(encoding="utf-8", errors="replace")
                attachment_quotes.extend(extract_quotes(attachment_text))

        all_quotes = []
        seen_quotes = set()
        for item in body_quotes + attachment_quotes:
            if item not in seen_quotes:
                seen_quotes.add(item)
                all_quotes.append(item)

        quote_summary = "; ".join([f"{currency} {amount}" for currency, amount in all_quotes])
        primary_currency = all_quotes[0][0] if all_quotes else ""
        primary_quote = all_quotes[0][1] if all_quotes else ""

        needs_manual_review = "yes" if attachments or low_quality_attachment else "no"
        intent = infer_intent(body_text, len(attachments), all_quotes)
        next_action = infer_next_action(intent, needs_manual_review)

        review_rows.append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "平台": row.get("平台", ""),
                "from_email": row.get("from_email", ""),
                "subject": row.get("subject", ""),
                "reply_at": row.get("reply_at", ""),
                "thread_id": row.get("thread_id", ""),
                "message_id": message_id,
                "reply_intent": intent,
                "interest_signal": "yes" if intent in {"rate_shared", "interested", "interested_need_brief", "attachment_only"} else "no",
                "quote_primary": primary_quote,
                "quote_currency": primary_currency,
                "quote_all": quote_summary,
                "body_summary": short_text(body_text, limit=320),
                "body_file": row.get("body_file", ""),
                "attachment_count": row.get("attachment_count", "0"),
                "attachment_names": row.get("attachment_names", ""),
                "attachment_summary": " | ".join(attachment_previews),
                "needs_manual_review": needs_manual_review,
                "manual_review_reason": "attachment_present" if attachments else ("low_pdf_text" if low_quality_attachment else ""),
                "next_action": next_action,
                "decision_note": "",
            }
        )

    fieldnames = [
        "账号ID",
        "频道/作者名称",
        "平台",
        "from_email",
        "subject",
        "reply_at",
        "thread_id",
        "message_id",
        "reply_intent",
        "interest_signal",
        "quote_primary",
        "quote_currency",
        "quote_all",
        "body_summary",
        "body_file",
        "attachment_count",
        "attachment_names",
        "attachment_summary",
        "needs_manual_review",
        "manual_review_reason",
        "next_action",
        "decision_note",
    ]
    write_rows(Path(args.output_csv), review_rows, fieldnames)

    summary = {
        "rows": len(review_rows),
        "rate_shared_count": sum(1 for r in review_rows if r["reply_intent"] == "rate_shared"),
        "interested_count": sum(1 for r in review_rows if r["interest_signal"] == "yes"),
        "manual_review_count": sum(1 for r in review_rows if r["needs_manual_review"] == "yes"),
        "rows_with_quote": sum(1 for r in review_rows if r["quote_primary"]),
        "output_csv": str(Path(args.output_csv).resolve()),
    }
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
