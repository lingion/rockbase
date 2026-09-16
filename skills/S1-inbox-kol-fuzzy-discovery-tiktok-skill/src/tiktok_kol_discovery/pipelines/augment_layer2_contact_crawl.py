from __future__ import annotations

import argparse
from pathlib import Path

from tiktok_kol_discovery.io_utils import read_csv, write_csv
from tiktok_kol_discovery.layer2.contact_page_crawler import ContactPageCrawler


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment TikTok L2 CSV with contact-page email crawl.")
    parser.add_argument("--input-csv", required=True, help="Path to existing TikTok L2 CSV.")
    parser.add_argument("--output-csv", default="", help="Optional output CSV path.")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional max rows to crawl.")
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)
    crawler = ContactPageCrawler()
    pending = [row for row in rows if not (row.get("contact_value") or "").strip() and (row.get("external_links") or "").strip()]
    if args.max_rows > 0:
        pending = pending[: args.max_rows]

    pending_ids = {id(row) for row in pending}
    for row in rows:
        if id(row) not in pending_ids:
            continue
        result = crawler.find_email(row.get("external_links", ""))
        row["contact_page_crawl_status"] = result.crawl_status
        row["contact_page_checked_urls"] = result.checked_urls_text()
        if result.email:
            row["contact_value"] = result.email
            row["contact_note"] = "来源: bioLink page crawl"
            row["email_source_url"] = result.email_source_url

    output_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else input_csv.with_name(f"{input_csv.stem}_contact_crawl.csv")
    write_csv(output_csv, rows)
    print(output_csv)


if __name__ == "__main__":
    main()
