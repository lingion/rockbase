from __future__ import annotations

import argparse
from pathlib import Path

from instagram_kol_discovery.io_utils import INSTAGRAM_L1_FLEX_FIELDS, INSTAGRAM_L1_REQUIRED_FIELDS, read_csv, safe_text, workbench_dir, write_csv, write_json
from instagram_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge multiple Instagram L1 unified CSV files into one deduped L1 run.")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--input-unified-csv", action="append", required=True, help="Repeat for every L1 unified CSV.")
    args = parser.parse_args()

    content_rows: list[dict[str, str]] = []
    seen_content: set[str] = set()
    source_files: list[str] = []
    min_views = 2000

    for raw_path in args.input_unified_csv:
        path = Path(raw_path).expanduser().resolve()
        source_files.append(str(path))
        for row in read_csv(path):
            if safe_text(row.get("row_type")) != "content":
                continue
            min_views = max(min_views, int(str(row.get("l2_skip_reason") or "0").split("_")[-1]) if "below_views_gate_" in safe_text(row.get("l2_skip_reason")) else min_views)
            key = safe_text(row.get("content_id")) or safe_text(row.get("content_url"))
            if not key or key in seen_content:
                continue
            seen_content.add(key)
            content_rows.append(row)

    candidates = aggregate_to_layer1_candidates(content_rows, min_views_for_l2=min_views)
    unified_rows = content_rows + candidates
    out_dir = workbench_dir(args.run_date)
    unified_csv = out_dir / f"instagram_kol_L1_unified_merged_{args.run_date}.csv"
    candidates_csv = out_dir / f"instagram_kol_L1_candidates_merged_{args.run_date}.csv"
    summary_json = out_dir / f"instagram_kol_L1_merge_summary_{args.run_date}.json"
    write_csv(unified_csv, unified_rows, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_csv(candidates_csv, candidates, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_json(
        summary_json,
        {
            "run_date": args.run_date,
            "source_files": source_files,
            "counts": {
                "deduped_content_rows": len(content_rows),
                "creator_candidates": len(candidates),
                "l2_eligible": sum(1 for row in candidates if safe_text(row.get("l2_eligible")) == "yes"),
            },
        },
    )
    print(candidates_csv)


if __name__ == "__main__":
    main()
