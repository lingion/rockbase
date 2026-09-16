from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


BROWSER_INTERNAL_DIR = Path(__file__).resolve().parents[2] / "browser" / "internal"
if str(BROWSER_INTERNAL_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_INTERNAL_DIR))

from extractors.instagram_easykol import enrich_instagram_easykol
from extractors.tiktok_easykol import enrich_tiktok_easykol
from extractors.youtube_easykol import enrich_youtube_easykol
from runner_common import run_enrichment


DEFAULT_FIELDS = [
    "top_pinned_views",
    "avg_views_10",
    "contact",
    "contact_note",
]
DEFAULT_WRITE_EVERY = 10
DEFAULT_BACKUP_EVERY = 100

PLATFORM_EXTRACTORS = {
    "youtube": enrich_youtube_easykol,
    "tiktok": enrich_tiktok_easykol,
    "instagram": enrich_instagram_easykol,
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
        mode_name="easykol_enrichment",
        default_fields=DEFAULT_FIELDS,
        platform_extractors=PLATFORM_EXTRACTORS,
        write_every=DEFAULT_WRITE_EVERY if args.write else 0,
        backup_every=DEFAULT_BACKUP_EVERY if args.write else 0,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
