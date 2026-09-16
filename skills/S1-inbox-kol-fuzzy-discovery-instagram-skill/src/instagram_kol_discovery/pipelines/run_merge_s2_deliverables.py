from __future__ import annotations

import argparse
from pathlib import Path

from instagram_kol_discovery.io_utils import read_csv, safe_text, workbench_dir, write_csv, write_json
from instagram_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision
from instagram_kol_discovery.pipelines.run_l3_to_s2_mapping import S2_COLUMNS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Instagram S2 deliverables into one sorted, deduped CSV.")
    parser.add_argument("--run-date", required=True, help="Date folder under deliverables/YYYY-MM-DD")
    return parser.parse_args()


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _deliverables_dir(run_date: str) -> Path:
    target = _skill_root() / "deliverables" / run_date
    target.mkdir(parents=True, exist_ok=True)
    return target


def _cleanup_deliverables_dir(run_date: str) -> list[str]:
    removed: list[str] = []
    target = _deliverables_dir(run_date)
    for path in sorted(target.glob("【S2_cold】*.csv")):
        if path.name.endswith("_merged_final.csv"):
            continue
        if path.is_file():
            path.unlink()
            removed.append(path.name)
    audit_json = target / f"【S2_cold】{run_date}_instagram_kol_S2_merge_audit.json"
    if audit_json.exists():
        audit_json.unlink()
        removed.append(audit_json.name)
    return removed


def _followers(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _merge_key(row: dict[str, str]) -> str:
    account_id = safe_text(row.get("账号ID")).lower().lstrip("@")
    if account_id:
        return account_id
    return f"row:{safe_text(row.get('账号链接'))}"


def main() -> int:
    args = _parse_args()
    input_dir = workbench_dir(args.run_date)
    deliverables_dir = _deliverables_dir(args.run_date)
    batch_paths = sorted(
        path
        for path in input_dir.glob(f"instagram_kol_S2_cold_batch*_{args.run_date}.csv")
        if "merged_final" not in path.name
    )
    all_rows: list[dict[str, str]] = []
    for path in batch_paths:
        all_rows.extend(read_csv(path))

    gated_rows: list[dict[str, str]] = []
    removed_org_rows: list[dict[str, str]] = []
    for row in all_rows:
        decision = deliverable_gate_decision(row)
        if decision.allowed:
            gated_rows.append(row)
        else:
            removed_org_rows.append(
                {
                    "账号ID": safe_text(row.get("账号ID")),
                    "频道/作者名称": safe_text(row.get("频道/作者名称")),
                    "reason": decision.reason,
                }
            )

    deduped: dict[str, dict[str, str]] = {}
    duplicates: list[dict[str, str]] = []
    for row in gated_rows:
        key = _merge_key(row)
        if key in deduped:
            duplicates.append({"key": key, "账号ID": safe_text(row.get("账号ID")), "账号链接": safe_text(row.get("账号链接"))})
            continue
        deduped[key] = row

    merged_rows = sorted(deduped.values(), key=lambda row: (-_followers(row.get("粉丝数", "")), safe_text(row.get("账号ID"))))
    merged_csv = deliverables_dir / f"【S2_cold】{args.run_date}_instagram_kol_S2_merged_final.csv"
    audit_json = workbench_dir(args.run_date) / f"instagram_kol_S2_merge_audit_{args.run_date}.json"

    write_csv(merged_csv, merged_rows, preferred_fields=S2_COLUMNS)
    removed_process_files = _cleanup_deliverables_dir(args.run_date)
    write_json(
        audit_json,
        {
            "run_date": args.run_date,
            "source_batches": [str(path) for path in batch_paths],
            "input_dir": str(input_dir),
            "counts": {
                "input_rows": len(all_rows),
                "org_filtered_rows": len(removed_org_rows),
                "post_org_filter_rows": len(gated_rows),
                "deduped_rows": len(merged_rows),
                "duplicate_rows": len(duplicates),
            },
            "removed_org_rows": removed_org_rows,
            "duplicates": duplicates,
            "removed_deliverable_process_files": removed_process_files,
        },
    )
    print(merged_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
