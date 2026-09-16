from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from x_kol_discovery.config import Layer1RunConfig
from x_kol_discovery.io_utils import (
    load_skill_env,
    read_csv,
    resolve_scweet_cookie_profiles,
    workbench_dir,
    write_csv,
    write_json,
)
from x_kol_discovery.layer1.scweet_adapter import ScweetCliAdapter
from x_kol_discovery.layer2.discovery_master import persist_discovery_master, route_candidates_with_discovery_master
from x_kol_discovery.layer2.enrichment import build_contact_enrichment_stub, build_layer2_payload_snapshot, enrich_with_scweet_user_info
from x_kol_discovery.layer2.enrichment import (
    apply_layer2_views_gate,
    enrich_with_scrapecreators_twitter_profile,
    sort_rows_by_followers_desc,
)
from x_kol_discovery.task_spec import load_task_spec, task_spec_to_config


def _chunk_rows(rows: list[dict], chunk_size: int) -> list[list[dict]]:
    if chunk_size <= 0 or len(rows) <= chunk_size:
        return [rows]
    return [rows[idx : idx + chunk_size] for idx in range(0, len(rows), chunk_size)]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Layer2 enrichment from existing Layer1 candidate CSV.")
    parser.add_argument(
        "--input-csv",
        required=True,
        help="Absolute or relative path to an existing x_kol_layer1_candidates_*.csv file.",
    )
    parser.add_argument("--run-date", default="2026-03-31", help="Output date folder under workbench/YYYY-MM-DD.")
    parser.add_argument("--batch", default="", help="Optional batch name. When set, outputs use batch-scoped filenames.")
    parser.add_argument(
        "--shortlist-target",
        type=int,
        default=100,
        help="Number of keep/review rows to keep in shortlist output.",
    )
    parser.add_argument(
        "--provider",
        choices=["scrapecreators_twitter_profile", "scweet_user_info"],
        default="",
        help="Layer2 enrichment provider.",
    )
    parser.add_argument("--chunk-size", type=int, default=30, help="Layer2 enrichment chunk size. Default: 30.")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, Layer2 thresholds/provider default come from spec.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    spec_path = ""
    if args.spec:
        spec_payload, resolved_spec_path = load_task_spec(args.spec)
        spec_path = str(resolved_spec_path)
        config = task_spec_to_config(spec_payload, run_date=args.run_date, shortlist_target=args.shortlist_target)
    else:
        config = Layer1RunConfig(run_date=args.run_date, shortlist_target=args.shortlist_target)
    out_dir = workbench_dir(config.run_date)
    print(f"📍 Routing to: {out_dir}")
    batch_name = args.batch or "batch_from_candidates"
    batch_suffix = f"_{args.batch}_{config.run_date}" if args.batch else f"_{config.run_date}"

    input_csv = Path(args.input_csv).expanduser().resolve()
    candidates = read_csv(input_csv)
    eligible_candidates, skipped_candidates = apply_layer2_views_gate(candidates, config.layer2_min_max_views)
    enrichment_candidates, blocked_by_master, master_meta, master_path = route_candidates_with_discovery_master(
        eligible_candidates,
        config,
        batch_name=batch_name,
    )

    enrichment_meta: list[dict[str, str]]
    provider = args.provider or config.layer2_provider
    chunk_size = args.chunk_size or config.layer2_enrichment_chunk_size or 30
    candidate_chunks = _chunk_rows(enrichment_candidates, chunk_size)

    if provider == "scweet_user_info":
        env = load_skill_env()
        adapter = ScweetCliAdapter(
            auth_token=env["X_AUTH_TOKEN"],
            language=config.language,
            profiles=resolve_scweet_cookie_profiles(env),
        )
        enrich_db = out_dir / f"scweet_layer2_state_{config.run_date}.db"
        if enrich_db.exists():
            enrich_db.unlink()
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
        batch_name=batch_name,
        master_path=master_path,
    )
    final_enriched_candidates = sort_rows_by_followers_desc(enriched_candidates)
    shortlist = [row for row in final_enriched_candidates if row["recommended_action"] in {"keep", "review"}][
        : config.shortlist_target
    ]
    contact_stub = [build_contact_enrichment_stub(row) for row in shortlist]

    enriched_csv = out_dir / f"x_kol_L2_enriched{batch_suffix}.csv"
    shortlist_csv = out_dir / f"x_kol_L2_shortlist_{config.shortlist_target}{batch_suffix}.csv"
    contact_csv = out_dir / f"x_kol_L2_contact_stub{batch_suffix}.csv"
    raw_json = out_dir / f"x_kol_L2_raw{batch_suffix}.json"
    runlog_json = out_dir / f"x_kol_L2_runlog{batch_suffix}.json"
    audit_csv = out_dir / f"x_kol_L2_master_audit{batch_suffix}.csv"
    audit_json = out_dir / f"x_kol_L2_master_audit{batch_suffix}.json"

    write_csv(enriched_csv, final_enriched_candidates)
    write_csv(shortlist_csv, shortlist)
    write_csv(contact_csv, contact_stub)
    write_csv(audit_csv, enrichment_meta + master_meta)
    write_json(
        raw_json,
        build_layer2_payload_snapshot(
            provider=provider,
            source_candidates_csv=str(input_csv),
            enrichment_meta=enrichment_meta,
            enriched_candidates=final_enriched_candidates,
        ),
    )
    write_json(
        audit_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_candidates_csv": str(input_csv),
            "spec_path": spec_path,
            "discovery_master_path": str(master_path),
            "counts": {
                "layer1_candidates": len(candidates),
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
        runlog_json,
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_candidates_csv": str(input_csv),
            "spec_path": spec_path,
            "discovery_master_path": str(master_path),
            "provider": provider,
            "layer2_min_max_views_threshold": config.layer2_min_max_views,
            "enrichment_meta": enrichment_meta + master_meta,
            "counts": {
                "layer1_candidates": len(candidates),
                "layer2_candidates_eligible": len(eligible_candidates),
                "layer2_candidates_skipped_by_views_gate": len(skipped_candidates),
                "layer2_candidates_blocked_by_master": len(blocked_by_master),
                "layer2_candidates_sent_to_provider": len(enrichment_candidates),
                "layer2_enriched": len(final_enriched_candidates),
                "shortlist": len(shortlist),
                "chunk_size": chunk_size,
                "chunk_count": len(candidate_chunks),
            },
        },
    )
    print(shortlist_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
