from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from x_kol_discovery.config import Layer1RunConfig
from x_kol_discovery.io_utils import (
    ensure_query_names_exist_in_library,
    load_skill_env,
    read_csv,
    resolve_scweet_cookie_profiles,
    workbench_dir,
    write_csv,
    write_json,
)
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
from x_kol_discovery.layer3.ranking import apply_layer3_followers_gate, rank_enriched_candidates
from x_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


def _chunk_rows(rows: list[dict], chunk_size: int) -> list[list[dict]]:
    if chunk_size <= 0 or len(rows) <= chunk_size:
        return [rows]
    return [rows[idx : idx + chunk_size] for idx in range(0, len(rows), chunk_size)]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a full batch pipeline with batch-aware file names.")
    parser.add_argument("--run-date", required=True, help="Date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch2", help="Batch label, e.g. batch2")
    parser.add_argument("--since", default="", help="Layer1 search since date, YYYY-MM-DD")
    parser.add_argument("--until", default="", help="Layer1 search until date, YYYY-MM-DD")
    parser.add_argument("--shortlist-target", type=int, default=100, help="Rows to keep in shortlist")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, all thresholds/queries come from spec.")
    parser.add_argument("--query-start", type=int, default=0, help="0-based query slice start for safer batch execution.")
    parser.add_argument("--query-count", type=int, default=0, help="Optional query slice length. 0 means use all remaining queries.")
    parser.add_argument("--query-variant", default="default", help="Optional query pack variant, e.g. default or batch3_alt.")
    parser.add_argument("--cookie-profile", default="", help="Prefer a specific Scweet cookie profile name for this batch.")
    parser.add_argument(
        "--emit-legacy-s1",
        action="store_true",
        help="Also write legacy S1 inbox compatibility outputs. Default: disabled.",
    )
    return parser.parse_args()


def _write_todo(path: Path, batch: str, run_date: str, since: str, until: str, topic: str, spec_path: str) -> None:
    path.write_text(
        "\n".join(
            [
                f"# x_kol {batch} TODO",
                "",
                f"- run_date: `{run_date}`",
                f"- batch: `{batch}`",
                f"- topic: `{topic}`",
                f"- window: `{since}` -> `{until}`",
                f"- spec_path: `{spec_path}`",
                "",
                "## Steps",
                "",
                "1. Run Layer1 live discovery with the task spec query pack.",
                "2. Dedupe raw hits and write batch-scoped L1 raw + candidates CSV.",
                "3. Apply the free Layer2 admission gate: only candidates with max_views >= 5000 enter profile enrichment.",
                "4. Run Layer2 with the spec-selected provider and write enriched/contact stub outputs.",
                "5. Apply Layer3 min-followers gate, then rank and write shortlist/review/audit outputs.",
                "6. Map Layer3 shortlist into S2 cold inside workbench only.",
                "7. Optionally emit legacy S1 compatibility outputs only when explicitly requested.",
                "8. Copy all batch outputs into the dedicated batch folder for review.",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    spec_path = ""
    if args.spec:
        spec_payload, resolved_spec_path = load_task_spec(args.spec)
        spec_path = str(resolved_spec_path)
        config = task_spec_to_config(spec_payload, run_date=args.run_date, shortlist_target=args.shortlist_target)
        query_variant = str(spec_payload.get("query_variant") or args.query_variant or "default")
        search_queries = build_search_queries_from_spec(spec_payload, query_variant=query_variant)
    else:
        config = Layer1RunConfig(
            run_date=args.run_date,
            since=args.since,
            until=args.until,
            shortlist_target=args.shortlist_target,
        )
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
    ensure_query_names_exist_in_library(search_queries)
    search_queries, blocked_queries, registry_path = route_queries_with_registry(
        search_queries,
        run_date=config.run_date,
        batch_name=args.batch,
        query_variant=query_variant,
        enabled=config.query_registry_enabled,
    )
    root_dir = workbench_dir(args.run_date)
    batch_dir = root_dir / f"x_kol_{args.batch}_pipeline"
    batch_dir.mkdir(parents=True, exist_ok=True)
    print(f"📍 Routing to: {batch_dir}")

    _write_todo(
        batch_dir / f"x_kol_{args.batch}_todo_{args.run_date}.md",
        batch=args.batch,
        run_date=args.run_date,
        since=config.since,
        until=config.until,
        topic=config.topic_query or config.task_name,
        spec_path=spec_path,
    )
    env = load_skill_env()
    auth_token = env.get("X_AUTH_TOKEN") or env.get("AUTH_TOKEN") or ""
    ct0 = env.get("CT0") or env.get("X_CT0") or ""
    cookie_profiles = resolve_scweet_cookie_profiles(env, preferred_profile=args.cookie_profile)
    if config.layer1_provider == "bird_cli":
        search_adapter = BirdCliAdapter(auth_token=auth_token, ct0=ct0, language=config.language)
    else:
        search_adapter = ScweetCliAdapter(auth_token=auth_token, language=config.language, profiles=cookie_profiles)
    adapter = ScweetCliAdapter(auth_token=auth_token, language=config.language, profiles=cookie_profiles)

    search_db = batch_dir / f"scweet_layer1_state_{args.batch}_{args.run_date}.db"
    enrich_db = batch_dir / f"scweet_layer2_state_{args.batch}_{args.run_date}.db"
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
        batch_name=args.batch,
        query_variant=query_variant,
        registry_path=registry_path,
        enabled=config.query_registry_enabled,
    )

    raw_rows = dedupe_raw_rows(raw_rows)
    l1_candidates = aggregate_to_layer1_candidates(raw_rows)

    l1_raw_json = batch_dir / f"x_kol_L1_raw_{args.batch}_{args.run_date}.json"
    l1_raw_csv = batch_dir / f"x_kol_L1_raw_{args.batch}_{args.run_date}.csv"
    l1_candidates_csv = batch_dir / f"x_kol_L1_candidates_{args.batch}_{args.run_date}.csv"
    l1_runlog_json = batch_dir / f"x_kol_L1_runlog_{args.batch}_{args.run_date}.json"

    write_json(
        l1_raw_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "search_meta": search_meta,
            "rows": raw_rows,
        },
    )
    write_csv(l1_raw_csv, raw_rows)
    write_csv(l1_candidates_csv, l1_candidates)
    write_json(
        l1_runlog_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "layer1_provider": config.layer1_provider,
            "query_registry_path": str(registry_path),
            "query_variant": query_variant,
            "query_registry_blocked": blocked_queries,
            "provider": "scweet",
            "since": config.since,
            "until": config.until,
            "layer2_min_max_views_threshold": config.layer2_min_max_views,
            "counts": {
                "raw_rows": len(raw_rows),
                "candidate_rows": len(l1_candidates),
                "queries_executed": len(search_queries),
                "queries_blocked_by_registry": len(blocked_queries),
            },
            "search_meta": search_meta,
        },
    )

    eligible_candidates, skipped_candidates = apply_layer2_views_gate(l1_candidates, config.layer2_min_max_views)
    enrichment_candidates, blocked_by_master, master_meta, master_path = route_candidates_with_discovery_master(
        eligible_candidates,
        config,
        batch_name=args.batch,
    )
    chunk_size = config.layer2_enrichment_chunk_size or 30
    candidate_chunks = _chunk_rows(enrichment_candidates, chunk_size)
    if config.layer2_provider == "scweet_user_info":
        enriched_candidates = []
        enrichment_meta = []
        for idx, chunk in enumerate(candidate_chunks, start=1):
            chunk_enriched, chunk_meta = enrich_with_scweet_user_info(
                chunk,
                adapter=adapter,
                config=config,
                db_path=enrich_db,
            )
            enriched_candidates.extend(chunk_enriched)
            enrichment_meta.extend(
                [{**row, "chunk_index": idx, "chunk_size": len(chunk)} for row in chunk_meta]
            )
    else:
        enriched_candidates = []
        enrichment_meta = []
        for idx, chunk in enumerate(candidate_chunks, start=1):
            chunk_enriched, chunk_meta = enrich_with_scrapecreators_twitter_profile(
                chunk,
                config=config,
            )
            enriched_candidates.extend(chunk_enriched)
            enrichment_meta.extend(
                [{**row, "chunk_index": idx, "chunk_size": len(chunk)} for row in chunk_meta]
            )
    persist_discovery_master(
        eligible_candidates=eligible_candidates,
        fresh_enriched_rows=enriched_candidates,
        reused_rows=[],
        config=config,
        batch_name=args.batch,
        master_path=master_path,
    )
    final_enriched_candidates = sort_rows_by_followers_desc(enriched_candidates)
    contact_stub = [build_contact_enrichment_stub(row) for row in final_enriched_candidates if row.get("recommended_action") in {"keep", "review"}]

    l2_enriched_csv = batch_dir / f"x_kol_L2_enriched_{args.batch}_{args.run_date}.csv"
    l2_raw_json = batch_dir / f"x_kol_L2_raw_{args.batch}_{args.run_date}.json"
    l2_contact_csv = batch_dir / f"x_kol_L2_contact_stub_{args.batch}_{args.run_date}.csv"
    l2_runlog_json = batch_dir / f"x_kol_L2_runlog_{args.batch}_{args.run_date}.json"
    l2_audit_csv = batch_dir / f"x_kol_L2_master_audit_{args.batch}_{args.run_date}.csv"
    l2_audit_json = batch_dir / f"x_kol_L2_master_audit_{args.batch}_{args.run_date}.json"

    write_csv(l2_enriched_csv, final_enriched_candidates)
    write_csv(l2_contact_csv, contact_stub)
    write_csv(l2_audit_csv, enrichment_meta + master_meta)
    write_json(
        l2_raw_json,
        build_layer2_payload_snapshot(
            provider=config.layer2_provider,
            source_candidates_csv=str(l1_candidates_csv),
            enrichment_meta=enrichment_meta,
            enriched_candidates=final_enriched_candidates,
        ),
    )
    write_json(
        l2_audit_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "discovery_master_path": str(master_path),
            "counts": {
                "layer1_candidates": len(l1_candidates),
                "eligible_after_views_gate": len(eligible_candidates),
                "blocked_by_views_gate": len(skipped_candidates),
                "blocked_by_master": len(blocked_by_master),
                "new_to_provider": len(enrichment_candidates),
                "chunk_size": chunk_size,
                "chunk_count": len(candidate_chunks),
            },
            "audit_rows": enrichment_meta + master_meta,
        },
    )
    write_json(
        l2_runlog_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "provider": config.layer2_provider,
            "discovery_master_path": str(master_path),
            "query_registry_path": str(registry_path),
            "layer2_min_max_views_threshold": config.layer2_min_max_views,
            "counts": {
                "layer1_candidates": len(l1_candidates),
                "layer2_candidates_eligible": len(eligible_candidates),
                "layer2_candidates_skipped_by_views_gate": len(skipped_candidates),
                "layer2_candidates_blocked_by_master": len(blocked_by_master),
                "layer2_candidates_sent_to_provider": len(enrichment_candidates),
                "layer2_enriched": len(final_enriched_candidates),
                "chunk_size": chunk_size,
                "chunk_count": len(candidate_chunks),
            },
            "enrichment_meta": enrichment_meta + master_meta,
        },
    )

    layer3_eligible_rows, layer3_gated_out_rows = apply_layer3_followers_gate(final_enriched_candidates, config.layer3_min_followers)
    ranked_rows, shortlist_rows = rank_enriched_candidates(layer3_eligible_rows, shortlist_target=args.shortlist_target)
    review_rows = [row for row in ranked_rows if str(row.get("recommended_action") or "") == "review"]
    base_columns = list(final_enriched_candidates[0].keys()) if final_enriched_candidates else []
    decision_columns = [
        "primary_language",
        "language_mix",
        "country_inferred",
        "country_confidence",
        "matched_signals",
        "decision_reason",
        "language_signal",
        "country_signal",
    ]
    output_columns = base_columns + [col for col in decision_columns if col not in base_columns]

    def serialize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{col: row.get(col, "") for col in output_columns} for row in rows]

    l3_shortlist_csv = batch_dir / f"x_kol_L3_shortlist_{args.batch}_{args.run_date}.csv"
    l3_review_csv = batch_dir / f"x_kol_L3_review_table_{args.batch}_{args.run_date}.csv"
    l3_runlog_json = batch_dir / f"x_kol_L3_runlog_{args.batch}_{args.run_date}.json"
    l3_audit_md = batch_dir / f"x_kol_L3_audit_summary_{args.batch}_{args.run_date}.md"

    write_csv(l3_shortlist_csv, serialize(shortlist_rows))
    write_csv(l3_review_csv, serialize(review_rows))
    write_json(
        l3_runlog_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec_path": spec_path,
            "layer3_min_followers_threshold": config.layer3_min_followers,
            "counts": {
                "layer2_rows": len(final_enriched_candidates),
                "layer3_rows_gated_out_by_min_followers": len(layer3_gated_out_rows),
                "layer3_rows_eligible": len(layer3_eligible_rows),
                "layer3_ranked_rows": len(ranked_rows),
                "shortlist_rows": len(shortlist_rows),
                "review_rows": len(review_rows),
            },
        },
    )
    l3_audit_md.write_text(
        "\n".join(
            [
                f"# L3 Audit Summary {args.batch} {args.run_date}",
                "",
                f"- source: `{l2_enriched_csv.name}`",
                f"- layer2 rows: `{len(final_enriched_candidates)}`",
                f"- min followers gate: `{config.layer3_min_followers}`",
                f"- gated out by min followers: `{len(layer3_gated_out_rows)}`",
                f"- shortlist rows: `{len(shortlist_rows)}`",
                f"- review rows: `{len(review_rows)}`",
            ]
        ),
        encoding="utf-8",
    )

    from x_kol_discovery.pipelines.run_l3_to_s2_mapping import (
        S2_COLUMNS,
        _map_row as _map_s2_row,
    )

    layer2_by_username = {
        str(row.get("username") or "").strip().lower(): row
        for row in read_csv(l2_enriched_csv)
        if str(row.get("username") or "").strip()
    }
    s2_rows = [_map_s2_row(row, layer2_by_username.get(str(row.get("username") or "").strip().lower())) for row in serialize(shortlist_rows)]
    s2_csv = root_dir / f"x_kol_S2_cold_{args.batch}_{args.run_date}.csv"
    s2_runlog_json = root_dir / f"x_kol_S2_mapping_runlog_{args.batch}_{args.run_date}.json"
    s2_audit_md = root_dir / f"x_kol_S2_mapping_audit_{args.batch}_{args.run_date}.md"
    write_csv(s2_csv, s2_rows if s2_rows else [{col: "" for col in S2_COLUMNS}])
    if not s2_rows:
        s2_csv.write_text(",".join(S2_COLUMNS) + "\n", encoding="utf-8-sig")

    write_json(
        s2_runlog_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_l3_csv": str(l3_shortlist_csv),
            "source_l2_csv": str(l2_enriched_csv),
            "source_l1_csv": str(l1_candidates_csv),
            "spec_path": spec_path,
            "layer2_min_max_views_threshold": config.layer2_min_max_views,
            "rows_gated_out_by_views": 0,
            "rows_written": len(s2_rows),
            "columns": S2_COLUMNS,
            "deliverable_mode": "workbench_only",
            "deliverable_rows_written": 0,
            "deliverable_path": "",
        },
    )
    s2_audit_md.write_text(
        "\n".join(
            [
                f"# L3 to S2 Mapping Audit {args.batch} {args.run_date}",
                "",
                f"- source_l3: `{l3_shortlist_csv.name}`",
                f"- source_l2: `{l2_enriched_csv.name}`",
                f"- source_l1: `{l1_candidates_csv.name}`",
                f"- inherited views gate: `max_views >= {config.layer2_min_max_views}`",
                "- gated out by views: `0`",
                f"- rows written: `{len(s2_rows)}`",
                "- deliverable rows written: `0`",
                "- business-conservative mapping applied",
                "- Mail1 fields intentionally left blank for later LLM fill",
            ]
        ),
        encoding="utf-8",
    )

    legacy_outputs: list[Path] = []
    if args.emit_legacy_s1:
        from x_kol_discovery.pipelines.run_l3_to_s1_mapping import _map_row, S1_COLUMNS

        s1_rows = [_map_row(row) for row in serialize(shortlist_rows)]
        s1_csv = batch_dir / f"x_kol_S1_inbox_{args.batch}_{args.run_date}.csv"
        s1_runlog_json = batch_dir / f"x_kol_S1_inbox_mapping_runlog_{args.batch}_{args.run_date}.json"
        s1_audit_md = batch_dir / f"x_kol_S1_inbox_mapping_audit_{args.batch}_{args.run_date}.md"
        write_csv(s1_csv, s1_rows if s1_rows else [{col: "" for col in S1_COLUMNS}])
        if not s1_rows:
            s1_csv.write_text(",".join(S1_COLUMNS) + "\n", encoding="utf-8-sig")
        write_json(
            s1_runlog_json,
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "source_l3_csv": str(l3_shortlist_csv),
                "rows_written": len(s1_rows),
                "columns": S1_COLUMNS,
                "mode": "legacy_compatibility",
            },
        )
        s1_audit_md.write_text(
            "\n".join(
                [
                    f"# L3 to S1 Mapping Audit {args.batch} {args.run_date}",
                    "",
                    f"- source: `{l3_shortlist_csv.name}`",
                    f"- rows written: `{len(s1_rows)}`",
                    "- legacy compatibility output",
                ]
            ),
            encoding="utf-8",
        )
        legacy_outputs.extend([s1_csv, s1_runlog_json, s1_audit_md])

    # Mirror key outputs to the date root for quick discovery without changing the batch folder canon.
    for path in [
        l1_raw_json,
        l1_raw_csv,
        l1_candidates_csv,
        l1_runlog_json,
        l2_enriched_csv,
        l2_raw_json,
        l2_contact_csv,
        l2_runlog_json,
        l3_shortlist_csv,
        l3_review_csv,
        l3_runlog_json,
        l3_audit_md,
        s2_csv,
        s2_runlog_json,
        s2_audit_md,
        *legacy_outputs,
    ]:
        dest = root_dir / path.name
        if path.resolve() == dest.resolve():
            continue
        shutil.copy2(path, dest)

    print(s2_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
