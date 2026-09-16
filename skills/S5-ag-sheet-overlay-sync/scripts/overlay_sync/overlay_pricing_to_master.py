#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit


PRICE_COLUMNS = ("原价", "rate（USD$)报价", "CPM", "利润")
SOURCE_NAME_ALIASES = {
    "平台博主": "频道/作者名称",
}


@dataclass
class SourceRecord:
    source_name: str
    row_number: int
    values: Dict[str, str]


@dataclass
class MatchDecision:
    source_name: str
    source_row_number: int
    match_by: str
    target_row_index: int
    target_row_number: int
    account_id: str
    author_name: str
    platform: str
    account_url: str
    changed_columns: List[str]
    values_to_write: Dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay pricing columns from multiple source sheets into a segmented master CSV."
    )
    parser.add_argument("--target", required=True, help="Target master CSV path.")
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        required=True,
        help="Source CSV path. Repeat for multiple source files.",
    )
    parser.add_argument("--write", action="store_true", help="Write changes to target.")
    parser.add_argument(
        "--backup-root",
        help="Backup root directory. Required with --write.",
    )
    parser.add_argument(
        "--report-dir",
        help="Directory for dry-run/write reports. Defaults to target sibling workbench date dir.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="CSV encoding. Defaults to utf-8-sig.",
    )
    return parser.parse_args()


def normalize_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def normalize_platform(value: object) -> str:
    text = normalize_value(value).lower()
    mapping = {
        "youtube": "youtube",
        "you tube": "youtube",
        "tiktok": "tiktok",
        "tik tok": "tiktok",
        "instagram": "instagram",
        "ig": "instagram",
        "x": "x",
        "twitter": "x",
    }
    return mapping.get(text, text)


def normalize_account_id(value: object) -> str:
    return normalize_value(value).lstrip("@").lower()


def normalize_url(value: object) -> str:
    text = normalize_value(value)
    if not text:
        return ""
    parts = urlsplit(text)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/").lower()
    if netloc in {"youtube.com", "www.youtube.com"}:
        netloc = "www.youtube.com"
    elif netloc in {"instagram.com", "www.instagram.com"}:
        netloc = "www.instagram.com"
    elif netloc in {"tiktok.com", "www.tiktok.com"}:
        netloc = "www.tiktok.com"
    elif netloc in {"twitter.com", "www.twitter.com", "x.com", "www.x.com"}:
        netloc = "x.com"
    return urlunsplit((scheme, netloc, path, "", ""))


def canonicalize_source_row(row: Dict[str, str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for key, value in row.items():
        canonical_key = SOURCE_NAME_ALIASES.get(key, key)
        result[canonical_key] = normalize_value(value)
    return result


def load_source_records(path: Path, encoding: str) -> List[SourceRecord]:
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        records: List[SourceRecord] = []
        for row_number, row in enumerate(reader, start=2):
            normalized = canonicalize_source_row(row)
            if not any(normalized.get(column, "") for column in PRICE_COLUMNS):
                continue
            if not (normalized.get("账号链接") or normalized.get("账号ID")):
                continue
            records.append(
                SourceRecord(
                    source_name=path.name,
                    row_number=row_number,
                    values=normalized,
                )
            )
    return records


def detect_header_rows(rows: Sequence[List[str]]) -> List[int]:
    indexes: List[int] = []
    for idx, row in enumerate(rows):
        stripped = [normalize_value(cell) for cell in row]
        if "账号ID" in stripped and "频道/作者名称" in stripped and "CPM" in stripped:
            indexes.append(idx)
    if not indexes:
        raise ValueError("Could not detect master header rows.")
    return indexes


def ensure_profit_column(rows: List[List[str]], header_rows: Sequence[int]) -> Tuple[List[List[str]], bool]:
    changed = False
    max_width = max(len(row) for row in rows)
    for row in rows:
        if len(row) < max_width:
            row.extend([""] * (max_width - len(row)))

    header = rows[header_rows[0]]
    if "利润" in header:
        return rows, changed

    cpm_index = header.index("CPM")
    insert_at = cpm_index + 1
    for row_index, row in enumerate(rows):
        value = "利润" if row_index in header_rows else ""
        row.insert(insert_at, value)
    changed = True
    return rows, changed


def build_target_indexes(rows: Sequence[List[str]], header_rows: Sequence[int]) -> Tuple[Dict[str, List[int]], Dict[str, List[int]], List[str]]:
    header = rows[header_rows[0]]
    by_url: Dict[str, List[int]] = defaultdict(list)
    by_platform_and_id: Dict[str, List[int]] = defaultdict(list)

    idx_platform = header.index("平台")
    idx_account_id = header.index("账号ID")
    idx_account_url = header.index("账号链接")

    header_row_set = set(header_rows)
    for row_index, row in enumerate(rows):
        if row_index in header_row_set:
            continue
        if not any(normalize_value(cell) for cell in row):
            continue
        if row and normalize_value(row[0]).startswith("----- "):
            continue
        url = normalize_url(row[idx_account_url] if idx_account_url < len(row) else "")
        account_id = normalize_account_id(row[idx_account_id] if idx_account_id < len(row) else "")
        platform = normalize_platform(row[idx_platform] if idx_platform < len(row) else "")
        if url:
            by_url[url].append(row_index)
        if platform and account_id:
            by_platform_and_id[f"{platform}::{account_id}"].append(row_index)

    return by_url, by_platform_and_id, header


def choose_target_row(
    record: SourceRecord,
    by_url: Dict[str, List[int]],
    by_platform_and_id: Dict[str, List[int]],
) -> Tuple[Optional[int], Optional[str], Optional[int]]:
    url = normalize_url(record.values.get("账号链接"))
    if url:
        candidates = by_url.get(url, [])
        if len(candidates) == 1:
            return candidates[0], "账号链接", None
        if len(candidates) > 1:
            return None, "账号链接", len(candidates)

    platform = normalize_platform(record.values.get("平台"))
    account_id = normalize_account_id(record.values.get("账号ID"))
    if platform and account_id:
        key = f"{platform}::{account_id}"
        candidates = by_platform_and_id.get(key, [])
        if len(candidates) == 1:
            return candidates[0], "平台+账号ID", None
        if len(candidates) > 1:
            return None, "平台+账号ID", len(candidates)

    return None, None, None


def build_price_overlay_plan(
    rows: List[List[str]],
    header_rows: Sequence[int],
    records: Sequence[SourceRecord],
) -> Tuple[List[MatchDecision], Dict[str, object]]:
    by_url, by_platform_and_id, header = build_target_indexes(rows, header_rows)
    col_indexes = {name: header.index(name) for name in header}
    idx_platform = col_indexes["平台"]
    idx_account_id = col_indexes["账号ID"]
    idx_author_name = col_indexes["频道/作者名称"]
    idx_account_url = col_indexes["账号链接"]

    decisions: List[MatchDecision] = []
    unmatched: List[Dict[str, object]] = []
    ambiguous: List[Dict[str, object]] = []
    duplicate_decisions: List[Dict[str, object]] = []
    claimed_targets: Dict[int, MatchDecision] = {}

    for record in records:
        target_index, matched_by, ambiguous_count = choose_target_row(record, by_url, by_platform_and_id)
        if ambiguous_count:
            ambiguous.append(
                {
                    "source": record.source_name,
                    "source_row_number": record.row_number,
                    "match_by": matched_by,
                    "candidate_count": ambiguous_count,
                    "账号ID": record.values.get("账号ID", ""),
                    "账号链接": record.values.get("账号链接", ""),
                }
            )
            continue
        if target_index is None or matched_by is None:
            unmatched.append(
                {
                    "source": record.source_name,
                    "source_row_number": record.row_number,
                    "账号ID": record.values.get("账号ID", ""),
                    "账号链接": record.values.get("账号链接", ""),
                }
            )
            continue

        changed_columns: List[str] = []
        values_to_write: Dict[str, str] = {}
        target_row = rows[target_index]
        for column in PRICE_COLUMNS:
            incoming = record.values.get(column, "")
            if not incoming:
                continue
            current = normalize_value(target_row[col_indexes[column]] if col_indexes[column] < len(target_row) else "")
            if incoming != current:
                changed_columns.append(column)
                values_to_write[column] = incoming

        if not changed_columns:
            continue

        decision = MatchDecision(
            source_name=record.source_name,
            source_row_number=record.row_number,
            match_by=matched_by,
            target_row_index=target_index,
            target_row_number=target_index + 1,
            account_id=normalize_value(target_row[idx_account_id]),
            author_name=normalize_value(target_row[idx_author_name]),
            platform=normalize_value(target_row[idx_platform]),
            account_url=normalize_value(target_row[idx_account_url]),
            changed_columns=changed_columns,
            values_to_write=values_to_write,
        )
        existing = claimed_targets.get(target_index)
        if existing is not None:
            duplicate_decisions.append(
                {
                    "target_row_number": decision.target_row_number,
                    "existing_source": existing.source_name,
                    "existing_source_row_number": existing.source_row_number,
                    "incoming_source": decision.source_name,
                    "incoming_source_row_number": decision.source_row_number,
                }
            )
            continue
        claimed_targets[target_index] = decision
        decisions.append(decision)

    source_breakdown: Dict[str, int] = defaultdict(int)
    match_by_breakdown: Dict[str, int] = defaultdict(int)
    column_change_breakdown: Dict[str, int] = defaultdict(int)
    for decision in decisions:
        source_breakdown[decision.source_name] += 1
        match_by_breakdown[decision.match_by] += 1
        for column in decision.changed_columns:
            column_change_breakdown[column] += 1

    summary = {
        "source_rows_with_pricing": len(records),
        "matched_and_changed_rows": len(decisions),
        "unmatched_rows": len(unmatched),
        "ambiguous_rows": len(ambiguous),
        "duplicate_source_conflicts": len(duplicate_decisions),
        "source_breakdown": dict(source_breakdown),
        "match_by_breakdown": dict(match_by_breakdown),
        "column_change_breakdown": dict(column_change_breakdown),
        "unmatched_samples": unmatched[:10],
        "ambiguous_samples": ambiguous[:10],
        "conflict_samples": duplicate_decisions[:10],
        "change_samples": [
            {
                "source": item.source_name,
                "source_row_number": item.source_row_number,
                "target_row_number": item.target_row_number,
                "账号ID": item.account_id,
                "changed_columns": item.changed_columns,
            }
            for item in decisions[:12]
        ],
    }
    return decisions, summary


def apply_decisions(rows: List[List[str]], header_rows: Sequence[int], decisions: Iterable[MatchDecision]) -> List[List[str]]:
    updated = [row[:] for row in rows]
    header = updated[header_rows[0]]
    col_indexes = {name: header.index(name) for name in header}
    for decision in decisions:
        row = updated[decision.target_row_index]
        for column, value in decision.values_to_write.items():
            row[col_indexes[column]] = value
    return updated


def build_report(
    target_path: Path,
    source_paths: Sequence[Path],
    profit_column_added: bool,
    header_rows: Sequence[int],
    decisions: Sequence[MatchDecision],
    summary: Dict[str, object],
    mode: str,
    backup_path: Optional[Path] = None,
) -> Dict[str, object]:
    return {
        "target_path": str(target_path),
        "source_paths": [str(path) for path in source_paths],
        "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profit_column_added": profit_column_added,
        "header_rows": [row + 1 for row in header_rows],
        "summary": summary,
        "decisions": [
            {
                "source_name": item.source_name,
                "source_row_number": item.source_row_number,
                "match_by": item.match_by,
                "target_row_number": item.target_row_number,
                "账号ID": item.account_id,
                "频道/作者名称": item.author_name,
                "平台": item.platform,
                "账号链接": item.account_url,
                "changed_columns": item.changed_columns,
                "values_to_write": item.values_to_write,
            }
            for item in decisions
        ],
        "backup_path": str(backup_path) if backup_path else None,
    }


def write_reports(report_dir: Path, report: Dict[str, object]) -> Tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "rockbase_pricing_overlay_dry_run.json"
    md_path = report_dir / "rockbase_pricing_overlay_dry_run.md"
    if report["mode"] == "write":
        json_path = report_dir / "rockbase_pricing_overlay_write.json"
        md_path = report_dir / "rockbase_pricing_overlay_write.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    md_lines = [
        "# Rockbase 价格覆盖报告",
        "",
        f"- 模式：`{report['mode']}`",
        f"- 目标表：`{report['target_path']}`",
        f"- 源表数：`{len(report['source_paths'])}`",
        f"- 利润列新增：`{'yes' if report['profit_column_added'] else 'no'}`",
        f"- Master 表头行：`{', '.join(str(x) for x in report['header_rows'])}`",
        f"- 源表价格记录数：`{summary['source_rows_with_pricing']}`",
        f"- 实际命中并改动：`{summary['matched_and_changed_rows']}`",
        f"- 未命中：`{summary['unmatched_rows']}`",
        f"- 歧义命中：`{summary['ambiguous_rows']}`",
        f"- 源表冲突：`{summary['duplicate_source_conflicts']}`",
        "",
        "## Source Breakdown",
        "",
    ]
    for key, value in summary["source_breakdown"].items():
        md_lines.append(f"- `{key}`: `{value}`")
    md_lines.extend(["", "## Column Changes", ""])
    for key, value in summary["column_change_breakdown"].items():
        md_lines.append(f"- `{key}`: `{value}`")
    md_lines.extend(["", "## Sample Changes", ""])
    for item in summary["change_samples"]:
        md_lines.append(
            f"- target_row={item['target_row_number']} source={item['source']}#{item['source_row_number']} "
            f"账号ID={item['账号ID']} changed={item['changed_columns']}"
        )
    if not summary["change_samples"]:
        md_lines.append("- []")
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def backup_target(target_path: Path, backup_root: Path) -> Path:
    day_dir = backup_root / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    backup_path = day_dir / f"{target_path.name}_bak_{datetime.now().strftime('%H%M%S')}.csv"
    shutil.copy2(target_path, backup_path)
    return backup_path


def main() -> int:
    args = parse_args()
    target_path = Path(args.target).expanduser().resolve()
    source_paths = [Path(value).expanduser().resolve() for value in args.sources]
    report_dir = (
        Path(args.report_dir).expanduser().resolve()
        if args.report_dir
        else target_path.parent.parent / "workbench" / datetime.now().strftime("%Y-%m-%d")
    )

    source_records: List[SourceRecord] = []
    for source_path in source_paths:
        source_records.extend(load_source_records(source_path, args.encoding))

    with target_path.open("r", encoding=args.encoding, newline="") as handle:
        target_rows = list(csv.reader(handle))

    header_rows = detect_header_rows(target_rows)
    target_rows, profit_column_added = ensure_profit_column(target_rows, header_rows)
    decisions, summary = build_price_overlay_plan(target_rows, header_rows, source_records)

    mode = "dry-run"
    backup_path: Optional[Path] = None
    if args.write:
        if not args.backup_root:
            raise SystemExit("--write requires --backup-root")
        backup_path = backup_target(target_path, Path(args.backup_root).expanduser().resolve())
        updated_rows = apply_decisions(target_rows, header_rows, decisions)
        with target_path.open("w", encoding=args.encoding, newline="") as handle:
            csv.writer(handle).writerows(updated_rows)
        mode = "write"

    report = build_report(
        target_path=target_path,
        source_paths=source_paths,
        profit_column_added=profit_column_added,
        header_rows=header_rows,
        decisions=decisions,
        summary=summary,
        mode=mode,
        backup_path=backup_path,
    )
    json_path, md_path = write_reports(report_dir, report)

    print("Pricing overlay plan")
    print(f"- mode: {mode}")
    print(f"- target: {target_path}")
    print(f"- profit_column_added: {'yes' if profit_column_added else 'no'}")
    print(f"- source_rows_with_pricing: {summary['source_rows_with_pricing']}")
    print(f"- matched_and_changed_rows: {summary['matched_and_changed_rows']}")
    print(f"- unmatched_rows: {summary['unmatched_rows']}")
    print(f"- ambiguous_rows: {summary['ambiguous_rows']}")
    print(f"- duplicate_source_conflicts: {summary['duplicate_source_conflicts']}")
    print(f"- report_json: {json_path}")
    print(f"- report_md: {md_path}")
    if backup_path:
        print(f"- backup_path: {backup_path}")
    if mode == "dry-run":
        print("Dry run complete. No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
