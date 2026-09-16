from __future__ import annotations

import argparse
from datetime import datetime, timezone

from x_kol_discovery.config import Layer1RunConfig
from x_kol_discovery.io_utils import load_skill_env, resolve_scweet_cookie_profiles, workbench_dir, write_csv, write_json
from x_kol_discovery.layer1.bird_adapter import BirdCliAdapter
from x_kol_discovery.layer1.dedupe import dedupe_raw_rows
from x_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates, bird_search_rows_to_records, raw_search_rows_to_records
from x_kol_discovery.layer1.queries import DEFAULT_OPENCLAW_QUERIES
from x_kol_discovery.layer1.query_registry import persist_query_registry, route_queries_with_registry
from x_kol_discovery.layer1.scweet_adapter import ScweetCliAdapter
from x_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reusable Layer1 X KOL discovery search.")
    parser.add_argument("--run-date", default="2026-03-31", help="Output date folder under workbench/YYYY-MM-DD.")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, Layer1 queries and thresholds come from spec.")
    parser.add_argument("--query-start", type=int, default=0, help="0-based query slice start for safer batch execution.")
    parser.add_argument("--query-count", type=int, default=0, help="Optional query slice length. 0 means use all remaining queries.")
    parser.add_argument("--query-variant", default="default", help="Optional query pack variant, e.g. default or batch3_alt.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    spec_payload: dict | None = None
    spec_path = ""
    if args.spec:
        spec_payload, resolved_spec_path = load_task_spec(args.spec)
        spec_path = str(resolved_spec_path)
        config = task_spec_to_config(spec_payload, run_date=args.run_date)
        query_variant = str(spec_payload.get("query_variant") or args.query_variant or "default")
        search_queries = build_search_queries_from_spec(spec_payload, query_variant=query_variant)
    else:
        config = Layer1RunConfig(run_date=args.run_date)
        query_variant = args.query_variant
        search_queries = DEFAULT_OPENCLAW_QUERIES

    if args.query_start or args.query_count:
        start = max(args.query_start, 0)
        if args.query_count and args.query_count > 0:
            search_queries = search_queries[start : start + args.query_count]
        else:
            search_queries = search_queries[start:]
        if not search_queries:
            raise SystemExit("No search queries remain after applying query slice.")
    batch_name = "layer1_mvp"
    search_queries, blocked_queries, registry_path = route_queries_with_registry(
        search_queries,
        run_date=config.run_date,
        batch_name=batch_name,
        query_variant=query_variant,
        enabled=config.query_registry_enabled,
    )
    out_dir = workbench_dir(config.run_date)
    print(f"📍 Routing to: {out_dir}")
    env = load_skill_env()
    auth_token = env.get("X_AUTH_TOKEN") or env.get("AUTH_TOKEN") or ""
    ct0 = env.get("CT0") or env.get("X_CT0") or ""
    cookie_profiles = resolve_scweet_cookie_profiles(env)
    if config.layer1_provider == "bird_cli":
        adapter = BirdCliAdapter(auth_token=auth_token, ct0=ct0, language=config.language)
    else:
        adapter = ScweetCliAdapter(auth_token=auth_token, language=config.language, profiles=cookie_profiles)
    search_db = out_dir / f"scweet_layer1_state_{config.run_date}.db"
    if search_db.exists():
        search_db.unlink()

    raw_rows: list[dict] = []
    meta: list[dict] = []
    for search_query in search_queries:
        rows, run_meta = adapter.search(search_query, config=config, db_path=search_db)
        meta.append(run_meta)
        if config.layer1_provider == "bird_cli":
            raw_rows.extend(bird_search_rows_to_records(rows, search_query.name, search_query.query))
        else:
            raw_rows.extend(raw_search_rows_to_records(rows, search_query.name, search_query.query))
    persist_query_registry(
        executed_queries=search_queries,
        search_meta=meta,
        run_date=config.run_date,
        batch_name=batch_name,
        query_variant=query_variant,
        registry_path=registry_path,
        enabled=config.query_registry_enabled,
    )

    raw_rows = dedupe_raw_rows(raw_rows)
    candidates = aggregate_to_layer1_candidates(raw_rows)

    write_json(
        out_dir / f"x_kol_layer1_raw_{config.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "task_name": config.task_name,
            "spec_path": spec_path,
            "query_registry_path": str(registry_path),
            "query_variant": query_variant,
            "query_registry_blocked": blocked_queries,
            "search_meta": meta,
            "rows": raw_rows,
        },
    )
    write_csv(out_dir / f"x_kol_layer1_raw_{config.run_date}.csv", raw_rows)
    write_csv(out_dir / f"x_kol_layer1_candidates_{config.run_date}.csv", candidates)
    print(out_dir / f"x_kol_layer1_candidates_{config.run_date}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
