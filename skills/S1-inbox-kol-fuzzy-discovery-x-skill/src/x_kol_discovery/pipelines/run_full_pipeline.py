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
from x_kol_discovery.layer2.discovery_master import persist_discovery_master, route_candidates_with_discovery_master
from x_kol_discovery.layer2.enrichment import (
    apply_layer2_views_gate,
    build_contact_enrichment_stub,
    build_layer2_payload_snapshot,
    enrich_with_scrapecreators_twitter_profile,
    enrich_with_scweet_user_info,
    sort_rows_by_followers_desc,
)
from x_kol_discovery.layer3.ranking import apply_layer3_followers_gate
from x_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full Layer1 + Layer2 X KOL pipeline.")
    parser.add_argument("--run-date", default="2026-03-31", help="Output date folder under workbench/YYYY-MM-DD.")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, all thresholds/queries come from spec.")
    parser.add_argument("--query-start", type=int, default=0, help="0-based query slice start for safer batch execution.")
    parser.add_argument("--query-count", type=int, default=0, help="Optional query slice length. 0 means use all remaining queries.")
    parser.add_argument("--query-variant", default="default", help="Optional query pack variant, e.g. default or batch3_alt.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
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
    batch_name = "full_pipeline"
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
        search_adapter = BirdCliAdapter(auth_token=auth_token, ct0=ct0, language=config.language)
    else:
        search_adapter = ScweetCliAdapter(auth_token=auth_token, language=config.language, profiles=cookie_profiles)
    adapter = ScweetCliAdapter(auth_token=auth_token, language=config.language, profiles=cookie_profiles)

    search_db = out_dir / f"scweet_layer1_state_{config.run_date}.db"
    enrich_db = out_dir / f"scweet_layer2_state_{config.run_date}.db"
    if search_db.exists():
        search_db.unlink()
    if enrich_db.exists():
        enrich_db.unlink()

    raw_rows: list[dict] = []
    search_meta: list[dict] = []
    for search_query in search_queries:
        rows, run_meta = search_adapter.search(search_query, config=config, db_path=search_db)
        search_meta.append(run_meta)
        if config.layer1_provider == "bird_cli":
            raw_rows.extend(bird_search_rows_to_records(rows, search_query.name, search_query.query))
        else:
            raw_rows.extend(raw_search_rows_to_records(rows, search_query.name, search_query.query))
    persist_query_registry(
        executed_queries=search_queries,
        search_meta=search_meta,
        run_date=config.run_date,
        batch_name=batch_name,
        query_variant=query_variant,
        registry_path=registry_path,
        enabled=config.query_registry_enabled,
    )
    raw_rows = dedupe_raw_rows(raw_rows)
    layer1_candidates = aggregate_to_layer1_candidates(raw_rows)

    eligible_candidates, skipped_candidates = apply_layer2_views_gate(layer1_candidates, config.layer2_min_max_views)
    enrichment_candidates, blocked_by_master, master_meta, master_path = route_candidates_with_discovery_master(
        eligible_candidates,
        config,
        batch_name="full_pipeline",
    )
    if config.layer2_provider == "scweet_user_info":
        enriched_candidates, enrichment_meta = enrich_with_scweet_user_info(
            enrichment_candidates,
            adapter=adapter,
            config=config,
            db_path=enrich_db,
        )
    else:
        enriched_candidates, enrichment_meta = enrich_with_scrapecreators_twitter_profile(
            enrichment_candidates,
            config=config,
        )
    persist_discovery_master(
        eligible_candidates=eligible_candidates,
        fresh_enriched_rows=enriched_candidates,
        reused_rows=[],
        config=config,
        batch_name="full_pipeline",
        master_path=master_path,
    )
    final_enriched_candidates = sort_rows_by_followers_desc(enriched_candidates)
    layer3_eligible, _ = apply_layer3_followers_gate(final_enriched_candidates, config.layer3_min_followers)
    shortlist = [row for row in layer3_eligible if row["recommended_action"] in {"keep", "review"}][: config.shortlist_target]
    contact_stub = [build_contact_enrichment_stub(row) for row in shortlist]

    write_json(
        out_dir / f"x_kol_full_raw_{config.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "layer1_provider": config.layer1_provider,
            "query_registry_path": str(registry_path),
            "query_variant": query_variant,
            "query_registry_blocked": blocked_queries,
            "search_meta": search_meta,
            "raw_rows": raw_rows,
        },
    )
    write_csv(out_dir / f"x_kol_full_raw_{config.run_date}.csv", raw_rows)
    write_csv(out_dir / f"x_kol_full_layer1_candidates_{config.run_date}.csv", layer1_candidates)
    write_csv(out_dir / f"x_kol_full_layer2_enriched_{config.run_date}.csv", final_enriched_candidates)
    write_csv(out_dir / f"x_kol_full_shortlist_{config.shortlist_target}_{config.run_date}.csv", shortlist)
    write_csv(out_dir / f"x_kol_full_contact_stub_{config.run_date}.csv", contact_stub)
    write_csv(out_dir / f"x_kol_full_layer2_master_audit_{config.run_date}.csv", enrichment_meta + master_meta)
    write_json(
        out_dir / f"x_kol_full_layer2_raw_{config.run_date}.json",
        build_layer2_payload_snapshot(
            provider=config.layer2_provider,
            source_candidates_csv=str(out_dir / f"x_kol_full_layer1_candidates_{config.run_date}.csv"),
            enrichment_meta=enrichment_meta,
            enriched_candidates=final_enriched_candidates,
        ),
    )
    write_json(
        out_dir / f"x_kol_full_layer2_master_audit_{config.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "discovery_master_path": str(master_path),
            "counts": {
                "layer1_candidates": len(layer1_candidates),
                "eligible_after_views_gate": len(eligible_candidates),
                "blocked_by_views_gate": len(skipped_candidates),
                "blocked_by_master": len(blocked_by_master),
                "new_to_provider": len(enrichment_candidates),
            },
            "audit_rows": enrichment_meta + master_meta,
        },
    )
    write_json(
        out_dir / f"x_kol_full_runlog_{config.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "search_meta": search_meta,
            "query_registry_path": str(registry_path),
            "query_variant": query_variant,
            "query_registry_blocked_count": len(blocked_queries),
            "discovery_master_path": str(master_path),
            "enrichment_meta": enrichment_meta + master_meta,
            "counts": {
                "raw_rows": len(raw_rows),
                "layer1_candidates": len(layer1_candidates),
                "layer2_candidates_eligible": len(eligible_candidates),
                "layer2_candidates_skipped_by_views_gate": len(skipped_candidates),
                "layer2_candidates_blocked_by_master": len(blocked_by_master),
                "layer2_candidates_sent_to_provider": len(enrichment_candidates),
                "layer2_enriched": len(final_enriched_candidates),
                "shortlist": len(shortlist),
            },
        },
    )
    print(out_dir / f"x_kol_full_shortlist_{config.shortlist_target}_{config.run_date}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
