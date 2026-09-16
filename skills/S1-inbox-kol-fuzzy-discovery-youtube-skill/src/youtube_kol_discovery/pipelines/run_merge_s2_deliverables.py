from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from youtube_kol_discovery.io_utils import read_csv, safe_text, skill_dir, workbench_dir, write_csv, write_json
from youtube_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision


S2_AUDIT_FIELDS = {
    "Source_File",
    "llm_entity_type",
    "llm_decision",
    "llm_confidence",
    "llm_rationale",
    "llm_review_status",
    "needs_llm_review",
    "final_decision",
    "script_decision",
    "account_risk_flags",
}


def deliverables_dir(run_date: str) -> Path:
    out_dir = skill_dir() / "deliverables" / run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def parse_int(value: str) -> int:
    text = re.sub(r"[^0-9]", "", str(value or ""))
    return int(text) if text else 0


def filled_contact_count(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if safe_text(row.get("联系方式")))


def row_has_contact(row: dict[str, str]) -> int:
    return 1 if safe_text(row.get("联系方式")) else 0


def clean_account_id(value: str) -> str:
    return safe_text(value).lower().lstrip("@")


def account_key(row: dict[str, str]) -> str:
    account_id = clean_account_id(row.get("账号ID", ""))
    if account_id:
        return account_id
    return safe_text(row.get("账号链接")).lower()


def _s2_row_to_gate_input(row: dict[str, str]) -> dict[str, str]:
    return {
        "final_decision": safe_text(row.get("final_decision")),
        "llm_decision": safe_text(row.get("llm_decision")),
        "account_risk_flags": safe_text(row.get("account_risk_flags")),
        "llm_entity_type": safe_text(row.get("llm_entity_type")),
        "needs_llm_review": safe_text(row.get("needs_llm_review")),
        "llm_review_status": safe_text(row.get("llm_review_status")),
    }


def discover_inputs(run_date: str, root: Path) -> list[Path]:
    pattern = f"youtube_kol_S2_cold*_{run_date}.csv"
    return [
        path
        for path in sorted(root.glob(pattern))
        if path.is_file() and "merged" not in path.name
    ]


def cleanup_deliverables_dir(run_date: str) -> list[str]:
    removed: list[str] = []
    target_dir = deliverables_dir(run_date)
    patterns = [
        f"【S2_cold】{run_date}_youtube_kol_S2_batch*.csv",
        f"【S2_cold】{run_date}_youtube_kol_S2_batch*_netnew.csv",
    ]
    for pattern in patterns:
        for path in sorted(target_dir.glob(pattern)):
            if path.is_file():
                path.unlink()
                removed.append(path.name)
    return removed


def public_s2_row(row: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in row.items() if key not in S2_AUDIT_FIELDS}


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge YouTube S2 workbench batch CSVs into one sorted, deduped final CSV.")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--input-dir", default="", help="Optional workbench/{date}/YouTube override.")
    parser.add_argument("--output-csv", default="", help="Optional merged CSV output path.")
    parser.add_argument("--audit-json", default="", help="Optional audit JSON output path.")
    parser.add_argument(
        "--allow-final-downgrade",
        action="store_true",
        help="Allow overwriting an existing merged final even if the new file has fewer filled contacts.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve() if args.input_dir else workbench_dir(args.run_date)
    wb_dir = workbench_dir(args.run_date)
    output_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else wb_dir / f"youtube_kol_S2_merged_filtered_{args.run_date}.csv"
    audit_json = Path(args.audit_json).expanduser().resolve() if args.audit_json else wb_dir / f"youtube_kol_S2_merged_filter_audit_{args.run_date}.json"
    final_csv = deliverables_dir(args.run_date) / f"【S2_cold】{args.run_date}_youtube_kol_S2_merged_final.csv"

    input_paths = discover_inputs(args.run_date, input_dir)
    if not input_paths:
        raise SystemExit(f"No YouTube S2 batch workbench CSVs found under {input_dir}")

    fieldnames: list[str] = []
    all_rows: list[dict[str, str]] = []
    for path in input_paths:
        rows = read_csv(path)
        if rows and not fieldnames:
            fieldnames = list(rows[0].keys())
        for row in rows:
            if not any(safe_text(value) for value in row.values()):
                continue
            copied = dict(row)
            copied["Source_File"] = path.name
            all_rows.append(copied)
    if "Source_File" not in fieldnames:
        fieldnames = ["Source_File"] + fieldnames

    deduped: dict[str, dict[str, str]] = {}
    duplicates: list[dict[str, str]] = []
    for row in all_rows:
        key = account_key(row)
        if not key:
            key = f"row:{len(deduped) + len(duplicates)}"
        if key in deduped:
            duplicates.append({"账号ID": row.get("账号ID", ""), "key": key, "source_file": row.get("Source_File", "")})
            continue
        deduped[key] = row

    kept_rows: list[dict[str, str]] = []
    removed_rows: list[dict[str, str]] = []
    for row in deduped.values():
        gate_decision = deliverable_gate_decision(_s2_row_to_gate_input(row))
        if not gate_decision.allowed:
            removed_rows.append(
                {
                    "账号ID": row.get("账号ID", ""),
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "粉丝数": row.get("粉丝数", ""),
                    "reason": gate_decision.reason,
                    "source_file": row.get("Source_File", ""),
                }
            )
            continue
        kept_rows.append(row)

    kept_rows.sort(
        key=lambda row: (
            -row_has_contact(row),
            -parse_int(row.get("粉丝数", "")),
            clean_account_id(row.get("账号ID", "")),
        )
    )
    public_kept_rows = [public_s2_row(row) for row in kept_rows]
    write_csv(output_csv, public_kept_rows, preferred_fields=fieldnames)
    if final_csv.exists() and not args.allow_final_downgrade:
        existing_final_rows = read_csv(final_csv)
        if filled_contact_count(existing_final_rows) > filled_contact_count(public_kept_rows):
            raise SystemExit(
                "Refusing to overwrite existing merged final because the new merge has fewer filled contacts. "
                "If this downgrade is intentional, rerun with --allow-final-downgrade."
            )
    write_csv(final_csv, public_kept_rows, preferred_fields=fieldnames)
    removed_deliverable_process_files = cleanup_deliverables_dir(args.run_date)

    audit = {
        "input_files": [path.name for path in input_paths],
        "input_dir": str(input_dir),
        "raw_rows": len(all_rows),
        "deduped_rows": len(deduped),
        "duplicate_rows": len(duplicates),
        "removed_rows": len(removed_rows),
        "kept_rows": len(kept_rows),
        "removed_rows_detail": removed_rows,
        "duplicates_detail": duplicates,
        "output_csv": str(output_csv),
        "deliverable_final_csv": str(final_csv),
        "removed_deliverable_process_files": removed_deliverable_process_files,
    }
    write_json(audit_json, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
