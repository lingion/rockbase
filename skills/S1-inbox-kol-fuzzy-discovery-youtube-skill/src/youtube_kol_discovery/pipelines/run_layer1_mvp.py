from __future__ import annotations

import argparse
from pathlib import Path

from youtube_kol_discovery.io_utils import (
    YOUTUBE_L1_FLEX_FIELDS,
    YOUTUBE_L1_REQUIRED_FIELDS,
    content_rows_to_csv_rows,
    workbench_dir,
    write_csv,
    write_json,
)
from youtube_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates
from youtube_kol_discovery.layer1.youtube_provider import YouTubeProvider
from youtube_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _default_output_dir(spec_path: Path, run_date: str) -> Path:
    return workbench_dir(run_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run YouTube KOL Layer1 MVP.")
    parser.add_argument("--spec", required=True, help="Path to the task spec JSON.")
    parser.add_argument("--run-date", default="", help="Optional run date override.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    args = parser.parse_args()

    spec, spec_path = load_task_spec(args.spec)
    config = task_spec_to_config(spec, run_date=args.run_date or None)
    search_queries = build_search_queries_from_spec(spec)
    provider = YouTubeProvider(region_code=config.country)

    raw_rows: list[dict[str, object]] = []
    runlog: dict[str, object] = {"platform": "youtube", "run_date": config.run_date, "events": []}

    if config.enable_discover_supplement:
        discover_rows, discover_blockers = provider.collect_discover(limit=config.discover_limit)
        raw_rows.extend(discover_rows)
        runlog["events"].append(
            {
                "step": "discover_supplement",
                "enabled": True,
                "result_count": len(discover_rows),
                "blockers": discover_blockers,
            }
        )
    else:
        runlog["events"].append(
            {
                "step": "discover_supplement",
                "enabled": False,
                "notes": ["search-first mode: discover is disabled by default"],
            }
        )

    for search_query in search_queries:
        rows, blockers = provider.collect_search(
            query_name=search_query.name,
            query_text=search_query.query,
            limit=search_query.limit,
        )
        raw_rows.extend(rows)
        runlog["events"].append(
            {
                "step": "search",
                "query_name": search_query.name,
                "query_text": search_query.query,
                "result_count": len(rows),
                "blockers": blockers,
            }
        )

    candidates = aggregate_to_layer1_candidates(raw_rows)
    content_rows = content_rows_to_csv_rows(raw_rows, min_views_for_l2=config.min_content_views_for_l2)
    unified_rows = content_rows + candidates
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else _default_output_dir(spec_path, config.run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_json_path = output_dir / f"youtube_kol_L1_raw_{config.run_date}.json"
    unified_csv_path = output_dir / f"youtube_kol_L1_unified_{config.run_date}.csv"
    candidate_csv_path = output_dir / f"youtube_kol_L1_candidates_{config.run_date}.csv"
    runlog_path = output_dir / f"youtube_kol_L1_runlog_{config.run_date}.json"

    write_json(raw_json_path, raw_rows)
    write_csv(unified_csv_path, unified_rows, preferred_fields=YOUTUBE_L1_REQUIRED_FIELDS + YOUTUBE_L1_FLEX_FIELDS)
    write_csv(candidate_csv_path, candidates, preferred_fields=YOUTUBE_L1_REQUIRED_FIELDS + YOUTUBE_L1_FLEX_FIELDS)
    write_json(runlog_path, runlog)

    print(candidate_csv_path)


if __name__ == "__main__":
    main()
