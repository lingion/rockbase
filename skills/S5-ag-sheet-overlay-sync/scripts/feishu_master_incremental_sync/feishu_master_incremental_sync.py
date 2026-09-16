#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from openpyxl import Workbook

AG_FEISHU_COPILOT_SCRIPTS = Path(
    "${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot/scripts"
)
if str(AG_FEISHU_COPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AG_FEISHU_COPILOT_SCRIPTS))

from runtime_config import require_app_credentials


ACTIVE_FEISHU_OPENAPI_HOST = ""
TOKEN_CACHE = {"token": "", "host": "", "expires_at": 0.0}


def build_feishu_session() -> requests.Session:
    session = requests.Session()
    # Feishu OpenAPI often fails behind the user's local tunnel proxy.
    # Default to direct egress, but allow explicit opt-in when the caller knows
    # the current proxy route is healthy.
    session.trust_env = os.getenv("FEISHU_USE_ENV_PROXY", "").strip().lower() in {"1", "true", "yes"}
    return session


def feishu_request(method: str, url: str, *, timeout: int = 30, retries: int = 2, **kwargs):
    session = build_feishu_session()
    if "headers" in kwargs and kwargs["headers"] is None:
        kwargs.pop("headers")
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return session.request(method=method, url=url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            time.sleep(min(2, attempt + 1))
    raise last_exc  # pragma: no cover


def collect_proxy_env() -> dict[str, str]:
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy"]
    return {key: os.getenv(key, "") for key in keys if os.getenv(key)}


def get_openapi_host_candidates() -> list[str]:
    configured = normalize_text(os.getenv("FEISHU_OPENAPI_BASE", ""))
    candidates = []
    for host in [configured, "https://open.feishu.cn", "https://open.larksuite.com"]:
        if host and host not in candidates:
            candidates.append(host)
    return candidates


def get_active_openapi_host() -> str:
    return ACTIVE_FEISHU_OPENAPI_HOST or get_openapi_host_candidates()[0]


def build_openapi_url(path: str) -> str:
    return f"{get_active_openapi_host()}{path}"


def detect_lark_cli_auth_route() -> dict:
    executable = shutil.which("lark-cli")
    result = {
        "available": bool(executable),
        "path": executable or "",
        "identity": "",
        "token_status": "",
        "route": "tenant_env_only",
        "raw": None,
    }
    if not executable:
        return result

    try:
        completed = subprocess.run(
            [executable, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        result["raw"] = {"error": str(exc)}
        result["route"] = "tenant_env_only_cli_probe_failed"
        return result

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    payload = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"stdout": stdout, "stderr": stderr}
    elif stderr:
        payload = {"stderr": stderr}
    result["raw"] = payload

    if isinstance(payload, dict):
        identity = normalize_text(payload.get("identity", ""))
        token_status = normalize_text(payload.get("tokenStatus", ""))
        result["identity"] = identity
        result["token_status"] = token_status
        if identity == "user" and token_status == "valid":
            result["route"] = "lark_cli_user_available"
        elif identity:
            result["route"] = f"lark_cli_{identity}_{token_status or 'unknown'}"
    return result


def diagnose_open_feishu_connectivity() -> dict:
    base_env = os.environ.copy()
    direct_env = {
        key: value
        for key, value in base_env.items()
        if key not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"}
    }
    probes = []
    for host in get_openapi_host_candidates():
        probe_specs = [
            (f"{host}|current_env", base_env, ["curl", "-I", "--max-time", "12", host]),
            (f"{host}|direct_env", direct_env, ["curl", "-I", "--max-time", "12", host]),
        ]
        for name, env, command in probe_specs:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    env=env,
                )
                probes.append(
                    {
                        "probe": name,
                        "returncode": completed.returncode,
                        "stdout": (completed.stdout or "").strip()[:500],
                        "stderr": (completed.stderr or "").strip()[:500],
                    }
                )
            except Exception as exc:
                probes.append({"probe": name, "error": str(exc)})
    return {"probes": probes}


def build_feishu_network_error(exc: Exception, *, stage: str) -> RuntimeError:
    details = {
        "stage": stage,
        "host_candidates": get_openapi_host_candidates(),
        "active_host": get_active_openapi_host(),
        "auth_route": detect_lark_cli_auth_route(),
        "proxy_env": collect_proxy_env(),
        "requests_trust_env": build_feishu_session().trust_env,
        "connectivity": diagnose_open_feishu_connectivity(),
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    return RuntimeError("Feishu OpenAPI unreachable.\n" + json.dumps(details, ensure_ascii=False, indent=2))


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


def infer_dm_sent_status(source_row: dict) -> str:
    explicit_status = normalize_text(source_row.get("DM 发送状态", ""))
    if explicit_status:
        return explicit_status

    legacy_status = normalize_text(source_row.get("Mail1发出状态", ""))
    if legacy_status in {"Y", "DM 未开通"}:
        return legacy_status

    remark = normalize_text(source_row.get("备注", ""))
    if "DM未开通" in normalize_key(remark):
        return "DM 未开通"
    return "Y"


def normalize_language(value) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    mapping = {
        "英语": "English",
        "英文": "English",
        "english": "English",
        "日语": "Japanese",
        "日文": "Japanese",
        "japanese": "Japanese",
        "中文": "Chinese",
        "汉语": "Chinese",
        "chinese": "Chinese",
    }
    return mapping.get(text.strip().lower(), text)


def format_follower_count(value) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    compact = text.replace(",", "").strip()
    upper = compact.upper()
    if upper.endswith(("K", "M", "B")):
        match = re.search(r"(\d+(?:\.\d+)?)", upper)
        if match:
            number = float(match.group(1))
            multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[upper[-1]]
            return str(int(round(number * multiplier)))
        return compact
    match = re.search(r"(\d+(?:\.\d+)?)", compact)
    if not match:
        return text
    number = float(match.group(1))
    return str(int(number)) if number.is_integer() else str(number)


def col_idx_to_letter(idx: int) -> str:
    letter = ""
    while idx >= 0:
        letter = chr(idx % 26 + ord("A")) + letter
        idx = idx // 26 - 1
    return letter


def extract_spreadsheet_token(url: str) -> str:
    match = re.search(r"/sheets/([A-Za-z0-9]+)", url)
    if not match:
        raise ValueError(f"Unable to extract spreadsheet token from URL: {url}")
    return match.group(1)


def get_tenant_access_token() -> str:
    global ACTIVE_FEISHU_OPENAPI_HOST, TOKEN_CACHE
    if TOKEN_CACHE["token"] and TOKEN_CACHE["host"] and TOKEN_CACHE["expires_at"] > time.time() + 120:
        ACTIVE_FEISHU_OPENAPI_HOST = str(TOKEN_CACHE["host"])
        return str(TOKEN_CACHE["token"])

    config = require_app_credentials()
    last_exc: Exception | None = None
    for host in get_openapi_host_candidates():
        try:
            response = feishu_request(
                "POST",
                f"{host}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": config.feishu_app_id, "app_secret": config.feishu_app_secret},
            )
            payload = response.json()
            if payload.get("code") not in (None, 0):
                raise RuntimeError(f"Failed to get tenant access token from {host}: {payload}")
            token = payload.get("tenant_access_token", "")
            if not token:
                raise RuntimeError(f"Tenant access token missing in response from {host}")
            ACTIVE_FEISHU_OPENAPI_HOST = host
            expire_seconds = int(payload.get("expire", 7200) or 7200)
            TOKEN_CACHE = {
                "token": token,
                "host": host,
                "expires_at": time.time() + expire_seconds,
            }
            return token
        except (requests.RequestException, RuntimeError) as exc:
            last_exc = exc
            continue
    raise build_feishu_network_error(last_exc or RuntimeError("Unknown Feishu auth failure"), stage="tenant_access_token")


def get_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def fetch_sheet_metas(spreadsheet_token: str) -> list[dict]:
    token = get_tenant_access_token()
    response = feishu_request(
        "GET",
        build_openapi_url(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo"),
        headers=get_headers(token),
        timeout=60,
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
    response = feishu_request(
        "GET",
        build_openapi_url(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{target_range}"),
        headers=get_headers(token),
        timeout=60,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to fetch values: {payload}")
    return payload["data"]["valueRange"].get("values", [])


def export_backup_xlsx(spreadsheet_token: str, output_dir: Path, values: list[list]) -> dict:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = output_dir / f"feishu_master_backup_{timestamp}.xlsx"
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


def load_source_rows(source_csv: Path) -> list[dict]:
    df = pd.read_csv(source_csv, encoding="utf-8-sig").fillna("")
    records = df.to_dict(orient="records")
    seen = set()
    deduped = []
    for row in records:
        account_id = normalize_key(row.get("账号ID", ""))
        account_url = normalize_key(row.get("账号链接", ""))
        key = account_id or account_url
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_header_index_map(header: list) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = {}
    for idx, cell in enumerate(header):
        key = normalize_text(cell)
        if not key:
            continue
        mapping.setdefault(key, []).append(idx)
    return mapping


def build_existing_sets(values: list[list], header_map: dict[str, list[int]]) -> tuple[set[str], set[str]]:
    account_idx = header_map.get("账号ID", [None])[0]
    url_idx = header_map.get("账号链接", [None])[0]
    existing_ids = set()
    existing_urls = set()
    for row in values[1:]:
        if account_idx is not None and account_idx < len(row):
            account = normalize_key(row[account_idx])
            if account:
                existing_ids.add(account)
        if url_idx is not None and url_idx < len(row):
            url = normalize_key(row[url_idx])
            if url:
                existing_urls.add(url)
    return existing_ids, existing_urls


def project_row(source_row: dict, master_header: list, header_map: dict[str, list[int]]) -> list[str]:
    output = [""] * len(master_header)
    for source_key, source_value in source_row.items():
        if source_key in {"Source_Date", "Source_File"}:
            continue
        if source_key not in header_map:
            continue
        normalized_value = normalize_text(source_value)
        if source_key == "语言":
            normalized_value = normalize_language(source_value)
        elif source_key == "粉丝数":
            normalized_value = format_follower_count(source_value)
        for idx in header_map[source_key]:
            output[idx] = normalized_value

    dm_sent_status = infer_dm_sent_status(source_row)
    for idx in header_map.get("DM 发送状态", []):
        output[idx] = dm_sent_status
    for idx in header_map.get("DM 回复状态", []):
        output[idx] = ""

    if "外链__平台抓取" in header_map:
        value = normalize_text(source_row.get("外链__平台抓取", ""))
        for idx in header_map["外链__平台抓取"]:
            output[idx] = value

    return output


def find_append_start_row(values: list[list]) -> int:
    last_non_empty = 0
    for idx, row in enumerate(values, start=1):
        if any(normalize_text(cell) for cell in row):
            last_non_empty = idx
    return last_non_empty + 1


def append_rows(spreadsheet_token: str, sheet_id: str, start_row: int, rows: list[list[str]]) -> dict:
    token = get_tenant_access_token()
    end_col = col_idx_to_letter(len(rows[0]) - 1)
    end_row = start_row + len(rows) - 1
    target_range = f"{sheet_id}!A{start_row}:{end_col}{end_row}"
    response = feishu_request(
        "POST",
        build_openapi_url(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update"),
        headers=get_headers(token),
        json={"valueRanges": [{"range": target_range, "values": rows}]},
        timeout=60,
    )
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to append rows: {payload}")
    payload["target_range"] = target_range
    return payload


def compute_stats(values: list[list], header_map: dict[str, list[int]], appended_rows: list[list[str]]) -> dict:
    account_idx = header_map.get("账号ID", [None])[0]
    sent_idx = header_map.get("DM 发送状态", [None])[0]
    reply_idx = header_map.get("DM 回复状态", [None])[0]

    total_accounts = 0
    total_sent = 0
    total_dm_unavailable = 0
    total_replied = 0
    for row in values[1:]:
        account = normalize_text(row[account_idx]) if account_idx is not None and account_idx < len(row) else ""
        sent = normalize_text(row[sent_idx]) if sent_idx is not None and sent_idx < len(row) else ""
        replied = normalize_text(row[reply_idx]) if reply_idx is not None and reply_idx < len(row) else ""
        if account:
            total_accounts += 1
        if sent.upper() == "Y":
            total_sent += 1
        if sent == "DM 未开通":
            total_dm_unavailable += 1
        if replied.upper() == "Y":
            total_replied += 1

    today_new_accounts = len(appended_rows)
    today_new_sent = 0
    today_new_dm_unavailable = 0
    today_new_replied = 0
    for row in appended_rows:
        if sent_idx is not None and sent_idx < len(row):
            sent_value = normalize_text(row[sent_idx])
            if sent_value.upper() == "Y":
                today_new_sent += 1
            if sent_value == "DM 未开通":
                today_new_dm_unavailable += 1
        if reply_idx is not None and reply_idx < len(row) and normalize_text(row[reply_idx]).upper() == "Y":
            today_new_replied += 1

    return {
        "表格一共多少人账号": total_accounts,
        "今日新增多少账号": today_new_accounts,
        "已发送 DM 数量一共多少": total_sent,
        "已发送 DM 数量今日新增多少": today_new_sent,
        "DM 未开通数量一共多少": total_dm_unavailable,
        "DM 未开通数量今日新增多少": today_new_dm_unavailable,
        "DM 已回复一共多少": total_replied,
        "DM 已回复今日新增多少": today_new_replied,
    }


def write_preview_csv(path: Path, header: list, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([normalize_text(cell) for cell in header])
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append-only Feishu master sync via OpenAPI")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
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

    master_header = values[0]
    header_map = build_header_index_map(master_header)
    existing_ids, existing_urls = build_existing_sets(values, header_map)
    source_rows = load_source_rows(source_csv)

    staged_rows = []
    skipped_rows = []
    for row in source_rows:
        account_id = normalize_key(row.get("账号ID", ""))
        account_url = normalize_key(row.get("账号链接", ""))
        if (account_id and account_id in existing_ids) or (account_url and account_url in existing_urls):
            skipped_rows.append(
                {
                    "账号ID": normalize_text(row.get("账号ID", "")),
                    "频道/作者名称": normalize_text(row.get("频道/作者名称", "")),
                    "reason": "exists_in_target",
                }
            )
            continue
        staged_rows.append(project_row(row, master_header, header_map))
        if account_id:
            existing_ids.add(account_id)
        if account_url:
            existing_urls.add(account_url)

    append_start_row = find_append_start_row(values)
    preview_csv = output_dir / "feishu_master_append_preview.csv"
    preview_json = output_dir / "feishu_master_append_preview.json"
    audit_json = output_dir / "feishu_master_append_audit.json"

    write_preview_csv(preview_csv, master_header, staged_rows)
    preview_json.write_text(
        json.dumps(
            {
                "source_csv": str(source_csv),
                "target_url": args.target_url,
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "mode": args.mode,
                "append_start_row": append_start_row,
                "staged_count": len(staged_rows),
                "skipped_count": len(skipped_rows),
                "rows_preview": staged_rows[:10],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    append_result = None
    backup_result = None
    if args.mode == "apply" and staged_rows:
        backup_result = export_backup_xlsx(spreadsheet_token, output_dir, values)
        append_result = append_rows(spreadsheet_token, sheet_id, append_start_row, staged_rows)

    _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=sheet_id,
    )
    refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count)
    stats = compute_stats(refreshed_values, header_map, staged_rows if args.mode == "apply" else [])

    verification = []
    if args.mode == "apply" and staged_rows:
        refreshed_header = [normalize_text(cell) for cell in refreshed_values[0]]
        idx = {name: i for i, name in enumerate(refreshed_header)}
        for row_num in range(append_start_row, append_start_row + min(len(staged_rows), 20)):
            row = refreshed_values[row_num - 1] if row_num - 1 < len(refreshed_values) else []
            verification.append(
                {
                    "row": row_num,
                    "账号ID": normalize_text(row[idx["账号ID"]]) if idx.get("账号ID") is not None and idx["账号ID"] < len(row) else "",
                    "DM 发送状态": normalize_text(row[idx["DM 发送状态"]]) if idx.get("DM 发送状态") is not None and idx["DM 发送状态"] < len(row) else "",
                    "语言": normalize_text(row[idx["语言"]]) if idx.get("语言") is not None and idx["语言"] < len(row) else "",
                    "粉丝数": normalize_text(row[idx["粉丝数"]]) if idx.get("粉丝数") is not None and idx["粉丝数"] < len(row) else "",
                }
            )

    audit = {
        "source_csv": str(source_csv),
        "target_url": args.target_url,
        "sheet_id": sheet_id,
        "sheet_title": sheet_title,
        "mode": args.mode,
        "target_rows_before": row_count,
        "target_rows_after": refreshed_row_count,
        "target_columns": column_count,
        "source_unique_rows": len(source_rows),
        "staged_append_rows": len(staged_rows),
        "skipped_existing_rows": len(skipped_rows),
        "append_start_row": append_start_row,
        "skipped_examples": skipped_rows[:20],
        "backup_result": backup_result,
        "append_result": append_result,
        "verification_sample": verification,
        "stats": stats,
    }
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
