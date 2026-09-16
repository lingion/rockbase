#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PRICE_RE = re.compile(r"(?i)(US?\$|USD\s*|£|GBP\s*|\$)\s*(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)")

PLATFORM_ORDER = ["YT", "TT", "INS", "X"]
PLATFORM_KEYWORDS = {
    "YT": ["youtube", "yt", "video", "channel"],
    "TT": ["tiktok", "tt"],
    "INS": ["instagram", "insta", "ig", "reel", "short", "shorts"],
    "X": ["twitter", "x.com", "tweet", "x "],
}

DEDICATED_KEYWORDS = [
    "dedicated",
    "full video review",
    "full-length sponsored video",
    "promotional video",
    "review",
    "sponsored unboxing",
    "interview",
]
INTEGRATION_KEYWORDS = [
    "integration",
    "integrated",
    "30s segment",
    "segments",
    "segment",
    "native verbal mention",
]
BUNDLE_KEYWORDS = [
    "bundle",
    "package",
    "buy 2",
    "month",
    "all these factors",
    "includes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pricing-focused review table v2.")
    parser.add_argument("--messages-csv", required=True)
    parser.add_argument("--attachments-report-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
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
    return text.strip()


def short_text(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", clean_text(text))
    return text[: limit - 3] + "..." if len(text) > limit else text


def split_lines(text: str) -> List[str]:
    text = clean_text(text)
    bits = []
    for raw in re.split(r"[\n•]+", text):
        line = re.sub(r"\s+", " ", raw).strip(" -\t")
        if line:
            bits.append(line)
    return bits


def currency_symbol(token: str) -> str:
    token = token.upper().replace(" ", "")
    if "£" in token or "GBP" in token:
        return "£"
    return "$"


def currency_code_from_symbol(symbol: str) -> str:
    return "GBP" if symbol == "£" else "USD"


def detect_platforms(line: str) -> List[str]:
    low = f" {line.lower()} "
    found = []
    for platform, keywords in PLATFORM_KEYWORDS.items():
        if any(keyword in low for keyword in keywords):
            found.append(platform)
    if not found:
        # default to YT for generic "video/channel" pricing in creator outreach
        found = ["YT"]
    return found


def detect_kind(line: str) -> str:
    low = line.lower()
    if any(keyword in low for keyword in INTEGRATION_KEYWORDS):
        return "integration"
    if any(keyword in low for keyword in DEDICATED_KEYWORDS):
        return "dedicated"
    return "other"


def extract_priced_lines(text: str) -> List[Dict[str, str]]:
    priced = []
    for line in split_lines(text):
        prices = list(PRICE_RE.finditer(line))
        if not prices:
            continue
        kind = detect_kind(line)
        platforms = detect_platforms(line)
        bundle_flag = any(keyword in line.lower() for keyword in BUNDLE_KEYWORDS)
        entries = []
        for match in prices:
            symbol = currency_symbol(match.group(1))
            amount = match.group(2).replace(",", "")
            entries.append({"symbol": symbol, "amount": amount})
        priced.append(
            {
                "line": line,
                "kind": kind,
                "platforms": platforms,
                "bundle": "yes" if bundle_flag else "no",
                "prices": entries,
            }
        )
    return priced


def aggregate_attachments(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("message_id", "")].append(row)
    return grouped


def assign_platform_rates(priced_lines: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[str, str]], List[str], List[str]]:
    matrix = {platform: {"dedicated": "", "integration": ""} for platform in PLATFORM_ORDER}
    bundle_lines = []
    raw_lines = []
    for item in priced_lines:
        line = item["line"]
        raw_lines.append(line)
        if item["bundle"] == "yes":
            bundle_lines.append(line)
        target_kind = item["kind"] if item["kind"] in {"dedicated", "integration"} else ""
        if not target_kind:
            continue
        if not item["prices"]:
            continue
        value = f"{item['prices'][0]['symbol']}{item['prices'][0]['amount']}"
        for platform in item["platforms"]:
            if platform in matrix and not matrix[platform][target_kind]:
                matrix[platform][target_kind] = value
    return matrix, bundle_lines, raw_lines


def platform_quote_all(matrix: Dict[str, Dict[str, str]]) -> str:
    lines = []
    for platform in PLATFORM_ORDER:
        dedicated = matrix[platform]["dedicated"] or "-"
        integration = matrix[platform]["integration"] or "-"
        lines.append(f"{platform}: dedicated {dedicated} | integration {integration}")
    return "\n".join(lines)


def find_primary_dedicated(matrix: Dict[str, Dict[str, str]]) -> Tuple[str, str]:
    for platform in PLATFORM_ORDER:
        value = matrix[platform]["dedicated"]
        if value:
            symbol = "£" if value.startswith("£") else "$"
            return value, currency_code_from_symbol(symbol)
    return "", ""


def build_attachment_excerpt(attachments: List[Dict[str, str]]) -> str:
    parts = []
    for attachment in attachments:
        text_file = attachment.get("text_file", "")
        if not text_file or not Path(text_file).exists():
            continue
        text = Path(text_file).read_text(encoding="utf-8", errors="replace")
        priced_lines = extract_priced_lines(text)
        if priced_lines:
            for item in priced_lines[:4]:
                parts.append(f"{attachment.get('filename', '')}: {item['line']}")
        else:
            preview = short_text(text, limit=180)
            if preview:
                parts.append(f"{attachment.get('filename', '')}: {preview}")
    return "\n".join(parts[:8])


def main() -> None:
    args = parse_args()
    message_rows = read_rows(Path(args.messages_csv))
    attachment_rows = read_rows(Path(args.attachments_report_csv))
    attachments_by_message = aggregate_attachments(attachment_rows)

    output_rows = []
    for row in message_rows:
        message_id = row.get("message_id", "")
        body_text = clean_text(row.get("body_text", ""))
        body_priced_lines = extract_priced_lines(body_text)
        attachments = attachments_by_message.get(message_id, [])

        attachment_priced_lines = []
        for attachment in attachments:
            text_file = attachment.get("text_file", "")
            if text_file and Path(text_file).exists():
                attachment_text = Path(text_file).read_text(encoding="utf-8", errors="replace")
                attachment_priced_lines.extend(extract_priced_lines(attachment_text))

        matrix, bundle_lines, raw_pricing_lines = assign_platform_rates(body_priced_lines + attachment_priced_lines)
        dedicated_rate, currency = find_primary_dedicated(matrix)
        quote_all = platform_quote_all(matrix)
        bundle_quote = "\n".join(bundle_lines[:4]) if bundle_lines else ""

        # Prefer explicit price lines from body first, then attachments.
        price_source_lines = [item["line"] for item in body_priced_lines[:4]]
        attachment_excerpt = build_attachment_excerpt(attachments)
        if attachment_excerpt:
            price_source_lines.append(attachment_excerpt)
        pricing_source_excerpt = "\n".join(price_source_lines[:8])

        output_rows.append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "平台": row.get("平台", ""),
                "from_email": row.get("from_email", ""),
                "subject": row.get("subject", ""),
                "reply_at": row.get("reply_at", ""),
                "dedicated_rate": dedicated_rate,
                "currency": currency,
                "quote_all": quote_all,
                "bundle_quote": bundle_quote,
                "pricing_source_excerpt": pricing_source_excerpt,
                "body_summary": short_text(body_text, limit=260),
                "attachment_names": row.get("attachment_names", ""),
                "needs_manual_review": "yes" if attachments else "no",
                "next_action": "review_attachment" if attachments else ("evaluate_rate" if dedicated_rate else "manual_triage"),
                "body_file": row.get("body_file", ""),
            }
        )

    fieldnames = [
        "账号ID",
        "频道/作者名称",
        "平台",
        "from_email",
        "subject",
        "reply_at",
        "dedicated_rate",
        "currency",
        "quote_all",
        "bundle_quote",
        "pricing_source_excerpt",
        "body_summary",
        "attachment_names",
        "needs_manual_review",
        "next_action",
        "body_file",
    ]
    write_rows(Path(args.output_csv), output_rows, fieldnames)

    summary = {
        "rows": len(output_rows),
        "rows_with_dedicated_rate": sum(1 for row in output_rows if row["dedicated_rate"]),
        "rows_with_bundle_quote": sum(1 for row in output_rows if row["bundle_quote"]),
        "rows_with_attachment": sum(1 for row in output_rows if row["attachment_names"]),
        "output_csv": str(Path(args.output_csv).resolve()),
    }
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
