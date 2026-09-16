#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List


DEFAULT_MASTER = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv"
)
DEFAULT_OUTPUT = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3/runs/2026-03-26_run-001/part2_reply_blocks_preview.csv"
)
DEFAULT_SUMMARY = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3/runs/2026-03-26_run-001/part2_reply_blocks_preview_summary.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a V3 Part2 reply block preview from the current master.")
    parser.add_argument("--master", default=str(DEFAULT_MASTER), help="Path to the V3 master CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Preview CSV output path.")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="Summary markdown output path.")
    return parser.parse_args()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compact_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


QUOTE_HEADER_PATTERNS = [
    re.compile(r"^On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^Am .+ schrieb.*:\s*$", re.IGNORECASE),
    re.compile(r"^Le .+ a écrit\s*:\s*$", re.IGNORECASE),
    re.compile(r"^\d{4}年.+<[^>]+>:\s*$"),
    re.compile(r"^From:\s.+", re.IGNORECASE),
    re.compile(r"^发件人[:：].+"),
]

OUTBOUND_FINGERPRINTS = [
    "I'm Annabel from Rockbase Agency.",
    "Our team has a strong track record in the AI and tech ecosystem.",
    "We have delivered high-impact campaigns for leading brands including",
    "We are currently finalizing our Premium Creator Shortlist for Q2",
    "Current rates for all channels",
]


def find_quote_start(lines: List[str]) -> int:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            return idx
        for pattern in QUOTE_HEADER_PATTERNS:
            if pattern.match(stripped):
                return idx
    return -1


def strip_trailing_signature_before_quote(lines: List[str], quote_idx: int) -> List[str]:
    if quote_idx <= 0:
        return lines[:quote_idx]
    window_start = max(0, quote_idx - 12)
    for idx in range(quote_idx - 1, window_start - 1, -1):
        if lines[idx].strip() == "--":
            return lines[:idx]
    return lines[:quote_idx]


def clean_reply_body(value: str) -> str:
    text = compact_text(value)
    if not text:
        return ""
    lines = text.split("\n")
    quote_idx = find_quote_start(lines)
    if quote_idx >= 0:
        lines = strip_trailing_signature_before_quote(lines, quote_idx)
    cleaned = "\n".join(lines).strip()
    return compact_text(cleaned)


def looks_like_outbound_template(value: str) -> bool:
    text = compact_text(value)
    if not text:
        return False
    score = sum(1 for item in OUTBOUND_FINGERPRINTS if item in text)
    return score >= 2


def make_block(reply_at: str, body: str) -> str:
    body_text = clean_reply_body(body)
    if looks_like_outbound_template(body_text):
        return ""
    if not body_text:
        return ""
    stamp = (reply_at or "").strip()
    if stamp:
        return f"[{stamp}]\n{body_text}"
    return body_text


def main() -> None:
    args = parse_args()
    rows = read_csv_rows(Path(args.master))

    preview_rows: List[Dict[str, str]] = []
    counts = {f"mail{i}": 0 for i in range(1, 6)}

    for row in rows:
        preview = {
            "Source_Tag": row.get("Source_Tag", ""),
            "账号ID": row.get("账号ID", ""),
            "频道/作者名称": row.get("频道/作者名称", ""),
            "平台": row.get("平台", ""),
            "多平台标记": row.get("多平台标记", ""),
            "账号链接": row.get("账号链接", ""),
            "语言": row.get("语言", ""),
            "Reply_Contact_Email": row.get("Reply_Contact_Email", ""),
            "mail1_reply_block": make_block(row.get("Mail1_Reply_At", ""), row.get("Mail1_Reply", "")),
            "mail2_reply_block": make_block(row.get("Mail2_Reply_At", ""), row.get("Mail2_Reply", "")),
            "mail3_reply_block": make_block(row.get("Mail3_Reply_At", ""), row.get("Mail3_Reply", "")),
            "mail4_reply_block": "",
            "mail5_reply_block": "",
            "Reply_Thread_ID": row.get("Reply_Thread_ID", ""),
            "Reply_Last_At": row.get("Reply_Last_At", ""),
        }
        for idx in range(1, 6):
            if preview[f"mail{idx}_reply_block"]:
                counts[f"mail{idx}"] += 1
        preview_rows.append(preview)

    fieldnames = list(preview_rows[0].keys()) if preview_rows else []
    write_csv(Path(args.output), preview_rows, fieldnames)

    summary_lines = [
        "# Part2 Reply Blocks Preview Summary",
        "",
        f"- rows: {len(preview_rows)}",
        f"- mail1_reply_block filled: {counts['mail1']}",
        f"- mail2_reply_block filled: {counts['mail2']}",
        f"- mail3_reply_block filled: {counts['mail3']}",
        f"- mail4_reply_block filled: {counts['mail4']}",
        f"- mail5_reply_block filled: {counts['mail5']}",
        "",
        "## Meaning",
        "",
        "- This preview is built from the current master after Part2 backfill.",
        "- mail1/mail2/mail3 blocks reuse the existing reply-at + reply-body pairs.",
        "- mail4/mail5 remain empty until later recovery adds more waves.",
    ]
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text("\n".join(summary_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
