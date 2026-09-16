#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


MASTER_HEADER_ALIASES = {
    "频道/作者名称": "频道名称",
    "频道名称 ": "频道名称",
}

SOURCE_HEADER_ALIASES = {
    "频道/作者名称": "频道名称",
}

DEFAULT_MATCH_KEYS = ("账号链接", "账号ID")
DEFAULT_PROTECTED_COLUMNS = ("备注",)
DEFAULT_FILL_ONLY_COLUMNS = ("提报时间",)


@dataclass
class TableData:
    path: Path
    raw: pd.DataFrame
    header_row_index: int
    columns: List[str]
    body: pd.DataFrame
    section_markers: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay a source influencer sheet onto a master sheet with dry-run support."
    )
    parser.add_argument("--source", required=True, help="Source CSV path.")
    parser.add_argument("--target", required=True, help="Target master CSV path.")
    parser.add_argument("--output", help="Output CSV path for write mode.")
    parser.add_argument("--write", action="store_true", help="Write changes to disk.")
    parser.add_argument(
        "--write-test-copy",
        action="store_true",
        help="Write to an auto-created test copy instead of the original target.",
    )
    parser.add_argument(
        "--test-output-dir",
        help="Directory used with --write-test-copy. Defaults to project_root/workbench/YYYY-MM-DD.",
    )
    parser.add_argument(
        "--backup-root",
        help="Backup root directory. Required when --write is used.",
    )
    parser.add_argument(
        "--source-date",
        default=datetime.now().strftime("%-m月%-d日"),
        help="Value used for 提报时间 when source lacks that column.",
    )
    parser.add_argument(
        "--match-keys",
        nargs="+",
        default=list(DEFAULT_MATCH_KEYS),
        help="Match key priority.",
    )
    parser.add_argument(
        "--protected-columns",
        nargs="*",
        default=list(DEFAULT_PROTECTED_COLUMNS),
        help="Columns never overwritten when target already has a value.",
    )
    parser.add_argument(
        "--fill-only-columns",
        nargs="*",
        default=list(DEFAULT_FILL_ONLY_COLUMNS),
        help="Columns only filled when target is empty.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="CSV encoding, defaults to utf-8-sig.",
    )
    parser.add_argument(
        "--diff-report",
        action="store_true",
        help="Print a structural diff summary between original and written output.",
    )
    return parser.parse_args()


def normalize_column_name(name: object, aliases: Dict[str, str]) -> str:
    text = "" if pd.isna(name) else str(name).strip()
    return aliases.get(text, text)


def project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "Agency").exists():
            return candidate
    return current.parents[2]


def workbench_day_dir() -> Path:
    day_dir = project_root() / "workbench" / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def detect_target_header_row(raw: pd.DataFrame) -> int:
    for idx in range(len(raw)):
        row = raw.iloc[idx].fillna("").astype(str).str.strip().tolist()
        if "提报时间" in row and "账号ID" in row:
            return idx
    return 0


def load_target(path: Path, encoding: str) -> TableData:
    raw = pd.read_csv(path, header=None, encoding=encoding)
    header_row_index = detect_target_header_row(raw)
    columns = [
        normalize_column_name(value, MASTER_HEADER_ALIASES)
        for value in raw.iloc[header_row_index].tolist()
    ]
    body = raw.iloc[header_row_index + 1 :].copy().reset_index(names="raw_index")
    body.columns = ["raw_index"] + columns
    section_markers = int(raw.iloc[:, 0].astype(str).str.startswith("----- ").sum())
    return TableData(
        path=path,
        raw=raw,
        header_row_index=header_row_index,
        columns=columns,
        body=body,
        section_markers=section_markers,
    )


def load_source(path: Path, encoding: str, source_date: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding=encoding)
    df.columns = [normalize_column_name(col, SOURCE_HEADER_ALIASES) for col in df.columns]
    if "提报时间" not in df.columns:
        df.insert(0, "提报时间", source_date)
    if "Unnamed: 0" in df.columns:
        marker = df["Unnamed: 0"].astype(str).str.strip().str.lower()
        df = df[~marker.str.startswith("part ")].copy()
    link_present = df["账号链接"].apply(normalize_url) if "账号链接" in df.columns else pd.Series(False, index=df.index)
    id_present = df["账号ID"].apply(normalize_account_id) if "账号ID" in df.columns else pd.Series(False, index=df.index)
    df = df[link_present.notna() | id_present.notna()].copy()
    df = df.reset_index(drop=True)
    return df


def normalize_value(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def normalize_platform(value: object) -> Optional[str]:
    text = normalize_value(value)
    if not text:
        return None
    lowered = text.lower()
    mapping = {
        "youtube": "youtube",
        "you tube": "youtube",
        "tiktok": "tiktok",
        "tik tok": "tiktok",
        "x": "x",
        "twitter": "x",
        "instagram": "instagram",
        "ig": "instagram",
    }
    return mapping.get(lowered, lowered)


def normalize_account_id(value: object) -> Optional[str]:
    text = normalize_value(value)
    if not text:
        return None
    return text.lstrip("@").strip().lower()


def normalize_url(value: object) -> Optional[str]:
    text = normalize_value(value)
    if not text:
        return None
    lowered = text.lower().strip()
    lowered = lowered.split("?", 1)[0].rstrip("/")
    lowered = lowered.replace("https://m.", "https://www.")
    if lowered.startswith("http://"):
        lowered = "https://" + lowered[len("http://") :]
    if lowered.startswith("https://youtube.com/"):
        lowered = lowered.replace("https://youtube.com/", "https://www.youtube.com/", 1)
    if lowered.startswith("https://tiktok.com/"):
        lowered = lowered.replace("https://tiktok.com/", "https://www.tiktok.com/", 1)
    if lowered.startswith("https://instagram.com/"):
        lowered = lowered.replace("https://instagram.com/", "https://www.instagram.com/", 1)
    return lowered


def row_match_value(row: pd.Series, key: str) -> Optional[str]:
    if key == "账号链接":
        return normalize_url(row.get(key))
    if key == "账号ID":
        return normalize_account_id(row.get(key))
    if key == "平台":
        return normalize_platform(row.get(key))
    return normalize_value(row.get(key))


def build_index(df: pd.DataFrame, key: str) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    for row_idx, row in df.iterrows():
        value = row_match_value(row, key)
        if value:
            index.setdefault(value, []).append(row_idx)
    return index


def ensure_columns(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result


def should_write_value(
    column: str,
    source_value: object,
    target_value: object,
    protected_columns: Iterable[str],
    fill_only_columns: Iterable[str],
) -> bool:
    if pd.isna(source_value):
        return False
    if column in protected_columns and normalize_value(target_value):
        return False
    if column in fill_only_columns and normalize_value(target_value):
        return False
    if pd.isna(target_value):
        return True
    return str(source_value) != str(target_value)


def overlay(
    source_df: pd.DataFrame,
    target: TableData,
    match_keys: Sequence[str],
    protected_columns: Sequence[str],
    fill_only_columns: Sequence[str],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    source_df = ensure_columns(source_df, target.columns)
    working = target.body.copy()
    indexes = {key: build_index(working, key) for key in match_keys}

    common_columns = [col for col in source_df.columns if col in target.columns]
    source_only_columns = [col for col in source_df.columns if col not in target.columns]
    target_only_columns = [col for col in target.columns if col not in source_df.columns]

    matched_rows = 0
    changed_rows = 0
    appended_rows = 0
    unmatched_rows = 0
    duplicate_hits: List[Dict[str, object]] = []
    change_samples: List[Dict[str, object]] = []

    for _, source_row in source_df.iterrows():
        matched_target_idx = None
        matched_by = None
        for key in match_keys:
            match_value = row_match_value(source_row, key)
            if not match_value:
                continue
            candidates = indexes[key].get(match_value, [])
            if len(candidates) > 1:
                duplicate_hits.append({"key": key, "value": match_value, "count": len(candidates)})
            if candidates:
                matched_target_idx = candidates[0]
                matched_by = key
                break

        if matched_target_idx is None:
            unmatched_rows += 1
            continue

        matched_rows += 1
        row_changed = False
        row_changes: List[str] = []
        for column in common_columns:
            source_value = source_row[column]
            target_value = working.at[matched_target_idx, column]
            if should_write_value(
                column, source_value, target_value, protected_columns, fill_only_columns
            ):
                working.at[matched_target_idx, column] = source_value
                row_changed = True
                row_changes.append(column)
        if row_changed:
            changed_rows += 1
            if len(change_samples) < 5:
                change_samples.append(
                    {
                        "match_by": matched_by,
                        "账号链接": source_row.get("账号链接"),
                        "账号ID": source_row.get("账号ID"),
                        "changed_columns": row_changes,
                    }
                )

    summary = {
        "source_rows": int(len(source_df)),
        "target_rows": int(len(target.body)),
        "common_columns": common_columns,
        "source_only_columns": source_only_columns,
        "target_only_columns": target_only_columns,
        "matched_rows": matched_rows,
        "changed_rows": changed_rows,
        "unmatched_rows": unmatched_rows,
        "appended_rows": appended_rows,
        "duplicate_hits": duplicate_hits,
        "change_samples": change_samples,
        "section_markers": target.section_markers,
    }
    return working, summary


def materialize_target(target: TableData, overlaid_body: pd.DataFrame) -> pd.DataFrame:
    raw = target.raw.copy()
    for _, row in overlaid_body.iterrows():
        raw_index = int(row["raw_index"])
        for col_idx, column in enumerate(target.columns):
            raw.iat[raw_index, col_idx] = row[column]
    return raw


def build_test_copy_path(target_path: Path, test_output_dir: Optional[str]) -> Path:
    base_dir = Path(test_output_dir).expanduser().resolve() if test_output_dir else workbench_day_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"{target_path.stem}__overlay_test__{timestamp}{target_path.suffix}"


def backup_target(target_path: Path, backup_root: Path) -> Path:
    timestamp = datetime.now().strftime("%H%M%S")
    day_dir = backup_root / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    backup_path = day_dir / f"{target_path.name}_bak_{timestamp}.csv"
    shutil.copy2(target_path, backup_path)
    return backup_path


def diff_report(original: pd.DataFrame, updated: pd.DataFrame, target: TableData) -> None:
    print("Diff report")
    print(f"- original_rows: {len(original)}")
    print(f"- updated_rows: {len(updated)}")
    print(f"- original_cols: {len(original.columns)}")
    print(f"- updated_cols: {len(updated.columns)}")
    marker_original = int(original.iloc[:, 0].astype(str).str.startswith('----- ').sum())
    marker_updated = int(updated.iloc[:, 0].astype(str).str.startswith('----- ').sum())
    print(f"- section_markers_before: {marker_original}")
    print(f"- section_markers_after: {marker_updated}")
    print(f"- header_row_index: {target.header_row_index}")
    header_before = original.iloc[target.header_row_index].fillna("").astype(str).tolist()
    header_after = updated.iloc[target.header_row_index].fillna("").astype(str).tolist()
    print(f"- header_changed: {header_before != header_after}")

    changed_cells = 0
    changed_rows = set()
    sample_changes: List[str] = []
    row_count = min(len(original), len(updated))
    col_count = min(len(original.columns), len(updated.columns))
    for row_idx in range(row_count):
        for col_idx in range(col_count):
            before = "" if pd.isna(original.iat[row_idx, col_idx]) else str(original.iat[row_idx, col_idx])
            after = "" if pd.isna(updated.iat[row_idx, col_idx]) else str(updated.iat[row_idx, col_idx])
            if before != after:
                changed_cells += 1
                changed_rows.add(row_idx)
                if len(sample_changes) < 8:
                    column_name = target.columns[col_idx] if row_idx > target.header_row_index and col_idx < len(target.columns) else f"col_{col_idx}"
                    sample_changes.append(
                        f"row={row_idx + 1} col={col_idx + 1} field={column_name} before={before!r} after={after!r}"
                    )
    print(f"- changed_rows: {len(changed_rows)}")
    print(f"- changed_cells: {changed_cells}")
    print("- sample_cell_changes:")
    if sample_changes:
        for item in sample_changes:
            print(f"  - {item}")
    else:
        print("  - []")


def print_summary(summary: Dict[str, object], match_keys: Sequence[str]) -> None:
    print("Overlay plan")
    print(f"- match_keys: {', '.join(match_keys)}")
    print(f"- source_rows: {summary['source_rows']}")
    print(f"- target_rows: {summary['target_rows']}")
    print(f"- section_markers: {summary['section_markers']}")
    print(f"- matched_rows: {summary['matched_rows']}")
    print(f"- changed_rows: {summary['changed_rows']}")
    print(f"- unmatched_rows: {summary['unmatched_rows']}")
    print(f"- appended_rows: {summary['appended_rows']}")
    print(f"- common_columns_count: {len(summary['common_columns'])}")
    print(f"- source_only_columns: {summary['source_only_columns']}")
    print(f"- target_only_columns: {summary['target_only_columns']}")
    duplicates = summary["duplicate_hits"]
    if duplicates:
        print("- duplicate_hits:")
        seen = set()
        for item in duplicates:
            token = (item["key"], item["value"])
            if token in seen:
                continue
            seen.add(token)
            print(f"  - {item['key']}={item['value']} count={item['count']}")
    else:
        print("- duplicate_hits: []")

    print("- change_samples:")
    for sample in summary["change_samples"]:
        print(
            f"  - match_by={sample['match_by']} 账号ID={sample['账号ID']} "
            f"账号链接={sample['账号链接']} changed={sample['changed_columns']}"
        )
    if not summary["change_samples"]:
        print("  - []")


def main() -> int:
    args = parse_args()
    source_path = Path(args.source).expanduser().resolve()
    target_path = Path(args.target).expanduser().resolve()
    target = load_target(target_path, args.encoding)
    source_df = load_source(source_path, args.encoding, args.source_date)
    overlaid_body, summary = overlay(
        source_df,
        target,
        args.match_keys,
        args.protected_columns,
        args.fill_only_columns,
    )
    print_summary(summary, args.match_keys)

    if not args.write and not args.write_test_copy:
        print("Dry run complete. No files were modified.")
        return 0

    raw = materialize_target(target, overlaid_body)

    if args.write_test_copy:
        output_path = build_test_copy_path(target_path, args.test_output_dir)
        shutil.copy2(target_path, output_path)
        raw.to_csv(output_path, index=False, header=False, encoding=args.encoding)
        print(f"Test copy created: {output_path}")
        if args.diff_report:
            diff_report(target.raw, raw, target)
        return 0

    if not args.output or not args.backup_root:
        raise SystemExit("--write requires --output and --backup-root")

    output_path = Path(args.output).expanduser().resolve()
    backup_path = backup_target(target_path, Path(args.backup_root).expanduser().resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_path, index=False, header=False, encoding=args.encoding)
    print(f"Backup created: {backup_path}")
    print(f"Wrote output: {output_path}")
    if args.diff_report:
        diff_report(target.raw, raw, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
