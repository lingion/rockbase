from __future__ import annotations

import argparse
from pathlib import Path

from tiktok_kol_discovery.io_utils import (
    TIKTOK_L1_FLEX_FIELDS,
    TIKTOK_L1_REQUIRED_FIELDS,
    get_env_value,
    truthy_env,
    workbench_dir,
    write_csv,
    write_json,
)
from tiktok_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates
from tiktok_kol_discovery.layer1.provider_stub import inspect_tiktok_runtime
from tiktok_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _default_output_dir(spec_path: Path, run_date: str) -> Path:
    return workbench_dir(run_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TikTok KOL Layer1 smoke validation.")
    parser.add_argument("--spec", required=True, help="Path to the task spec JSON.")
    parser.add_argument("--run-date", default="", help="Optional run date override.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--no-proxy", action="store_true", help="Disable the default skill-local static proxy for this run.")
    args = parser.parse_args()

    spec, spec_path = load_task_spec(args.spec)
    config = task_spec_to_config(spec, run_date=args.run_date or None)
    search_queries = build_search_queries_from_spec(spec)
    ms_token = get_env_value("TIKTOK_MS_TOKEN")
    proxy_url = get_env_value("TIKTOK_PROXY_URL")
    proxy_enabled = (not args.no_proxy) and truthy_env("TIKTOK_PROXY_ENABLED", default=config.use_proxy_by_default)

    runtime_plan = inspect_tiktok_runtime(has_ms_token=bool(ms_token), proxy_enabled=proxy_enabled)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else _default_output_dir(spec_path, config.run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict[str, object]] = []
    candidates = aggregate_to_layer1_candidates(raw_rows, min_views_for_l2=config.min_content_views_for_l2)
    unified_rows = raw_rows + candidates

    blocker_rows = [
        {
            "platform": "tiktok",
            "row_type": "runtime_blocker",
            "creator_handle": "",
            "display_name": "",
            "content_title": "",
            "theme_text": "",
            "content_url": "",
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "matched_query_name": "",
            "matched_query_text": "",
            "matched_queries": " | ".join(query.query for query in search_queries),
            "matched_content_count": 0,
            "max_views": 0,
            "max_likes": 0,
            "max_comments": 0,
            "sample_contents": "",
            "top_content_url": "",
            "source_content_ids": "",
            "provider_source": runtime_plan.provider_name,
            "discovery_route": "content_first",
            "content_tags_or_hashtags": "",
            "l2_eligible": "no",
            "l2_skip_reason": "runtime_blocked",
            "session_required": "yes",
            "proxy_required": "yes" if proxy_enabled else "no",
        }
    ]

    unified_output = unified_rows if runtime_plan.provider_ready else blocker_rows
    candidates_output = candidates if runtime_plan.provider_ready else blocker_rows

    runlog = {
        "platform": "tiktok",
        "run_date": config.run_date,
        "provider": runtime_plan.provider_name,
        "provider_ready": runtime_plan.provider_ready,
        "queries": [{"name": item.name, "query": item.query, "limit": item.limit} for item in search_queries],
        "env_status": {
            "has_ms_token": bool(ms_token),
            "proxy_enabled": proxy_enabled,
            "proxy_url_present": bool(proxy_url),
            "proxy_mode": "static_ip_default" if proxy_enabled else "disabled_for_this_run",
        },
        "blockers": runtime_plan.blockers,
        "notes": runtime_plan.notes,
        "next_action": "Provide TIKTOK_MS_TOKEN and keep the skill-local static proxy enabled for the first real search validation.",
    }

    raw_json_path = output_dir / f"tiktok_kol_L1_raw_{config.run_date}.json"
    unified_csv_path = output_dir / f"tiktok_kol_L1_unified_{config.run_date}.csv"
    candidate_csv_path = output_dir / f"tiktok_kol_L1_candidates_{config.run_date}.csv"
    runlog_path = output_dir / f"tiktok_kol_L1_runlog_{config.run_date}.json"

    write_json(raw_json_path, raw_rows)
    write_csv(unified_csv_path, unified_output, preferred_fields=TIKTOK_L1_REQUIRED_FIELDS + TIKTOK_L1_FLEX_FIELDS)
    write_csv(candidate_csv_path, candidates_output, preferred_fields=TIKTOK_L1_REQUIRED_FIELDS + TIKTOK_L1_FLEX_FIELDS)
    write_json(runlog_path, runlog)

    print(candidate_csv_path)


if __name__ == "__main__":
    main()
