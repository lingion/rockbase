from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from x_kol_discovery.io_utils import read_csv, write_csv, write_json
from x_kol_discovery.layer3.ranking import apply_layer3_followers_gate, rank_enriched_candidates
from x_kol_discovery.task_spec import load_task_spec, task_spec_to_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Layer3 selection from an existing Layer2 enriched CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to x_kol_L2_enriched_batchN_YYYY-MM-DD.csv")
    parser.add_argument("--run-date", required=True, help="Date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
    parser.add_argument("--shortlist-target", type=int, default=100, help="Rows to keep in shortlist")
    parser.add_argument("--min-followers", type=int, default=1000, help="Hard gate: followers_count below this threshold cannot enter Layer3.")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, Layer3 min-followers default comes from spec.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    spec_path = ""
    input_csv = Path(args.input_csv).expanduser().resolve()
    out_dir = input_csv.parent
    print(f"📍 Routing to: {out_dir}")

    enriched_rows = read_csv(input_csv)
    min_followers = args.min_followers
    if args.spec:
        spec_payload, resolved_spec_path = load_task_spec(args.spec)
        spec_path = str(resolved_spec_path)
        min_followers = task_spec_to_config(spec_payload, run_date=args.run_date, shortlist_target=args.shortlist_target).layer3_min_followers
    eligible_rows, gated_out_rows = apply_layer3_followers_gate(enriched_rows, min_followers)
    ranked_rows, shortlist_rows = rank_enriched_candidates(eligible_rows, shortlist_target=args.shortlist_target)
    review_rows = [row for row in ranked_rows if str(row.get("recommended_action") or "") == "review"]
    keep_rows = [row for row in ranked_rows if str(row.get("recommended_action") or "") == "keep"]
    drop_rows = [row for row in ranked_rows if str(row.get("recommended_action") or "") == "drop"]
    base_columns = list(enriched_rows[0].keys()) if enriched_rows else []
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

    write_csv(out_dir / f"x_kol_L3_shortlist_{args.batch}_{args.run_date}.csv", serialize(shortlist_rows))
    write_csv(out_dir / f"x_kol_L3_review_table_{args.batch}_{args.run_date}.csv", serialize(review_rows))
    write_json(
        out_dir / f"x_kol_L3_runlog_{args.batch}_{args.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_enriched_csv": str(input_csv),
            "spec_path": spec_path,
            "min_followers_threshold": min_followers,
            "counts": {
                "layer2_rows": len(enriched_rows),
                "layer2_rows_gated_out_by_min_followers": len(gated_out_rows),
                "layer2_rows_eligible_for_layer3": len(eligible_rows),
                "layer3_ranked_rows": len(ranked_rows),
                "shortlist_rows": len(shortlist_rows),
                "keep_rows": len(keep_rows),
                "review_rows": len(review_rows),
                "drop_rows": len(drop_rows),
            },
        },
    )
    (out_dir / f"x_kol_L3_audit_summary_{args.batch}_{args.run_date}.md").write_text(
        "\n".join(
            [
                f"# L3 Audit Summary {args.batch} {args.run_date}",
                "",
                f"- source: `{input_csv.name}`",
                f"- layer2 rows: `{len(enriched_rows)}`",
                f"- min followers gate: `{min_followers}`",
                f"- gated out by min followers: `{len(gated_out_rows)}`",
                f"- eligible for L3: `{len(eligible_rows)}`",
                f"- shortlist rows: `{len(shortlist_rows)}`",
                f"- keep rows: `{len(keep_rows)}`",
                f"- review rows: `{len(review_rows)}`",
                f"- drop rows: `{len(drop_rows)}`",
                "- shortlist now exports keep/review rows only",
            ]
        ),
        encoding="utf-8",
    )
    print(out_dir / f"x_kol_L3_shortlist_{args.batch}_{args.run_date}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
