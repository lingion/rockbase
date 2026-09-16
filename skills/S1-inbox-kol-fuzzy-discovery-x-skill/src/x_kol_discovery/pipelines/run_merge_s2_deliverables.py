#!/usr/bin/env python3
"""Merge S2 deliverables for a run date into one sorted, filtered CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


DEFAULT_ORG_HANDLES = {
    "@alphasignalai",
    "@bytebytego",
    "@claudecodelog",
    "@intheworldofai",
    "@langchain",
    "@marketcallshq",
    "@qoder_ai_ide",
    "@remote_jobs_hub",
    "@rivet_dev",
    "@shipper_now",
    "@techmeme",
    "@trending_repos",
    "@warpdotdev",
}

SUSPECT_ORG_KEYWORDS = [
    "agency",
    "ai lab",
    "company",
    "community",
    "corporation",
    "daily",
    "foundation",
    "github repositories",
    "hub",
    "inc",
    "labs",
    "media",
    "newsletter",
    "official",
    "platform",
    "studio",
    "team",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """Return the formal Social Agency project root, never the internal .agent dir."""
    for candidate in [Path.cwd().resolve(), *Path(__file__).resolve().parents]:
        if candidate.name == ".agent":
            continue
        if (candidate / "workbench").is_dir() and (candidate / "Agency").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate Social Agency project root containing workbench/ and Agency/")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [{k: (v or "") for k, v in row.items()} for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_handle(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    if not text.startswith("@"):
        text = "@" + text
    return text


def parse_int(value: str) -> int:
    text = re.sub(r"[^0-9]", "", str(value or ""))
    return int(text) if text else 0


def account_key(row: dict[str, str]) -> str:
    handle = clean_handle(row.get("账号ID", ""))
    if handle:
        return handle
    return (row.get("账号链接") or "").strip().lower()


def org_suspicion_reason(row: dict[str, str]) -> str:
    text = " ".join(
        [
            row.get("账号ID", ""),
            row.get("频道/作者名称", ""),
            row.get("账号简介__平台抓取", ""),
            row.get("账号简介", ""),
        ]
    ).lower()
    for keyword in SUSPECT_ORG_KEYWORDS:
        if keyword in text:
            return f"suspect_keyword:{keyword}"
    return ""


def discover_inputs(deliverables_dir: Path, run_date: str) -> list[Path]:
    pattern = f"x_kol_S2_cold_batch*_{run_date}.csv"
    paths = sorted(deliverables_dir.glob(pattern))
    return [
        path
        for path in paths
        if "merged" not in path.name
        and path.is_file()
        and not path.name.startswith(".")
    ]


def deliverables_dir(run_date: str) -> Path:
    target = repo_root() / "deliverables" / run_date
    target.mkdir(parents=True, exist_ok=True)
    return target


def cleanup_deliverables_dir(run_date: str) -> list[str]:
    removed: list[str] = []
    target = deliverables_dir(run_date)
    patterns = [
        f"【S2_cold】{run_date}_x_kol_S2_batch*.csv",
        f"【S2_cold】{run_date}_x_kol_S2_batch*_netnew.csv",
        f"【S2_cold】{run_date}_x_kol_S2_merged_filtered_dm_3.2.csv",
    ]
    for pattern in patterns:
        for path in sorted(target.glob(pattern)):
            if path.is_file():
                path.unlink()
                removed.append(path.name)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--workbench-dir", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--audit-json", type=Path, default=None)
    parser.add_argument("--org-handle", action="append", default=[], help="Additional org handle to remove. Repeatable.")
    parser.add_argument("--keep-orgs", action="store_true", help="Disable org filtering.")
    parser.add_argument(
        "--remove-suspected-orgs",
        action="store_true",
        help="Also remove keyword-suspected org rows. Default: audit only; final obvious-org removal should still use LLM/manual review.",
    )
    args = parser.parse_args()

    skill_root = repo_root()
    root = project_root()
    input_dir = args.input_dir or root / "workbench" / args.run_date
    workbench_dir = args.workbench_dir or root / "workbench" / args.run_date
    output_csv = args.output_csv or workbench_dir / f"x_kol_S2_merged_filtered_{args.run_date}.csv"
    audit_json = args.audit_json or workbench_dir / f"x_kol_S2_merged_filter_audit_{args.run_date}.json"
    final_csv = deliverables_dir(args.run_date) / f"【S2_cold】{args.run_date}_x_kol_S2_merged_final.csv"

    input_paths = discover_inputs(input_dir, args.run_date)
    if not input_paths:
        raise SystemExit(f"No X S2 batch workbench CSVs found under {input_dir}")

    fieldnames: list[str] = []
    all_rows: list[dict[str, str]] = []
    for path in input_paths:
        fields, rows = read_csv(path)
        for field in fields:
            if field not in fieldnames:
                fieldnames.append(field)
        for row in rows:
            if not any((value or "").strip() for value in row.values()):
                continue
            row["Source_File"] = path.name
            all_rows.append(row)
    if "Source_File" not in fieldnames:
        fieldnames.insert(0, "Source_File")

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

    org_handles = set(DEFAULT_ORG_HANDLES)
    org_handles.update(clean_handle(handle) for handle in args.org_handle)
    kept_rows: list[dict[str, str]] = []
    removed_org_rows: list[dict[str, str]] = []
    suspected_org_rows: list[dict[str, str]] = []
    for row in deduped.values():
        handle = clean_handle(row.get("账号ID", ""))
        if not args.keep_orgs and handle in org_handles:
            removed_org_rows.append(
                {
                    "账号ID": row.get("账号ID", ""),
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "粉丝数": row.get("粉丝数", ""),
                    "reason": "org_handle_list",
                    "source_file": row.get("Source_File", ""),
                }
            )
            continue
        suspicion = "" if args.keep_orgs else org_suspicion_reason(row)
        if suspicion:
            suspect_item = {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "粉丝数": row.get("粉丝数", ""),
                "reason": suspicion,
                "source_file": row.get("Source_File", ""),
            }
            suspected_org_rows.append(suspect_item)
            if args.remove_suspected_orgs:
                removed_org_rows.append(suspect_item)
                continue
        kept_rows.append(row)

    kept_rows.sort(key=lambda row: (-parse_int(row.get("粉丝数", "")), clean_handle(row.get("账号ID", ""))))
    write_csv(output_csv, fieldnames, kept_rows)
    write_csv(final_csv, fieldnames, kept_rows)
    removed_deliverable_files = cleanup_deliverables_dir(args.run_date)

    audit = {
        "input_files": [path.name for path in input_paths],
        "input_dir": str(input_dir),
        "raw_rows": len(all_rows),
        "deduped_rows": len(deduped),
        "duplicate_rows": len(duplicates),
        "removed_org_rows": len(removed_org_rows),
        "kept_rows": len(kept_rows),
        "filter_rule": "script only performs conservative org prefilter; final obvious-org removal requires LLM/manual review",
        "suspected_org_rows": len(suspected_org_rows),
        "suspected_org_policy": "audit_only_by_default; pass --remove-suspected-orgs for aggressive script removal, but normal closeout should use LLM/manual obvious-org review",
        "removed_org_rows_detail": removed_org_rows,
        "suspected_org_rows_detail": suspected_org_rows,
        "duplicates_detail": duplicates,
        "output_csv": str(output_csv),
        "final_csv": str(final_csv),
        "removed_deliverable_files": removed_deliverable_files,
    }
    audit_json.parent.mkdir(parents=True, exist_ok=True)
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
