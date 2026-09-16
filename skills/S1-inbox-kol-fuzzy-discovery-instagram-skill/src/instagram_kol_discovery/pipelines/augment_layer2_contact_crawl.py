from __future__ import annotations

import argparse
import re
from pathlib import Path

from instagram_kol_discovery.io_utils import (
    INSTAGRAM_L2_FLEX_FIELDS,
    INSTAGRAM_L2_REQUIRED_FIELDS,
    read_csv,
    safe_text,
    workbench_dir,
    write_csv,
    write_json,
)
from instagram_kol_discovery.layer2.contact_page_crawler import ContactPageCrawler


DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _infer_run_date(input_csv: Path) -> str:
    for candidate in [input_csv.parent.name, input_csv.parent.parent.name]:
        if DATE_RE.fullmatch(candidate):
            return candidate
    match = DATE_RE.search(input_csv.stem)
    if match:
        return match.group(0)
    raise ValueError(f"Could not infer run_date from input path: {input_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment an existing Instagram KOL L2 CSV with contact page email crawl.")
    parser.add_argument("--input-csv", required=True, help="Path to an existing Instagram L2 enriched CSV.")
    parser.add_argument("--output-csv", default="", help="Optional output CSV path.")
    parser.add_argument("--runlog-json", default="", help="Optional runlog JSON path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for debug runs.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="HTTP timeout per crawled page.")
    parser.add_argument("--max-urls-per-creator", type=int, default=6, help="Maximum contact URLs to check per creator.")
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)
    crawler = ContactPageCrawler(timeout_seconds=args.timeout_seconds, max_urls_per_creator=args.max_urls_per_creator)
    runlog: list[dict[str, str]] = []
    processed = 0

    for row in rows:
        if args.limit > 0 and processed >= args.limit:
            break
        if safe_text(row.get("contact_value")):
            row.setdefault("contact_page_crawl_status", "not_attempted_existing_contact")
            continue
        links = safe_text(row.get("external_links")) or safe_text(row.get("contact_signals"))
        result = crawler.find_email(links)
        row["contact_page_crawl_status"] = result.crawl_status
        row["contact_page_checked_urls"] = result.checked_urls_text()
        if result.email:
            row["contact_value"] = result.email
            row["email_source_url"] = result.email_source_url
            row["contact_note"] = f"contact page crawl: {result.email_source_url}"
        runlog.append(
            {
                "creator_handle": safe_text(row.get("creator_handle")),
                "contact_page_crawl_status": result.crawl_status,
                "email_found": "yes" if result.email else "no",
                "email_source_url": result.email_source_url,
            }
        )
        processed += 1

    if args.output_csv:
        output_csv = Path(args.output_csv).expanduser().resolve()
    else:
        run_date = _infer_run_date(input_csv)
        output_csv = workbench_dir(run_date) / f"{input_csv.stem}_contact_crawl.csv"
    runlog_json = Path(args.runlog_json).expanduser().resolve() if args.runlog_json else output_csv.with_suffix(".runlog.json")
    write_csv(output_csv, rows, preferred_fields=INSTAGRAM_L2_REQUIRED_FIELDS + INSTAGRAM_L2_FLEX_FIELDS)
    write_json(
        runlog_json,
        {
            "source_l2_csv": str(input_csv),
            "output_csv": str(output_csv),
            "processed_missing_contact_rows": processed,
            "email_found": sum(1 for item in runlog if item["email_found"] == "yes"),
            "rows": runlog,
        },
    )
    print(output_csv)


if __name__ == "__main__":
    main()
