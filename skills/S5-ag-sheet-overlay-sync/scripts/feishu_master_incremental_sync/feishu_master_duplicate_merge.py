#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests
from openpyxl import Workbook

AG_FEISHU_COPILOT_SCRIPTS = Path(
    "${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot/scripts"
)
if str(AG_FEISHU_COPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AG_FEISHU_COPILOT_SCRIPTS))

from runtime_config import require_app_credentials


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
        raise RuntimeError({"sheet_id": sheet_id, "sheet_title": sheet_title, "available": sheets})
    if len(matches) > 1:
        raise RuntimeError({"sheet_title": sheet_title, "matches": matches})
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
    backup_path = output_dir / f"feishu_master_duplicate_merge_backup_{timestamp}.xlsx"
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


def delete_row(spreadsheet_token: str, sheet_id: str, row_num: int) -> dict:
    token = get_tenant_access_token()
    response = requests.delete(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/dimension_range",
        headers=get_headers(token),
        json={
            "dimension": {
                "sheetId": sheet_id,
                "majorDimension": "ROWS",
                "startIndex": row_num - 1,
                "endIndex": row_num,
            }
        },
        timeout=30,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to delete row {row_num}: {payload}")
    payload["deleted_row"] = row_num
    return payload


def build_header_map(header: list[str]) -> dict[str, int]:
    return {normalize_text(cell): idx for idx, cell in enumerate(header) if normalize_text(cell)}


def row_snapshot(values: list[list], header: list[str], row_num: int) -> dict[str, str]:
    row = values[row_num - 1] if row_num - 1 < len(values) else []
    return {column: normalize_text(row[idx]) if idx < len(row) else "" for idx, column in enumerate(header)}


def verify_duplicate_groups(values: list[list], plans: list[dict]) -> dict:
    header = [normalize_text(cell) for cell in values[0]]
    idx_account = header.index("账号ID") if "账号ID" in header else None
    idx_url = header.index("账号链接") if "账号链接" in header else None
    live_rows = []
    for row_num, row in enumerate(values[1:], start=2):
        account = normalize_text(row[idx_account]) if idx_account is not None and idx_account < len(row) else ""
        url = normalize_text(row[idx_url]) if idx_url is not None and idx_url < len(row) else ""
        live_rows.append({"row": row_num, "账号ID": account, "账号链接": url})
    unresolved = []
    for plan in plans:
        keep_identity = plan["keep_identity"]
        keep_hits = [
            item for item in live_rows
            if (keep_identity.get("账号ID") and normalize_text(item["账号ID"]).lower() == normalize_text(keep_identity["账号ID"]).lower())
            or (keep_identity.get("账号链接") and normalize_text(item["账号链接"]).lower() == normalize_text(keep_identity["账号链接"]).lower())
        ]
        if len(keep_hits) != 1:
            unresolved.append({"keep_row": plan["keep_row"], "hits": keep_hits})
    return {"unresolved_keep_hits": unresolved}


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate Feishu master rows from a prepared merge plan")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = Path(args.plan_json).expanduser().resolve()
    plans = json.loads(plan_path.read_text(encoding="utf-8"))

    spreadsheet_token = extract_spreadsheet_token(args.target_url)
    sheet_id, sheet_title, row_count, column_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
    )
    values = fetch_values(spreadsheet_token, sheet_id, row_count, column_count)
    if not values:
        raise RuntimeError("Target sheet returned no values")
    header = [normalize_text(cell) for cell in values[0]]
    header_map = build_header_map(header)

    dry_run_payload = []
    for plan in plans:
        keep_before = row_snapshot(values, header, plan["keep_row"])
        drop_before = row_snapshot(values, header, plan["drop_row"])
        dry_run_payload.append(
            {
                "keep_row": plan["keep_row"],
                "drop_row": plan["drop_row"],
                "keep_before": keep_before,
                "drop_before": drop_before,
                "updates": plan["updates"],
                "preserved_conflicts": plan["preserved_conflicts"],
            }
        )

    backup_result = None
    write_results = []
    delete_results = []
    if args.mode == "apply":
        backup_result = export_backup_xlsx(spreadsheet_token, output_dir, values)
        for plan in plans:
            for update in plan["updates"]:
                write_results.append(
                    {
                        "keep_row": plan["keep_row"],
                        "drop_row": plan["drop_row"],
                        "column": update["column"],
                        "result": write_cell(
                            spreadsheet_token,
                            sheet_id,
                            plan["keep_row"],
                            header_map[update["column"]],
                            update["after"],
                        ),
                    }
                )
        for row_num in sorted([plan["drop_row"] for plan in plans], reverse=True):
            delete_results.append(delete_row(spreadsheet_token, sheet_id, row_num))

    refreshed_sheet_id, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=sheet_id,
    )
    refreshed_values = fetch_values(spreadsheet_token, refreshed_sheet_id, refreshed_row_count, refreshed_col_count)
    verification = verify_duplicate_groups(refreshed_values, plans)

    result = {
        "target_url": args.target_url,
        "sheet_id": sheet_id,
        "sheet_title": sheet_title,
        "mode": args.mode,
        "plan_json": str(plan_path),
        "group_count": len(plans),
        "update_count": sum(len(plan["updates"]) for plan in plans),
        "delete_count": len(plans) if args.mode == "apply" else 0,
        "backup_result": backup_result,
        "write_results_count": len(write_results),
        "delete_results_count": len(delete_results),
        "planned_groups": dry_run_payload,
        "verification": verification,
    }
    report_path = output_dir / "feishu_master_duplicate_merge_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
