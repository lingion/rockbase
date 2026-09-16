from __future__ import annotations

import argparse
from pathlib import Path

from tiktok_kol_discovery.io_utils import (
    TIKTOK_L1_FLEX_FIELDS,
    TIKTOK_L1_REQUIRED_FIELDS,
    workbench_dir,
    write_csv,
    write_json,
)
from tiktok_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates
from tiktok_kol_discovery.layer1.scrapecreators_client import TikTokScrapeCreatorsClient
from tiktok_kol_discovery.layer1.scrapecreators_normalize import normalize_search_item
from tiktok_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _default_output_dir(spec_path: Path, run_date: str) -> Path:
    return workbench_dir(run_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TikTok KOL Layer1 via ScrapeCreators.")
    parser.add_argument("--spec", required=True, help="Path to the task spec JSON.")
    parser.add_argument("--run-date", default="", help="Optional run date override.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--batch", default="", help="Optional batch suffix for output filenames.")
    parser.add_argument("--region", default="US", help="ScrapeCreators region.")
    parser.add_argument("--date-posted", type=int, default=30, help="Days lookback for keyword search.")
    parser.add_argument("--sort-by", default="most_likes", help="ScrapeCreators sort order.")
    args = parser.parse_args()

    spec, spec_path = load_task_spec(args.spec)
    config = task_spec_to_config(spec, run_date=args.run_date or None)
    search_queries = build_search_queries_from_spec(spec)
    client = TikTokScrapeCreatorsClient()

    raw_payloads: list[dict[str, object]] = []
    content_rows: list[dict[str, object]] = []
    runlog: dict[str, object] = {
        "platform": "tiktok",
        "run_date": config.run_date,
        "provider": "scrapecreators",
        "events": [],
    }

    for search_query in search_queries:
        result = client.search_keyword(
            query=search_query.query,
            region=args.region,
            sort_by=args.sort_by,
            date_posted=args.date_posted,
        )
        raw_payloads.append(
            {
                "query_name": search_query.name,
                "query_text": search_query.query,
                "request_meta": result.request_meta,
                "items": result.items,
            }
        )
        runlog["events"].append(
            {
                "step": "search_keyword",
                "query_name": search_query.name,
                "query_text": search_query.query,
                "result_count": len(result.items),
                "blockers": result.blockers,
            }
        )
        for item in result.items:
            content_rows.append(
                normalize_search_item(
                    item,
                    query_name=search_query.name,
                    query_text=search_query.query,
                    provider_source="scrapecreators.tiktok.search_keyword",
                    min_views_for_l2=config.min_content_views_for_l2,
                )
            )

    candidates = aggregate_to_layer1_candidates(content_rows, min_views_for_l2=config.min_content_views_for_l2)
    unified_rows = content_rows + candidates

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else _default_output_dir(spec_path, config.run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    batch_suffix = f"_{args.batch}_{config.run_date}" if args.batch else f"_{config.run_date}"
    raw_json_path = output_dir / f"tiktok_kol_L1_raw{batch_suffix}.json"
    unified_csv_path = output_dir / f"tiktok_kol_L1_unified{batch_suffix}.csv"
    candidate_csv_path = output_dir / f"tiktok_kol_L1_candidates{batch_suffix}.csv"
    runlog_path = output_dir / f"tiktok_kol_L1_runlog{batch_suffix}.json"

    write_json(raw_json_path, raw_payloads)
    write_csv(unified_csv_path, unified_rows, preferred_fields=TIKTOK_L1_REQUIRED_FIELDS + TIKTOK_L1_FLEX_FIELDS)
    write_csv(candidate_csv_path, candidates, preferred_fields=TIKTOK_L1_REQUIRED_FIELDS + TIKTOK_L1_FLEX_FIELDS)
    write_json(runlog_path, runlog)

    print(candidate_csv_path)


if __name__ == "__main__":
    main()
