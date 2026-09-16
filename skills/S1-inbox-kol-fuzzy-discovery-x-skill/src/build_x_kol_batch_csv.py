from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_COLUMNS = [
    "账号ID",
    "频道/作者名称",
    "平台",
    "账号链接",
    "语言",
    "粉丝数",
    "账号简介__平台抓取",
    "Sample Content",
    "外链__平台抓取",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deduped X KOL batch CSV from scraped JSON.")
    parser.add_argument("--reference-csv", required=True)
    parser.add_argument("--profiles-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--batch-label", required=True)
    parser.add_argument("--source-file", default="")
    parser.add_argument("--reporter", default="Codex")
    return parser.parse_args()


def load_header(reference_csv: Path) -> list[str]:
    with reference_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def detect_language(text: str) -> str:
    sample = (text or "").strip()
    if not sample:
        return ""
    lowered = sample.lower()
    spanish_tokens = {" que ", " los ", " las ", " para ", " una ", " pero ", " gracias ", " más ", " como ", " cosas "}
    if any(token in f" {lowered} " for token in spanish_tokens):
        return "Spanish"
    return "English"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def make_backup_if_needed(output_csv: Path, backup_root: Path) -> Path | None:
    if not output_csv.exists():
        return None
    backup_dir = backup_root / datetime.now().strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"{output_csv.name}_bak_{datetime.now().strftime('%H%M%S')}.csv"
    backup_path = backup_dir / backup_name
    shutil.copy2(output_csv, backup_path)
    return backup_path


def existing_rows(output_csv: Path) -> list[dict[str, str]]:
    if not output_csv.exists():
        return []
    with output_csv.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def profile_to_row(profile: dict, columns: list[str], batch_label: str, source_file: str, reporter: str) -> dict[str, str]:
    row = {col: "" for col in columns}
    candidate = profile.get("candidate", {})
    external_links = profile.get("externalLinks") or []
    first_external = external_links[0]["href"] if external_links else ""
    sample_content = clean_text(candidate.get("text") or profile.get("latestOwnText") or "")
    if candidate.get("handle"):
        account_key = candidate["handle"].lstrip("@")
    else:
        account_key = ""

    row["Source_File"] = source_file
    row["分区"] = batch_label
    row["备注"] = "May batch via Chrome plugin"
    row["提报人"] = reporter
    row["账号ID"] = str(profile.get("accountId") or account_key)
    row["频道/作者名称"] = clean_text(profile.get("name") or candidate.get("name") or "")
    row["平台"] = "X"
    row["账号链接"] = profile.get("profileUrl") or (f"https://x.com/{account_key}" if account_key else "")
    row["语言"] = detect_language(sample_content)
    row["粉丝数"] = str(profile.get("followers") or "")
    row["账号简介__平台抓取"] = clean_text(profile.get("bio") or "")
    row["Sample Content"] = sample_content
    row["外链__平台抓取"] = first_external
    row["Recommendation"] = f"Pass-{batch_label}" if profile.get("hasDM") and (profile.get("followers") or 0) >= 1000 else ""
    row["联系方式备注"] = "DM visible on profile" if profile.get("hasDM") else ""
    return row


def main() -> None:
    args = parse_args()
    reference_csv = Path(args.reference_csv)
    profiles_json = Path(args.profiles_json)
    output_csv = Path(args.output_csv)
    backup_root = Path(args.backup_root)

    columns = load_header(reference_csv)
    profiles = json.loads(profiles_json.read_text(encoding="utf-8"))

    filtered_profiles = [
        profile
        for profile in profiles
        if (profile.get("followers") or 0) >= 1000 and profile.get("hasDM")
    ]

    new_rows = [
        profile_to_row(profile, columns, args.batch_label, args.source_file, args.reporter)
        for profile in filtered_profiles
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    backup_path = make_backup_if_needed(output_csv, backup_root)
    rows = existing_rows(output_csv)

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("账号ID", "").strip() or row.get("账号链接", "").strip()
        if not key:
            continue
        deduped[key] = row
    for row in new_rows:
        key = row.get("账号ID", "").strip() or row.get("账号链接", "").strip()
        if not key or key in deduped:
            continue
        deduped[key] = row

    final_rows = list(deduped.values())
    final_rows.sort(key=lambda row: (row.get("粉丝数", ""), row.get("频道/作者名称", "")), reverse=True)

    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(final_rows)

    summary = {
        "output_csv": str(output_csv),
        "backup_path": str(backup_path) if backup_path else "",
        "existing_rows": len(rows),
        "new_rows": len(new_rows),
        "final_rows": len(final_rows),
        "qualified_profiles": len(filtered_profiles),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
