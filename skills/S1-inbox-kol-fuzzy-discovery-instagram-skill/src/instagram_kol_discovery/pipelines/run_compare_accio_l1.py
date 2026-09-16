from __future__ import annotations

import json
from pathlib import Path

from instagram_kol_discovery.io_utils import workbench_dir, write_json


def main() -> None:
    run_date = "2026-04-10"
    output_dir = workbench_dir(run_date)
    compare_path = output_dir / f"instagram_accio_l1_compare_{run_date}.json"

    scrape_summary = json.loads((output_dir / f"instagram_accio_scrapecreators_summary_{run_date}.json").read_text(encoding="utf-8"))
    instaloader_summary = json.loads((output_dir / f"instagram_accio_instaloader_smoke_{run_date}.json").read_text(encoding="utf-8"))

    write_json(
        compare_path,
        {
            "topic": "accio",
            "thresholds": {"views": 2000, "followers": 2000},
            "scrapecreators": scrape_summary,
            "instaloader": instaloader_summary,
            "conclusion": {
                "current_default_l1": "scrapecreators.instagram.reels_search",
                "why": [
                    "ScrapeCreators reels search returned usable content rows and view counts.",
                    "ScrapeCreators profile lookup returned follower counts for discovered owners.",
                    "Instaloader without session hit Instagram login_required / 403 blockers on hashtag and profile routes.",
                ],
            },
        },
    )
    print(compare_path)


if __name__ == "__main__":
    main()
