#!/usr/bin/env python3
import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_MASTER = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv"
)
DEFAULT_HUB_V2 = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v2"
)
DEFAULT_HUB_V3 = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3"
)


@dataclass
class ReviewCandidate:
    account_id: str
    reply_at: Optional[datetime]
    subject: str
    body_file: str
    body_text: str
    excerpt: str
    pricing: str
    source_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Part2 reply content into the V3 master.")
    parser.add_argument("--master", default=str(DEFAULT_MASTER), help="Path to the V3 master CSV.")
    parser.add_argument("--hub-v2", default=str(DEFAULT_HUB_V2), help="Path to Hub V2.")
    parser.add_argument("--hub-v3", default=str(DEFAULT_HUB_V3), help="Path to Hub V3.")
    parser.add_argument("--write-master", action="store_true", help="Write the updated master back to disk.")
    parser.add_argument("--audit-dir", default="", help="Optional audit output directory.")
    return parser.parse_args()


def parse_reply_at(value: str) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.replace(" (UTC)", "")
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_body_text(v3_body_dir: Path, body_ref: str) -> str:
    name = Path(body_ref).name
    if not name:
        return ""
    body_path = v3_body_dir / name
    if not body_path.exists():
        return ""
    return body_path.read_text(encoding="utf-8", errors="replace").strip()


def load_v2_candidates(hub_v2: Path, hub_v3: Path) -> Dict[str, List[ReviewCandidate]]:
    index: Dict[str, List[ReviewCandidate]] = {}
    review_dir = hub_v2 / "02-review-ready"
    body_dir = hub_v3 / "bodies"
    for csv_path in sorted(review_dir.glob("*_review_table_v3.csv")):
        for row in read_csv_rows(csv_path):
            account_id = (row.get("账号ID") or "").strip()
            body_ref = (row.get("body_file") or "").strip()
            excerpt = (row.get("价格原文摘录") or "").strip()
            pricing = (row.get("综合报价") or "").strip()
            if not account_id or not (body_ref or excerpt or pricing):
                continue
            candidate = ReviewCandidate(
                account_id=account_id,
                reply_at=parse_reply_at(row.get("reply_at", "")),
                subject=(row.get("subject") or "").strip(),
                body_file=body_ref,
                body_text=load_body_text(body_dir, body_ref),
                excerpt=excerpt,
                pricing=pricing,
                source_file=csv_path.name,
            )
            index.setdefault(account_id, []).append(candidate)
    for values in index.values():
        values.sort(key=lambda item: item.reply_at or datetime.min.replace(tzinfo=timezone.utc))
    return index


def choose_candidate(candidates: List[ReviewCandidate], current_reply_at: Optional[datetime]) -> Optional[ReviewCandidate]:
    if not candidates:
        return None
    if current_reply_at is None:
        return candidates[-1]
    earlier = [item for item in candidates if item.reply_at and item.reply_at < current_reply_at]
    if earlier:
        return earlier[-1]
    return candidates[-1]


def build_mail1_from_current(row: Dict[str, str], hub_v3: Path) -> Optional[Dict[str, str]]:
    reply_file = (row.get("Reply_Body_File") or "").strip()
    if not reply_file:
        return None
    body_text = load_body_text(hub_v3 / "bodies", reply_file)
    if not body_text:
        return None
    return {
        "source": "current_reply_body",
        "mail1_reply": body_text,
        "mail1_reply_at": (row.get("Reply_Last_At") or "").strip(),
        "mail1_subject": (row.get("Reply_Last_Subject") or "").strip(),
        "candidate_body_file": reply_file,
        "candidate_source_file": "",
        "candidate_excerpt": "",
        "candidate_pricing": "",
    }


def build_mail1_from_v2(row: Dict[str, str], candidates: Dict[str, List[ReviewCandidate]]) -> Optional[Dict[str, str]]:
    account_id = (row.get("账号ID") or "").strip()
    current_reply_at = parse_reply_at(row.get("Mail2_Reply_At", "") or row.get("Reply_Last_At", ""))
    candidate = choose_candidate(candidates.get(account_id, []), current_reply_at)
    if candidate is None:
        return None
    mail1_reply = candidate.body_text or candidate.excerpt
    if not mail1_reply:
        return None
    reply_at = ""
    if candidate.reply_at is not None:
        reply_at = candidate.reply_at.strftime("%a, %d %b %Y %H:%M:%S %z")
    return {
        "source": "hub_v2_by_account",
        "mail1_reply": mail1_reply,
        "mail1_reply_at": reply_at,
        "mail1_subject": candidate.subject,
        "candidate_body_file": candidate.body_file,
        "candidate_source_file": candidate.source_file,
        "candidate_excerpt": candidate.excerpt,
        "candidate_pricing": candidate.pricing,
    }


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    hub_v2 = Path(args.hub_v2)
    hub_v3 = Path(args.hub_v3)
    audit_dir = Path(args.audit_dir) if args.audit_dir else hub_v3 / "audit"

    rows = read_csv_rows(master_path)
    fieldnames = list(rows[0].keys()) if rows else []
    v2_candidates = load_v2_candidates(hub_v2, hub_v3)

    audit_rows: List[Dict[str, str]] = []
    summary = {
        "single_reply_backfilled": 0,
        "mail2_chain_backfilled": 0,
        "skipped_no_source": 0,
    }

    for row in rows:
        mail1 = (row.get("Mail1_Reply") or "").strip()
        mail2 = (row.get("Mail2_Reply") or "").strip()

        result = None
        if not mail1 and not mail2:
            result = build_mail1_from_current(row, hub_v3)
            if result:
                summary["single_reply_backfilled"] += 1
        elif not mail1 and mail2:
            result = build_mail1_from_v2(row, v2_candidates)
            if result:
                summary["mail2_chain_backfilled"] += 1

        if result is None:
            if not mail1:
                summary["skipped_no_source"] += 1
            continue

        row["Mail1_Reply"] = result["mail1_reply"]
        if not (row.get("Mail1_Reply_At") or "").strip():
            row["Mail1_Reply_At"] = result["mail1_reply_at"]
        if not (row.get("Mail1_Subject") or "").strip():
            row["Mail1_Subject"] = result["mail1_subject"]

        audit_rows.append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "backfill_source": result["source"],
                "Mail1_Reply_At": row.get("Mail1_Reply_At", ""),
                "Mail2_Reply_At": row.get("Mail2_Reply_At", ""),
                "Reply_Last_At": row.get("Reply_Last_At", ""),
                "candidate_body_file": result["candidate_body_file"],
                "candidate_source_file": result["candidate_source_file"],
                "candidate_excerpt": result["candidate_excerpt"],
                "candidate_pricing": result["candidate_pricing"],
            }
        )

    if args.write_master:
        write_csv(master_path, rows, fieldnames)

    audit_path = audit_dir / "2026-03-26_part2_backfill_audit.csv"
    summary_path = audit_dir / "2026-03-26_part2_backfill_summary.md"
    write_csv(audit_path, audit_rows, list(audit_rows[0].keys()) if audit_rows else ["账号ID"])
    summary_lines = [
        "# Part2 Backfill Write Summary",
        "",
        f"- master rows: {len(rows)}",
        f"- single reply rows backfilled from current Reply_Body_File: {summary['single_reply_backfilled']}",
        f"- mail2 chains backfilled from Hub V2: {summary['mail2_chain_backfilled']}",
        f"- remaining rows without Mail1 source: {summary['skipped_no_source']}",
        "",
        "## Rule",
        "",
        "- If a row had no Mail1 and no Mail2 but had Reply_Body_File, backfill Mail1 from the current reply body.",
        "- If a row had Mail2 but no Mail1, backfill Mail1 from the latest earlier Hub V2 reply candidate for the same 账号ID.",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
