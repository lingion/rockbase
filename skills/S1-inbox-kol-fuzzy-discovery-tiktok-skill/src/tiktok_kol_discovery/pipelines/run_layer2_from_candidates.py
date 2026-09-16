from __future__ import annotations

import argparse
from pathlib import Path

from tiktok_kol_discovery.io_utils import (
    TIKTOK_L2_FLEX_FIELDS,
    TIKTOK_L2_REQUIRED_FIELDS,
    read_csv,
    workbench_dir,
    write_csv,
    write_json,
)
from tiktok_kol_discovery.layer2.discovery_master import persist_discovery_master, route_candidates_with_discovery_master
from tiktok_kol_discovery.layer2.tiktok_enrichment import TikTokProfileEnricher


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TikTok KOL Layer2 enrichment from existing L1 candidates.")
    parser.add_argument("--input-csv", required=True, help="Path to TikTok L1 candidate CSV.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--run-date", default="", help="Run date for discovery master writes.")
    parser.add_argument("--batch", default="batch1", help="Batch name for discovery master audit.")
    parser.add_argument("--skip-discovery-master", action="store_true", help="Disable discovery master filtering.")
    parser.add_argument("--skip-contact-crawl", action="store_true", help="Disable bio-link email crawl.")
    parser.add_argument("--limit", type=int, default=0, help="Optional candidate limit for debug runs.")
    parser.add_argument("--followers-gate", type=int, default=3000, help="Followers gate for L3 eligibility.")
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    candidates = [row for row in read_csv(input_csv) if row.get("l2_eligible") == "yes"]
    if args.limit > 0:
        candidates = candidates[: args.limit]
    run_date = args.run_date or input_csv.stem.rsplit("_", 1)[-1]
    master_enabled = not args.skip_discovery_master

    enrichment_candidates, blocked_by_master, master_audit_rows, master_path = route_candidates_with_discovery_master(
        candidates,
        batch_name=args.batch,
        enabled=master_enabled,
    )
    enricher = TikTokProfileEnricher(
        min_followers_for_l3=args.followers_gate,
        skip_contact_crawl=args.skip_contact_crawl,
    )
    enriched_rows, runlog = enricher.enrich_candidates(enrichment_candidates)
    persist_discovery_master(
        eligible_candidates=enrichment_candidates,
        fresh_enriched_rows=enriched_rows,
        batch_name=args.batch,
        run_date=run_date,
        enabled=master_enabled,
        master_path=master_path,
    )

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workbench_dir(run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    batch_suffix = f"_{args.batch}_{run_date}" if args.batch else f"_{run_date}"
    enriched_csv = output_dir / f"tiktok_kol_L2_enriched{batch_suffix}.csv"
    shortlist_csv = output_dir / f"tiktok_kol_L2_shortlist{batch_suffix}.csv"
    runlog_json = output_dir / f"tiktok_kol_L2_runlog{batch_suffix}.json"
    audit_csv = output_dir / f"tiktok_kol_L2_master_audit{batch_suffix}.csv"
    audit_json = output_dir / f"tiktok_kol_L2_master_audit{batch_suffix}.json"

    shortlist = [row for row in enriched_rows if row.get("recommended_action") in {"keep", "review"}]
    write_csv(enriched_csv, enriched_rows, preferred_fields=TIKTOK_L2_REQUIRED_FIELDS + TIKTOK_L2_FLEX_FIELDS)
    write_csv(shortlist_csv, shortlist, preferred_fields=TIKTOK_L2_REQUIRED_FIELDS + TIKTOK_L2_FLEX_FIELDS)
    write_csv(audit_csv, master_audit_rows)
    write_json(
        audit_json,
        {
            "source_candidates_csv": str(input_csv),
            "discovery_master_path": str(master_path),
            "counts": {
                "input_candidates": len(candidates),
                "blocked_by_master": len(blocked_by_master),
                "new_to_provider": len(enrichment_candidates),
            },
            "audit_rows": master_audit_rows,
        },
    )
    write_json(
        runlog_json,
        {
            "source_candidates_csv": str(input_csv),
            "discovery_master_path": str(master_path),
            "counts": {
                "input_candidates": len(candidates),
                "blocked_by_master": len(blocked_by_master),
                "new_to_provider": len(enrichment_candidates),
            },
            "rows": runlog,
        },
    )
    print(enriched_csv)


if __name__ == "__main__":
    main()
