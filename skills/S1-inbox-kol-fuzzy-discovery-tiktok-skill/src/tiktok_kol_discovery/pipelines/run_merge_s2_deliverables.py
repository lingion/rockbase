from __future__ import annotations

import argparse
import json
from pathlib import Path

from tiktok_kol_discovery.io_utils import read_csv, safe_text, workbench_dir, write_csv, write_json
from tiktok_kol_discovery.pipelines.run_l3_to_s2_mapping import S2_COLUMNS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge TikTok S2 workbench batch CSVs into one sorted, deduped final CSV.")
    parser.add_argument("--run-date", required=True, help="Date folder under workbench/YYYY-MM-DD/TikTok")
    parser.add_argument("--input-dir", default="", help="Optional workbench/{date}/TikTok override.")
    parser.add_argument("--output-csv", default="", help="Optional merged CSV output path.")
    parser.add_argument("--audit-json", default="", help="Optional audit JSON output path.")
    parser.add_argument("--followers-gate", type=int, default=3000, help="Hard follower floor for merged final.")
    parser.add_argument(
        "--allow-final-downgrade",
        action="store_true",
        help="Allow overwriting an existing merged final even if the new file has fewer filled contacts.",
    )
    return parser.parse_args()


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _deliverables_dir(run_date: str) -> Path:
    out_dir = _skill_root() / "deliverables" / run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _followers(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _passes_followers_gate(row: dict[str, str], *, followers_gate: int) -> bool:
    return _followers(row.get("粉丝数", "")) >= followers_gate


def _row_is_org_like(row: dict[str, str]) -> bool:
    recommendation = safe_text(row.get("Recommendation"))
    tags = " ".join(
        [
            safe_text(row.get("账号ID")).lower(),
            safe_text(row.get("频道/作者名称")).lower(),
            safe_text(row.get("账号简介__平台抓取")).lower(),
            safe_text(row.get("外链__平台抓取")).lower(),
            recommendation.lower(),
        ]
    )
    org_keywords = [
        " agency",
        " brand",
        " collective",
        " company",
        " media",
        " official",
        " shop",
        " studio",
        " supplier",
        " team",
        " wholesale",
    ]
    return any(keyword in tags for keyword in org_keywords)


def _merge_key(row: dict[str, str]) -> str:
    account_id = safe_text(row.get("账号ID")).lower().lstrip("@")
    if account_id:
        return account_id
    return f"row:{safe_text(row.get('账号链接'))}"


def _filled_contact_count(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if safe_text(row.get("联系方式")))


def main() -> int:
    args = _parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve() if args.input_dir else workbench_dir(args.run_date)
    deliverables_dir = _deliverables_dir(args.run_date)
    batch_paths = sorted(
        path
        for path in input_dir.glob(f"tiktok_kol_S2_cold_batch*_{args.run_date}.csv")
        if path.is_file() and "merged" not in path.name
    )
    if not batch_paths:
        raise SystemExit(f"No TikTok S2 batch workbench CSVs found under {input_dir}")
    all_rows: list[dict[str, str]] = []
    for path in batch_paths:
        all_rows.extend(read_csv(path))
    gated_rows = [row for row in all_rows if _passes_followers_gate(row, followers_gate=args.followers_gate)]
    non_org_rows = [row for row in gated_rows if not _row_is_org_like(row)]

    deduped: dict[str, dict[str, str]] = {}
    duplicates: list[dict[str, str]] = []
    for row in non_org_rows:
        key = _merge_key(row)
        if key in deduped:
            duplicates.append({"key": key, "账号ID": safe_text(row.get("账号ID")), "账号链接": safe_text(row.get("账号链接"))})
            continue
        deduped[key] = row

    merged_rows = sorted(deduped.values(), key=lambda row: (-_followers(row.get("粉丝数", "")), safe_text(row.get("账号ID"))))
    wb_dir = workbench_dir(args.run_date)
    merged_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else deliverables_dir / f"【S2_cold】{args.run_date}_tiktok_kol_S2_merged_final.csv"
    audit_json = Path(args.audit_json).expanduser().resolve() if args.audit_json else wb_dir / f"tiktok_kol_S2_merge_audit_{args.run_date}.json"

    if merged_csv.exists() and not args.allow_final_downgrade:
        existing_rows = read_csv(merged_csv)
        if _filled_contact_count(existing_rows) > _filled_contact_count(merged_rows):
            raise SystemExit(
                "Refusing to overwrite existing merged final because the new merge has fewer filled contacts. "
                "If this downgrade is intentional, rerun with --allow-final-downgrade."
            )
    write_csv(merged_csv, merged_rows, preferred_fields=S2_COLUMNS)
    write_json(
        audit_json,
        {
            "run_date": args.run_date,
            "source_batches": [str(path) for path in batch_paths],
            "input_dir": str(input_dir),
            "counts": {
                "input_rows": len(all_rows),
                "below_followers_gate_rows": len(all_rows) - len(gated_rows),
                "gated_rows": len(gated_rows),
                "org_filtered_rows": len(gated_rows) - len(non_org_rows),
                "post_org_filter_rows": len(non_org_rows),
                "deduped_rows": len(merged_rows),
                "duplicate_rows": len(duplicates),
            },
            "duplicates": duplicates,
        },
    )
    print(merged_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
