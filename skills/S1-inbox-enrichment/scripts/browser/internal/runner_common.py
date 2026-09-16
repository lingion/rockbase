from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from browser_runtime import get_browser_context
from field_registry import CANONICAL_ALIASES, build_field_map
from path_resolver import build_report_dir, build_test_copy_path, resolve_csv_path
from router import infer_platform


DEFAULT_PROTECTED_FIELDS = {"notes"}
DEFAULT_FILL_ONLY_FIELDS = {"report_time"}
DEFAULT_ROW_TIMEOUT_SECONDS = 45

Extractor = Callable[..., Any]


def parse_row_numbers(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if "-" in raw:
        start, end = raw.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(x) for x in raw.split(",") if x.strip()]


def normalize_field_token(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        return ""
    lowered = "".join(raw.lower().split())
    if lowered in CANONICAL_ALIASES:
        return lowered
    for canonical, aliases in CANONICAL_ALIASES.items():
        options = [canonical, *aliases]
        if any("".join(option.lower().split()) == lowered for option in options):
            return canonical
    return raw


def parse_target_fields(raw_fields: str | None, defaults: list[str]) -> list[str]:
    fields = list(defaults)
    if raw_fields:
        for token in raw_fields.split(","):
            normalized = normalize_field_token(token)
            if normalized and normalized not in fields:
                fields.append(normalized)
    return fields


def ensure_backup(csv_path: Path) -> Path:
    project_root = csv_path.parents[2]
    backup_root = project_root / "Agency" / "list-bak" / datetime.now().strftime("%Y-%m-%d")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f"{csv_path.name}_bak_{datetime.now().strftime('%H%M%S')}.csv"
    shutil.copy2(csv_path, backup_path)
    return backup_path


def detect_header_row(raw_df: pd.DataFrame) -> int:
    for idx, row in raw_df.iterrows():
        values = [str(value).strip() for value in row.tolist()]
        if "提报时间" in values:
            return idx
    return 0


def load_csv_with_structure(csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, int, list[str]]:
    raw_df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False, header=None)
    header_row = detect_header_row(raw_df)
    headers = [str(value).strip() for value in raw_df.iloc[header_row].tolist()]
    body_df = raw_df.iloc[header_row + 1 :].copy().reset_index(names="raw_index")
    body_df.columns = ["raw_index"] + headers
    marker_col = body_df.iloc[:, 1].astype(str).str.strip()
    body_df = body_df[~marker_col.str.startswith("----- ")].copy()
    body_df = body_df[~body_df.apply(is_repeat_header_row, axis=1, headers=headers)].copy()
    body_df = body_df[body_df.apply(has_meaningful_value, axis=1, headers=headers)].copy()
    body_df = body_df.reset_index(drop=True)
    return raw_df, body_df, header_row, headers


def is_repeat_header_row(row: pd.Series, headers: list[str]) -> bool:
    values = [str(row[header]).strip() for header in headers]
    return values == headers


def has_meaningful_value(row: pd.Series, headers: list[str]) -> bool:
    for header in headers:
        if str(row[header]).strip():
            return True
    return False


def write_back_to_raw(raw_df: pd.DataFrame, body_df: pd.DataFrame, headers: list[str]) -> pd.DataFrame:
    written = raw_df.copy()
    for _, row in body_df.iterrows():
        raw_index = int(row["raw_index"])
        for col_idx, header in enumerate(headers):
            written.iat[raw_index, col_idx] = row[header]
    return written


def select_row_indices(df: pd.DataFrame, row_numbers: list[int]) -> list[int]:
    if not row_numbers:
        return list(range(len(df)))
    selected = []
    for row_no in row_numbers:
        idx = row_no - 2
        if 0 <= idx < len(df):
            selected.append(idx)
    return selected


def value_or_empty(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def apply_if_needed(
    df: pd.DataFrame,
    idx: int,
    header: str | None,
    value: str,
    field_name: str,
    changed_fields: list[str],
) -> None:
    if not header or not value:
        return
    current = value_or_empty(df.at[idx, header])
    if field_name in DEFAULT_PROTECTED_FIELDS and current:
        return
    if field_name in DEFAULT_FILL_ONLY_FIELDS and current:
        return
    if current == value:
        return
    df.at[idx, header] = value
    changed_fields.append(field_name)


def apply_404_note(df: pd.DataFrame, idx: int, header: str | None, changed_fields: list[str]) -> None:
    if not header:
        return
    current = value_or_empty(df.at[idx, header])
    if current == "404":
        return
    df.at[idx, header] = f"{current}; 404" if current else "404"
    changed_fields.append("notes")


def build_diff_report(before_df: pd.DataFrame, after_df: pd.DataFrame) -> dict[str, Any]:
    changed_rows = 0
    changed_cells = 0
    samples: list[dict[str, Any]] = []
    for idx in range(min(len(before_df), len(after_df))):
        row_changes = []
        for column in before_df.columns:
            before = value_or_empty(before_df.at[idx, column])
            after = value_or_empty(after_df.at[idx, column])
            if before != after:
                changed_cells += 1
                row_changes.append({"field": column, "before": before, "after": after})
        if row_changes:
            changed_rows += 1
            if len(samples) < 5:
                samples.append({"row_index": idx, "changes": row_changes[:6]})
    return {"changed_rows": changed_rows, "changed_cells": changed_cells, "samples": samples}


def write_checkpoint_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def flush_csv_write(
    *,
    csv_path: Path,
    raw_df: pd.DataFrame,
    df: pd.DataFrame,
    headers: list[str],
    backup_every: int,
    flush_count: int,
    backup_paths: list[str],
) -> tuple[int, str | None]:
    backup_path: str | None = None
    if backup_every > 0 and flush_count % backup_every == 0:
        backup_path = str(ensure_backup(csv_path))
        backup_paths.append(backup_path)
    written_raw_df = write_back_to_raw(raw_df, df, headers)
    written_raw_df.to_csv(csv_path, index=False, header=False, encoding="utf-8-sig")
    return flush_count, backup_path


async def run_enrichment(
    *,
    csv_path_raw: str,
    row_numbers_raw: str,
    target_fields_raw: str | None,
    write: bool,
    write_test_copy: bool,
    dry_run: bool,
    diff_report: bool,
    mode_name: str,
    default_fields: list[str],
    platform_extractors: dict[str, Extractor],
    write_every: int = 0,
    backup_every: int = 0,
) -> dict[str, Any]:
    if write and write_test_copy:
        raise ValueError("--write 和 --write-test-copy 不能同时使用")

    csv_path = resolve_csv_path(csv_path_raw)
    target_fields = parse_target_fields(target_fields_raw, default_fields)
    row_numbers = parse_row_numbers(row_numbers_raw)

    raw_df, df, header_row_index, headers = load_csv_with_structure(csv_path)
    field_map = build_field_map(headers)
    before_df = df.copy(deep=True)
    report_dir = build_report_dir(csv_path)
    row_indices = select_row_indices(df, row_numbers)

    missing_required = [name for name in ["profile_url"] if field_map.index_for(name) is None]
    if missing_required:
        raise RuntimeError(f"当前 CSV 缺少必要列: {missing_required}")

    backup_path: str | None = None
    backup_paths: list[str] = []
    test_copy_path: str | None = None
    results: list[dict[str, Any]] = []
    write_flushes = 0
    timestamp_stub = datetime.now().strftime("%H%M%S")
    checkpoint_path = report_dir / f"{mode_name}_checkpoint_{timestamp_stub}.json"

    checkpoint_payload: dict[str, Any] = {
        "mode": "dry-run",
        "runner": mode_name,
        "csv_path": str(csv_path),
        "rows": row_numbers if row_numbers else "auto",
        "target_fields": target_fields,
        "processed_count": 0,
        "write_every": write_every,
        "backup_every": backup_every,
        "write_flushes": 0,
        "backup_paths": backup_paths,
        "results": results,
    }
    write_checkpoint_json(checkpoint_path, checkpoint_payload)

    playwright = browser = context = page = None
    try:
        playwright, browser, context = await get_browser_context()
        page = await context.new_page()

        for idx in row_indices:
            row_no = idx + 2
            row = df.iloc[idx]
            profile_url = value_or_empty(row.get(field_map.header_for("profile_url")))
            platform_value = value_or_empty(row.get(field_map.header_for("platform")))
            platform = infer_platform(platform_value, profile_url)
            if not profile_url:
                results.append({"row": row_no, "status": "skipped", "reason": "missing_profile_url"})
                continue

            extractor = platform_extractors.get(platform)
            if extractor is None:
                results.append({"row": row_no, "status": "skipped", "reason": f"unsupported_platform:{platform}"})
                continue

            try:
                extracted = await extractor(page, profile_url)
            except Exception as exc:
                results.append(
                    {"row": row_no, "status": "error", "platform": platform, "profile_url": profile_url, "error": str(exc)}
                )
                continue

            changed_fields: list[str] = []
            if extracted.get("is_404") == "yes":
                apply_404_note(df, idx, field_map.header_for("notes"), changed_fields)

            for field_name in target_fields:
                header_name = field_map.header_for(field_name)
                if field_name == "contact":
                    apply_if_needed(df, idx, header_name, extracted.get("visible_email", ""), field_name, changed_fields)
                elif field_name == "contact_note":
                    apply_if_needed(df, idx, header_name, extracted.get("contact_note", ""), field_name, changed_fields)
                else:
                    apply_if_needed(df, idx, header_name, extracted.get(field_name, ""), field_name, changed_fields)

            results.append(
                {
                    "row": row_no,
                    "status": "ok" if changed_fields else "no_change",
                    "platform": platform,
                    "profile_url": profile_url,
                    "changed_fields": changed_fields,
                    "extracted": {
                        field: (
                            extracted.get("visible_email", "")
                            if field == "contact"
                            else extracted.get("contact_note", "")
                            if field == "contact_note"
                            else extracted.get(field, "")
                        )
                        for field in target_fields
                    },
                }
            )

            checkpoint_payload["processed_count"] = len(results)
            write_checkpoint_json(checkpoint_path, checkpoint_payload)

            if write and write_every > 0 and len(results) % write_every == 0:
                write_flushes += 1
                _, maybe_backup = flush_csv_write(
                    csv_path=csv_path,
                    raw_df=raw_df,
                    df=df,
                    headers=headers,
                    backup_every=backup_every,
                    flush_count=len(results),
                    backup_paths=backup_paths,
                )
                if maybe_backup:
                    backup_path = maybe_backup
                checkpoint_payload["write_flushes"] = write_flushes
                checkpoint_payload["mode"] = "write"
                write_checkpoint_json(checkpoint_path, checkpoint_payload)
    finally:
        if playwright is not None:
            await playwright.stop()

    written_raw_df = write_back_to_raw(raw_df, df, headers)
    report: dict[str, Any] = {
        "mode": "dry-run",
        "runner": mode_name,
        "csv_path": str(csv_path),
        "rows": row_numbers if row_numbers else "auto",
        "target_fields": target_fields,
        "results": results,
        "checkpoint_path": str(checkpoint_path),
    }

    if write_test_copy:
        test_path = build_test_copy_path(csv_path)
        written_raw_df.to_csv(test_path, index=False, header=False, encoding="utf-8-sig")
        test_copy_path = str(test_path)
        report["mode"] = "test-copy"
        report["test_copy_path"] = test_copy_path
    elif write:
        if write_every <= 0:
            if backup_every > 0:
                backup_path = str(ensure_backup(csv_path))
                backup_paths.append(backup_path)
            written_raw_df.to_csv(csv_path, index=False, header=False, encoding="utf-8-sig")
            write_flushes = 1
        else:
            needs_final_flush = len(results) % write_every != 0 or len(results) == 0
            if needs_final_flush:
                write_flushes += 1
                _, maybe_backup = flush_csv_write(
                    csv_path=csv_path,
                    raw_df=raw_df,
                    df=df,
                    headers=headers,
                    backup_every=backup_every,
                    flush_count=len(results),
                    backup_paths=backup_paths,
                )
                if maybe_backup:
                    backup_path = maybe_backup
        report["mode"] = "write"
        report["backup_path"] = backup_path
        report["backup_paths"] = backup_paths
        report["write_flushes"] = write_flushes

    if diff_report or write or write_test_copy:
        report["diff"] = build_diff_report(before_df, df)
        report["structure"] = {
            "header_row_index": header_row_index,
            "raw_rows": len(raw_df),
            "body_rows": len(df),
        }

    report_path = report_dir / f"{mode_name}_report_{datetime.now().strftime('%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
