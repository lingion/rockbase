from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from extractors.instagram_basic import enrich_instagram_basic
from extractors.tiktok_basic import enrich_tiktok_basic
from extractors.youtube_basic import enrich_youtube_basic
from runner_common import run_enrichment


DEFAULT_FIELDS = [
    "handle",
    "author_name",
    "country",
    "followers",
    "language",
    "bio_raw",
    "category_tags",
    "external_links_raw",
]

PLATFORM_EXTRACTORS = {
    "youtube": enrich_youtube_basic,
    "tiktok": enrich_tiktok_basic,
    "instagram": enrich_instagram_basic,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--rows", default="")
    parser.add_argument("--target-fields")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-test-copy", action="store_true")
    parser.add_argument("--diff-report", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    report = await run_enrichment(
        csv_path_raw=args.csv_path,
        row_numbers_raw=args.rows,
        target_fields_raw=args.target_fields,
        write=args.write,
        write_test_copy=args.write_test_copy,
        dry_run=args.dry_run,
        diff_report=args.diff_report,
        mode_name="basic_enrichment",
        default_fields=DEFAULT_FIELDS,
        platform_extractors=PLATFORM_EXTRACTORS,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
