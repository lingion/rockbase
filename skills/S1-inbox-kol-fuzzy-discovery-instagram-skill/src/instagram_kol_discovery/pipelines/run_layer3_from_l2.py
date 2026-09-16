from __future__ import annotations

import argparse
from pathlib import Path

from instagram_kol_discovery.io_utils import INSTAGRAM_L2_FLEX_FIELDS, INSTAGRAM_L2_REQUIRED_FIELDS, read_csv, workbench_dir, write_csv, write_json


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _to_float(value: str) -> float:
    try:
        return float(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0.0


def _decision_from_row(row: dict[str, str], *, min_followers: int) -> tuple[str, str]:
    followers = _to_int(row.get("followers_count", ""))
    overall = _to_float(row.get("overall_score", ""))
    topic = _to_float(row.get("topic_match_score", ""))
    contactability = _to_float(row.get("contactability_score", ""))
    has_email = bool((row.get("contact_value") or "").strip())

    if followers >= min_followers and overall >= 60 and topic >= 50:
        return "keep", "L3 复核通过：粉丝、主题和活跃度均达标"
    if followers >= min_followers and overall >= 48:
        return "review", "L3 复核：粉丝达标，但综合分仍建议人工判断"
    if has_email and overall >= 50 and contactability >= 55:
        return "review", "L3 复核：已有联系方式，可保留观察"
    if followers <= 0:
        return "review", "L3 复核：粉丝缺失，需人工确认"
    return "drop", "L3 复核：未达到正式 shortlist 标准"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Instagram L3 selection from existing L2 CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to Instagram L2 enriched CSV.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--run-date", default="", help="Run date for output naming.")
    parser.add_argument("--batch", default="batch1", help="Batch name.")
    parser.add_argument("--followers-gate", type=int, default=2000, help="Follower threshold for keep.")
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)
    run_date = args.run_date or input_csv.stem.rsplit("_", 1)[-1]
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workbench_dir(run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    reviewed: list[dict[str, str]] = []
    for row in rows:
        updated = dict(row)
        action, reason = _decision_from_row(updated, min_followers=args.followers_gate)
        updated["recommended_action"] = action
        updated["decision_reason"] = reason
        reviewed.append(updated)

    reviewed.sort(key=lambda row: (-_to_int(row.get("followers_count", "")), -_to_int(row.get("max_views", ""))))
    shortlist = [row for row in reviewed if row.get("recommended_action") in {"keep", "review"}]

    batch_suffix = f"_{args.batch}_{run_date}" if args.batch else f"_{run_date}"
    reviewed_csv = output_dir / f"instagram_kol_L3_reviewed{batch_suffix}.csv"
    shortlist_csv = output_dir / f"instagram_kol_L3_shortlist{batch_suffix}.csv"
    runlog_json = output_dir / f"instagram_kol_L3_runlog{batch_suffix}.json"

    write_csv(reviewed_csv, reviewed, preferred_fields=INSTAGRAM_L2_REQUIRED_FIELDS + INSTAGRAM_L2_FLEX_FIELDS)
    write_csv(shortlist_csv, shortlist, preferred_fields=INSTAGRAM_L2_REQUIRED_FIELDS + INSTAGRAM_L2_FLEX_FIELDS)
    write_json(
        runlog_json,
        {
            "source_l2_csv": str(input_csv),
            "counts": {
                "input_rows": len(rows),
                "keep": sum(1 for row in reviewed if row.get("recommended_action") == "keep"),
                "review": sum(1 for row in reviewed if row.get("recommended_action") == "review"),
                "drop": sum(1 for row in reviewed if row.get("recommended_action") == "drop"),
                "shortlist": len(shortlist),
            },
        },
    )
    print(shortlist_csv)


if __name__ == "__main__":
    main()
