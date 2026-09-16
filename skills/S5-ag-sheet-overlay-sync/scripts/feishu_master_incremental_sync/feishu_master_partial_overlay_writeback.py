#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests
from openpyxl import Workbook

AG_FEISHU_COPILOT_SCRIPTS = Path(
    "${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot/scripts"
)
if str(AG_FEISHU_COPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AG_FEISHU_COPILOT_SCRIPTS))

from runtime_config import require_app_credentials


DEFAULT_MATCH_KEYS = ("账号链接", "账号ID")
DEFAULT_WRITE_COLUMNS = ("原始报价信息", "联系方式", "联系方式备注", "DM 发送状态")
DM_STATUS_COLUMNS = {"DM 发送状态", "DM二次发送状态"}


def normalize_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("link") or ""
                if text:
                    parts.append(str(text).strip())
            elif item is not None:
                parts.append(str(item).strip())
        return " | ".join([p for p in parts if p])
    return str(value).strip()


def normalize_key(value) -> str:
    return re.sub(r"\s+", "", normalize_text(value).strip().lower())


def normalize_account_id(value) -> str:
    return normalize_key(value).lstrip("@")


def normalize_url(value) -> str:
    text = normalize_text(value).lower().strip()
    if not text:
        return ""
    text = text.split("?", 1)[0].rstrip("/")
    text = text.replace("https://m.", "https://www.")
    if text.startswith("http://"):
        text = "https://" + text[len("http://") :]
    if text.startswith("https://youtube.com/"):
        text = text.replace("https://youtube.com/", "https://www.youtube.com/", 1)
    if text.startswith("https://tiktok.com/"):
        text = text.replace("https://tiktok.com/", "https://www.tiktok.com/", 1)
    if text.startswith("https://instagram.com/"):
        text = text.replace("https://instagram.com/", "https://www.instagram.com/", 1)
    if text.startswith("https://x.com/") or text.startswith("https://www.x.com/"):
        text = text.replace("https://www.x.com/", "https://x.com/", 1)
    return text


def canonical_dm_sent_status(value) -> str:
    raw = normalize_text(value)
    if not raw:
        return ""
    compact = re.sub(r"\s+", "", raw).lower()
    if compact == "y":
        return "Y"
    if compact in {"dm未开通", "dmnotopen", "dmclosed"}:
        return "DM 未开通"
    return raw


def normalize_source_cell(column: str, value) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if column in DM_STATUS_COLUMNS:
        return canonical_dm_sent_status(text)
    return text


def semantic_compare_key(column: str, value) -> str:
    text = normalize_source_cell(column, value)
    if not text:
        return ""
    if column in {"联系方式", "联系方式备注", "原始报价信息"}:
        parts = [
            re.sub(r"\s+", " ", part).strip()
            for part in re.split(r"\s*(?:\||\n|\r\n)\s*", text)
            if re.sub(r"\s+", " ", part).strip()
        ]
        return " || ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def extract_spreadsheet_token(url: str) -> str:
    match = re.search(r"/sheets/([A-Za-z0-9]+)", url)
    if not match:
        raise ValueError(f"Unable to extract spreadsheet token from URL: {url}")
    return match.group(1)


def get_tenant_access_token() -> str:
    config = require_app_credentials()
    response = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": config.feishu_app_id, "app_secret": config.feishu_app_secret},
        timeout=30,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to get tenant access token: {payload}")
    token = payload.get("tenant_access_token", "")
    if not token:
        raise RuntimeError("Tenant access token missing in response")
    return token


def get_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def col_idx_to_letter(idx: int) -> str:
    letter = ""
    while idx >= 0:
        letter = chr(idx % 26 + ord("A")) + letter
        idx = idx // 26 - 1
    return letter


def fetch_sheet_metas(spreadsheet_token: str) -> list[dict]:
    token = get_tenant_access_token()
    response = requests.get(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo",
        headers=get_headers(token),
        timeout=30,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to fetch sheet meta: {payload}")
    return payload["data"]["sheets"]


def select_sheet_meta(spreadsheet_token: str, sheet_id: str = "", sheet_title: str = "") -> tuple[str, str, int, int]:
    sheets = fetch_sheet_metas(spreadsheet_token)
    if sheet_id:
        matches = [sheet for sheet in sheets if sheet.get("sheetId") == sheet_id]
    elif sheet_title:
        matches = [sheet for sheet in sheets if normalize_text(sheet.get("title")) == sheet_title]
    else:
        matches = sheets[:1]

    if not matches:
        available = [
            {"sheet_id": sheet.get("sheetId"), "title": sheet.get("title")}
            for sheet in sheets
        ]
        raise RuntimeError(
            "Unable to select target sheet. "
            f"Requested sheet_id={sheet_id!r}, sheet_title={sheet_title!r}. "
            f"Available sheets: {available}"
        )
    if len(matches) > 1:
        available = [
            {"sheet_id": sheet.get("sheetId"), "title": sheet.get("title")}
            for sheet in matches
        ]
        raise RuntimeError(
            "Ambiguous target sheet selection. "
            f"Requested sheet_title={sheet_title!r}. Matches: {available}"
        )

    sheet = matches[0]
    return (
        sheet["sheetId"],
        normalize_text(sheet.get("title")),
        int(sheet.get("rowCount", 0)),
        int(sheet.get("columnCount", 0)),
    )


def fetch_values(spreadsheet_token: str, sheet_id: str, row_count: int, column_count: int) -> list[list]:
    token = get_tenant_access_token()
    end_col = col_idx_to_letter(column_count - 1)
    target_range = f"{sheet_id}!A1:{end_col}{max(row_count, 1)}"
    response = requests.get(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{target_range}",
        headers=get_headers(token),
        timeout=60,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to fetch values: {payload}")
    return payload["data"]["valueRange"].get("values", [])


def export_backup_xlsx(spreadsheet_token: str, output_dir: Path, values: list[list]) -> dict:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = output_dir / f"feishu_master_partial_overlay_backup_{timestamp}.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Master"
    max_cols = max((len(row) for row in values), default=0)
    for row in values:
        padded = row + [""] * (max_cols - len(row))
        worksheet.append([normalize_text(cell) for cell in padded])
    workbook.save(backup_path)
    if not backup_path.exists() or backup_path.stat().st_size <= 0:
        raise RuntimeError(f"Backup export failed or produced empty file: {backup_path}")
    return {
        "spreadsheet_token": spreadsheet_token,
        "local_backup_path": str(backup_path),
        "local_backup_size": backup_path.stat().st_size,
        "format": "xlsx",
        "method": "openapi-read-to-xlsx",
    }


def write_cell(spreadsheet_token: str, sheet_id: str, row_num: int, col_idx: int, value: str) -> dict:
    token = get_tenant_access_token()
    col_letter = col_idx_to_letter(col_idx)
    target_range = f"{sheet_id}!{col_letter}{row_num}:{col_letter}{row_num}"
    response = requests.post(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
        headers=get_headers(token),
        json={"valueRanges": [{"range": target_range, "values": [[value]]}]},
        timeout=30,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to write cell {target_range}: {payload}")
    return payload


def load_source_rows(source_csv: Path) -> list[dict]:
    df = pd.read_csv(source_csv, encoding="utf-8-sig").fillna("")
    records = df.to_dict(orient="records")
    usable = []
    for row in records:
        if normalize_url(row.get("账号链接", "")) or normalize_account_id(row.get("账号ID", "")):
            usable.append(row)
    return usable


def build_header_map(header: list) -> dict[str, int]:
    mapping = {}
    for idx, cell in enumerate(header):
        name = normalize_text(cell)
        if name and name not in mapping:
            mapping[name] = idx
    return mapping


def build_row_indexes(values: list[list], header_map: dict[str, int]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    url_idx = header_map.get("账号链接")
    account_idx = header_map.get("账号ID")
    by_url: dict[str, list[int]] = {}
    by_account: dict[str, list[int]] = {}
    for row_num, row in enumerate(values[1:], start=2):
        if url_idx is not None and url_idx < len(row):
            url = normalize_url(row[url_idx])
            if url:
                by_url.setdefault(url, []).append(row_num)
        if account_idx is not None and account_idx < len(row):
            account = normalize_account_id(row[account_idx])
            if account:
                by_account.setdefault(account, []).append(row_num)
    return by_url, by_account


def resolve_target_row(
    source_row: dict, by_url: dict[str, list[int]], by_account: dict[str, list[int]]
) -> Tuple[Optional[int], Optional[str], list[dict]]:
    duplicate_hits = []
    source_url = normalize_url(source_row.get("账号链接", ""))
    source_account = normalize_account_id(source_row.get("账号ID", ""))
    if source_url:
        hits = by_url.get(source_url, [])
        if len(hits) == 1:
            return hits[0], "账号链接", duplicate_hits
        if len(hits) > 1:
            duplicate_hits.append({"match_by": "账号链接", "match_value": source_url, "count": len(hits), "rows": hits})
    if source_account:
        hits = by_account.get(source_account, [])
        if len(hits) == 1:
            return hits[0], "账号ID", duplicate_hits
        if len(hits) > 1:
            duplicate_hits.append({"match_by": "账号ID", "match_value": source_account, "count": len(hits), "rows": hits})
    return None, None, duplicate_hits


def stage_changes(values: list[list], source_rows: list[dict], write_columns: list[str]) -> dict:
    header = [normalize_text(cell) for cell in values[0]]
    header_map = build_header_map(header)
    missing_columns = [column for column in write_columns if column not in header_map]
    if missing_columns:
        raise RuntimeError(f"Target sheet missing required columns: {missing_columns}")
    if "账号链接" not in header_map or "账号ID" not in header_map:
        raise RuntimeError("Target sheet must include 账号链接 and 账号ID for matching")

    by_url, by_account = build_row_indexes(values, header_map)
    planned_changes = []
    unmatched_rows = []
    ambiguous_rows = []
    matched_rows = 0
    changed_rows = 0

    for source_row in source_rows:
        row_num, matched_by, duplicate_hits = resolve_target_row(source_row, by_url, by_account)
        row_label = {
            "账号ID": normalize_text(source_row.get("账号ID", "")),
            "账号链接": normalize_text(source_row.get("账号链接", "")),
            "频道/作者名称": normalize_text(source_row.get("频道/作者名称", "")),
        }
        if duplicate_hits and row_num is None:
            ambiguous_rows.append({**row_label, "duplicate_hits": duplicate_hits})
            continue
        if row_num is None:
            unmatched_rows.append(row_label)
            continue

        matched_rows += 1
        row = values[row_num - 1]
        row_changes = []
        for column in write_columns:
            source_value = normalize_source_cell(column, source_row.get(column, ""))
            if not source_value:
                continue
            target_idx = header_map[column]
            target_value = normalize_source_cell(column, row[target_idx] if target_idx < len(row) else "")
            if semantic_compare_key(column, source_value) == semantic_compare_key(column, target_value):
                continue
            row_changes.append(
                {
                    "row": row_num,
                    "column": column,
                    "column_index": target_idx,
                    "before": target_value,
                    "after": source_value,
                }
            )
        if row_changes:
            changed_rows += 1
            planned_changes.append(
                {
                    **row_label,
                    "row": row_num,
                    "match_by": matched_by,
                    "changes": row_changes,
                }
            )

    return {
        "header": header,
        "header_map": header_map,
        "planned_changes": planned_changes,
        "matched_rows": matched_rows,
        "changed_rows": changed_rows,
        "unmatched_rows": unmatched_rows,
        "ambiguous_rows": ambiguous_rows,
        "source_rows": len(source_rows),
    }


def write_preview_csv(path: Path, planned_changes: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "账号ID", "账号链接", "频道/作者名称", "match_by", "column", "before", "after"])
        for item in planned_changes:
            for change in item["changes"]:
                writer.writerow(
                    [
                        item["row"],
                        item["账号ID"],
                        item["账号链接"],
                        item["频道/作者名称"],
                        item["match_by"],
                        change["column"],
                        change["before"],
                        change["after"],
                    ]
                )


def apply_changes(spreadsheet_token: str, sheet_id: str, planned_changes: list[dict]) -> list[dict]:
    results = []
    for item in planned_changes:
        for change in item["changes"]:
            result = write_cell(
                spreadsheet_token,
                sheet_id,
                change["row"],
                change["column_index"],
                change["after"],
            )
            results.append(
                {
                    "row": change["row"],
                    "column": change["column"],
                    "result": result,
                }
            )
    return results


def verify_applied_changes(refreshed_values: list[list], header_map: dict[str, int], planned_changes: list[dict]) -> list[dict]:
    verification = []
    for item in planned_changes[:20]:
        row_num = item["row"]
        row = refreshed_values[row_num - 1] if row_num - 1 < len(refreshed_values) else []
        snapshot = {
            "row": row_num,
            "账号ID": item["账号ID"],
            "账号链接": item["账号链接"],
            "频道/作者名称": item["频道/作者名称"],
        }
        for change in item["changes"]:
            idx = header_map[change["column"]]
            snapshot[change["column"]] = normalize_text(row[idx]) if idx < len(row) else ""
        verification.append(snapshot)
    return verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Write selected local CSV columns back to existing Feishu rows")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--write-columns",
        nargs="+",
        default=list(DEFAULT_WRITE_COLUMNS),
        help="Selected columns to write back. Defaults to 原始报价信息 联系方式 联系方式备注 DM 发送状态",
    )
    args = parser.parse_args()

    source_csv = Path(args.source_csv).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    spreadsheet_token = extract_spreadsheet_token(args.target_url)
    sheet_id, sheet_title, row_count, column_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
    )
    values = fetch_values(spreadsheet_token, sheet_id, row_count, column_count)
    if not values:
        raise RuntimeError("Target sheet returned no values")

    source_rows = load_source_rows(source_csv)
    staged = stage_changes(values, source_rows, args.write_columns)

    preview_csv = output_dir / "feishu_master_partial_overlay_preview.csv"
    preview_json = output_dir / "feishu_master_partial_overlay_preview.json"
    audit_json = output_dir / "feishu_master_partial_overlay_audit.json"
    write_preview_csv(preview_csv, staged["planned_changes"])
    preview_json.write_text(
        json.dumps(
            {
                "source_csv": str(source_csv),
                "target_url": args.target_url,
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "mode": args.mode,
                "write_columns": args.write_columns,
                "source_rows": staged["source_rows"],
                "matched_rows": staged["matched_rows"],
                "changed_rows": staged["changed_rows"],
                "unmatched_count": len(staged["unmatched_rows"]),
                "ambiguous_count": len(staged["ambiguous_rows"]),
                "planned_changes_preview": staged["planned_changes"][:20],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    backup_result = None
    write_results = []
    if args.mode == "apply" and staged["planned_changes"]:
        backup_result = export_backup_xlsx(spreadsheet_token, output_dir, values)
        write_results = apply_changes(spreadsheet_token, sheet_id, staged["planned_changes"])

    refreshed_values = values
    if args.mode == "apply":
        _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(spreadsheet_token, sheet_id=sheet_id)
        refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count)
    verification = verify_applied_changes(refreshed_values, staged["header_map"], staged["planned_changes"])

    audit = {
        "source_csv": str(source_csv),
        "target_url": args.target_url,
        "sheet_id": sheet_id,
        "sheet_title": sheet_title,
        "mode": args.mode,
        "write_columns": args.write_columns,
        "source_rows": staged["source_rows"],
        "matched_rows": staged["matched_rows"],
        "changed_rows": staged["changed_rows"],
        "changed_cells": sum(len(item["changes"]) for item in staged["planned_changes"]),
        "unmatched_count": len(staged["unmatched_rows"]),
        "ambiguous_count": len(staged["ambiguous_rows"]),
        "backup_result": backup_result,
        "write_results_count": len(write_results),
        "planned_changes_preview": staged["planned_changes"][:20],
        "unmatched_examples": staged["unmatched_rows"][:20],
        "ambiguous_examples": staged["ambiguous_rows"][:20],
        "verification_sample": verification,
        "dm_sent_status_rule": {
            "accepted_as_Y": ["Y", "y", " Y "],
            "accepted_as_DM_未开通": ["DM未开通", "DM 未开通", "dm未开通"],
            "blank_source_behavior": "skip_write",
        },
    }
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
