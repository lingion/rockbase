#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


EXACT_DROP_HANDLES = {
    "@androiddev",
    "@openclaw",
    "@cursor_ai",
    "@openaidevs",
    "@theinformation",
    "@therundownai",
    "@higgsfield_ai",
    "@intcyberdigest",
    "@testingcatalog",
    "@notiondevs",
    "@8090_factory",
}

PERSONAL_SIGNALS = [
    " founder",
    " cofounder",
    " ceo",
    " engineer",
    " developer",
    " researcher",
    " builder",
    " coder",
    " head of ai",
    " product manager",
    " tech lead",
    " professor",
]

ORG_TERMS = [
    "official",
    "newsletter",
    "media",
    "publication",
    "platform",
    "developers",
    "developer platform",
    "largest ai newsletter",
    "read daily",
]

MARKETING_TERMS = [
    "collab",
    "collabs",
    "promotion",
    "promotions",
    "brand partnerships",
    "influencer",
    "dropshipping",
    "recruiter",
    "job vacancies",
    "paid",
    "daily prompts",
]

PRACTITIONER_SIGNALS = [
    "i built",
    "i use",
    "my workflow",
    "my stack",
    "building",
    "shipped",
    "shipping",
    "benchmark",
    "evals",
    "repo",
    "subagents",
    "hooks",
    "skills",
    "mcp",
]


def _text(row: dict[str, str]) -> str:
    return " ".join(
        [
            row.get("账号ID", ""),
            row.get("频道/作者名称", ""),
            row.get("账号简介", ""),
            row.get("账号简介__平台抓取", ""),
            row.get("Latest Activity Proof", ""),
            row.get("外链__平台抓取", ""),
        ]
    ).lower()


def _has_any(text: str, items: list[str]) -> bool:
    return any(item in text for item in items)


def _reason(row: dict[str, str]) -> str:
    handle = (row.get("账号ID") or "").strip().lower()
    text = _text(row)
    if (row.get("语言") or "").strip() != "英语":
        return "drop_non_english"
    if handle in EXACT_DROP_HANDLES:
        return "drop_exact_org_handle"
    if _has_any(text, ORG_TERMS) and not _has_any(text, PERSONAL_SIGNALS):
        return "drop_org_media_profile"
    if _has_any(text, MARKETING_TERMS) and not _has_any(text, PRACTITIONER_SIGNALS + PERSONAL_SIGNALS):
        return "drop_marketing_distribution_profile"
    return "keep"


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple auto-clean: strict drop org/media, broad keep personal.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)
    audit_json = Path(args.audit_json)
    summary_md = Path(args.summary_md)

    with input_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    kept: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []
    for row in rows:
        reason = _reason(row)
        if reason == "keep":
            kept.append(row)
            continue
        removed.append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "粉丝数": row.get("粉丝数", ""),
                "reason": reason,
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    audit = {
        "source_csv": str(input_csv),
        "raw_rows": len(rows),
        "auto_removed_rows": len(removed),
        "auto_kept_rows": len(kept),
        "auto_removed_rows_detail": removed,
        "auto_keep_handles": [row.get("账号ID", "") for row in kept],
        "output_csv": str(output_csv),
    }
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    removed_lines = "\n".join(["- `" + item.get("账号ID", "") + "`: " + item.get("reason", "") for item in removed])
    kept_lines = "\n".join(["- `" + row.get("账号ID", "") + "`" for row in kept])
    summary_md.write_text(
        f"# Auto Personal Clean Summary\n\n- source rows: `{len(rows)}`\n- auto removed rows: `{len(removed)}`\n- auto kept rows: `{len(kept)}`\n\n## Removed Handles\n\n{removed_lines}\n\n## Kept Handles\n\n{kept_lines}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
