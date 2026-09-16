from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from youtube_kol_discovery.io_utils import read_csv, safe_text, write_csv, write_json
from youtube_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Aully Hub YouTube L3 pools and remove obvious org/media accounts.")
    parser.add_argument("--input-root", required=True, help="AullyHub root directory that contains batch_* folders.")
    parser.add_argument("--output-csv", required=True, help="Merged L3 pool output CSV.")
    parser.add_argument("--audit-json", required=True, help="Audit JSON output path.")
    parser.add_argument(
        "--glob",
        default="batch_*/*_L3_shortlist_final_*.csv",
        help="Glob under input-root for L3 shortlist inputs.",
    )
    return parser.parse_args()


def _row_key(row: dict[str, str]) -> str:
    creator_handle = safe_text(row.get("creator_handle")).lower()
    if creator_handle:
        return creator_handle
    return safe_text(row.get("profile_url")).lower()


def _sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    email = 1 if safe_text(row.get("clean_email") or row.get("contact_value")) else 0
    followers = int("".join(ch for ch in safe_text(row.get("followers_count")) if ch.isdigit()) or "0")
    views = int("".join(ch for ch in safe_text(row.get("max_views")) if ch.isdigit()) or "0")
    return (-email, -followers, -views, safe_text(row.get("display_name")).lower())


def main() -> int:
    args = _parse_args()
    input_root = Path(args.input_root).expanduser().resolve()
    paths = sorted(path for path in input_root.glob(args.glob) if path.is_file())
    if not paths:
        raise SystemExit(f"No L3 shortlist files found under {input_root} with glob {args.glob}")

    all_rows: list[dict[str, str]] = []
    fieldnames: list[str] = []
    for path in paths:
        rows = read_csv(path)
        if rows and not fieldnames:
            fieldnames = list(rows[0].keys())
        for row in rows:
            copied = dict(row)
            copied["source_file"] = path.name
            copied["source_batch"] = path.parent.name
            all_rows.append(copied)
    if "source_file" not in fieldnames:
        fieldnames += ["source_file", "source_batch"]

    deduped: dict[str, dict[str, str]] = {}
    duplicates: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []
    for row in all_rows:
        gate_decision = deliverable_gate_decision(
            {
                "final_decision": safe_text(row.get("final_decision")),
                "llm_decision": safe_text(row.get("llm_decision")),
                "llm_entity_type": safe_text(row.get("llm_entity_type")),
                "llm_review_status": safe_text(row.get("llm_review_status")),
            }
        )
        if not gate_decision.allowed:
            removed.append(
                {
                    "display_name": safe_text(row.get("display_name")),
                    "creator_handle": safe_text(row.get("creator_handle")),
                    "reason": gate_decision.reason,
                    "source_file": safe_text(row.get("source_file")),
                }
            )
            continue
        key = _row_key(row)
        if not key:
            key = f"row:{len(deduped) + len(duplicates)}"
        if key in deduped:
            duplicates.append(
                {
                    "display_name": safe_text(row.get("display_name")),
                    "creator_handle": safe_text(row.get("creator_handle")),
                    "source_file": safe_text(row.get("source_file")),
                }
            )
            existing = deduped[key]
            if _sort_key(row) < _sort_key(existing):
                deduped[key] = row
            continue
        deduped[key] = row

    kept_rows = sorted(deduped.values(), key=_sort_key)
    write_csv(Path(args.output_csv).expanduser().resolve(), kept_rows, preferred_fields=fieldnames)
    write_json(
        Path(args.audit_json).expanduser().resolve(),
        {
            "input_root": str(input_root),
            "input_files": [path.name for path in paths],
            "raw_rows": len(all_rows),
            "removed_org_or_media_rows": len(removed),
            "duplicate_rows": len(duplicates),
            "kept_rows": len(kept_rows),
            "removed_rows_detail": removed,
            "duplicate_rows_detail": duplicates,
        },
    )
    print(json.dumps({"kept_rows": len(kept_rows), "removed_org_or_media_rows": len(removed)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
