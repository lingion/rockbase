#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import os
import re
import ssl
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - runtime dependency guard
    requests = None

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover - runtime dependency guard
    Workbook = None

AG_FEISHU_COPILOT_SCRIPTS = Path(
    "${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot/scripts"
)
if str(AG_FEISHU_COPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AG_FEISHU_COPILOT_SCRIPTS))

from runtime_config import require_app_credentials

PROJECT_ROOT = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency"
)
WORKBENCH_ROOT = PROJECT_ROOT / "workbench"
LIST_MASTER_ROOT = PROJECT_ROOT / "Agency/list-master"
ENRICHABLE_FIELDS = (
    "账号ID",
    "平台",
    "多平台标记",
    "账号链接",
    "语言",
    "博主国家",
    "粉丝数",
    "账号类目标签__平台抓取",
    "账号类目标签",
    "置顶最高播放",
    "原价",
    "账号简介",
    "账号简介__平台抓取",
    "联系方式",
    "联系方式备注",
    "外链__平台抓取",
)
ENRICH_FIELD_ALIASES = {
    "账号ID": ("账号ID", "username", "creator_handle", "handle"),
    "平台": ("平台", "platform"),
    "多平台标记": ("多平台标记", "multi_platform"),
    "账号链接": ("账号链接", "profile_url", "url"),
    "语言": ("语言", "language"),
    "博主国家": ("博主国家", "country"),
    "粉丝数": ("粉丝数", "followers", "follower_count"),
    "账号类目标签__平台抓取": ("账号类目标签__平台抓取", "账号类目标签", "category", "bio_keywords"),
    "账号类目标签": ("账号类目标签", "账号类目标签__平台抓取", "category", "bio_keywords"),
    "置顶最高播放": ("置顶最高播放", "top_views", "peak_views"),
    "原价": ("原价", "original_price"),
    "账号简介": ("账号简介", "bio", "账号简介__平台抓取"),
    "账号简介__平台抓取": ("账号简介__平台抓取", "bio", "账号简介"),
    "联系方式": ("联系方式", "contact", "Reply_Contact_Email"),
    "联系方式备注": ("联系方式备注", "contact_note"),
    "外链__平台抓取": ("外链__平台抓取", "external_links", "links", "website"),
}
HEADER_ALIASES = {
    "Mail1邮件发送": ("Mail1邮件发送", "Mail1发送", "Mail1 发送"),
    "Mail1 邮件回复": ("Mail1 邮件回复", "Mail1 回复", "Mail1邮件回复"),
}
MANDATORY_APPEND_FIELDS = (
    "账号ID",
    "频道/作者名称",
    "平台",
    "账号链接",
    "语言",
    "粉丝数",
    "联系方式",
    "报价标准化",
    "报价原文",
)
DEFAULT_OPENAPI_BASE_URL = os.environ.get("FEISHU_OPENAPI_BASE", "https://open.larksuite.com").rstrip("/")
REQUEST_SESSION = None


def describe_network_context() -> str:
    keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "NO_PROXY",
        "no_proxy",
    )
    parts = [f"{key}={os.environ.get(key, '')}" for key in keys if os.environ.get(key)]
    parts.append(f"ssl={ssl.OPENSSL_VERSION}")
    return "; ".join(parts)


def wrap_request_error(stage: str, err: Exception) -> RuntimeError:
    return RuntimeError(
        f"Feishu API request failed during {stage}: {type(err).__name__}: {err}. "
        f"network_context={describe_network_context()}"
    )


def get_requests_session():
    global REQUEST_SESSION
    if REQUEST_SESSION is None:
        REQUEST_SESSION = requests.Session()
        # Ignore shell proxy env so this workflow can use the direct OpenAPI path.
        REQUEST_SESSION.trust_env = False
    return REQUEST_SESSION


def require_runtime_dependencies() -> None:
    missing = []
    if requests is None:
        missing.append("requests")
    if Workbook is None:
        missing.append("openpyxl")
    if missing:
        raise RuntimeError(
            "Missing runtime dependencies: "
            + ", ".join(missing)
            + ". Run this workflow with the project Python environment that includes them."
        )


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
        return "\n".join([part for part in parts if part])
    if isinstance(value, dict):
        return str(value.get("text") or value.get("link") or "").strip()
    return str(value).strip()


def normalize_key(value) -> str:
    return re.sub(r"\s+", "", normalize_text(value).strip().lower())


def normalize_name(value: str) -> str:
    text = normalize_text(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"[^\w ]+", "", text)


def normalize_creator_name(value: str) -> str:
    text = normalize_text(value).strip()
    lower = text.lower()
    prefixes = (
        "potential ai campaign fit:",
        "paid collaboration:",
        "paid collab:",
        "youtube collaboration idea for your audience",
        "re:",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix):].strip(" :-")
            lower = text.lower()
    text = re.sub(r"\s+x\s+rockbase agency\b", "", text, flags=re.I).strip(" -:")
    return normalize_name(text)


def parse_date_only(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    return ""


def row_belongs_to_s3_replyops(row: dict) -> bool:
    subject = normalize_text(row.get("Reply_Last_Subject", "")).lower()
    reply_status = normalize_text(row.get("Reply_Status", "")).lower()
    current_scenario = normalize_text(row.get("Current_Reply_Scenario", "")).lower()
    next_action = normalize_text(row.get("Next_Reply_Action", "")).lower()
    sort_bucket = normalize_text(row.get("Sort_Bucket", "")).lower()
    pipeline_stage = normalize_text(row.get("Pipeline_Stage", "")).lower()
    if not subject:
        subject_based = True
    else:
        blocked_markers = (
            "airtap x",
            "official termination of collaboration",
            "urgent refund request",
        )
        if any(marker in subject for marker in blocked_markers):
            return False
        allow_markers = (
            "rockbase agency",
            "potential ai campaign fit:",
            "paid collaboration:",
            "paid collab:",
            "youtube collaboration idea for your audience",
            "paid ai productivity campaigns",
        )
        subject_based = any(marker in subject for marker in allow_markers)
    state_based = any(
        marker in " | ".join([reply_status, current_scenario, next_action, sort_bucket, pipeline_stage])
        for marker in (
            "wf1_price_recovered",
            "price_captured_waiting_reply_send",
            "review_gmail_draft_then_send_if_approved",
            "1_quoted_mail1",
            "price_received_followup_pending",
        )
    )
    return subject_based or state_based


def completeness_score(row: dict) -> int:
    score = 0
    for key in ENRICHABLE_FIELDS:
        if normalize_text(row.get(key, "")):
            score += 1
    if normalize_key(row.get("账号ID", "")):
        score += 2
    if normalize_key(row.get("账号链接", "")):
        score += 2
    if extract_emails(row.get("联系方式", "")) or extract_emails(row.get("Reply_Contact_Email", "")):
        score += 2
    if "rockbase agency" in normalize_text(row.get("Reply_Last_Subject", "")).lower():
        score += 1
    return score


def canonical_duplicate_key(row: dict) -> tuple[str, str, str] | None:
    email_candidates = extract_emails(row.get("联系方式", "")) or extract_emails(row.get("Reply_Contact_Email", ""))
    email_key = email_candidates[0] if email_candidates else ""
    price_key = normalize_text(row.get("latest_price_normalized", ""))
    platform_key = normalize_key(row.get("平台", ""))
    if email_key and price_key:
        return (email_key, price_key, platform_key)
    return None


def extract_emails(value: str) -> list[str]:
    text = normalize_text(value)
    matches = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
    return sorted({normalize_key(item) for item in matches if item})


def extract_spreadsheet_token(url: str) -> str:
    match = re.search(r"/sheets/([A-Za-z0-9]+)", url)
    if not match:
        raise ValueError(f"Unable to extract spreadsheet token from URL: {url}")
    return match.group(1)


def is_real_price_value(value: str) -> bool:
    text = normalize_text(value)
    lower = text.lower()
    blocked_markers = (
        "no_new_price",
        "no_price",
        "attachment_",
        "pending_parse",
        "verification_gate",
        "brief_gate",
        "company_context_requested",
    )
    if any(marker in lower for marker in blocked_markers):
        return False
    return bool(re.search(r"[$€£¥₹0-9]", text))


def col_idx_to_letter(idx: int) -> str:
    letter = ""
    while idx >= 0:
        letter = chr(idx % 26 + ord("A")) + letter
        idx = idx // 26 - 1
    return letter


def _run_lark_cli_auth_status() -> dict:
    try:
        result = subprocess.run(
            ["lark-cli", "auth", "status"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return {}
    try:
        return json.loads(result.stdout)
    except Exception:
        return {}


def resolve_auth_mode() -> dict[str, str]:
    auth = _run_lark_cli_auth_status()
    if auth.get("identity") == "user" and auth.get("tokenStatus") == "valid":
        return {
            "auth_mode": "lark_cli_user_available",
            "auth_note": "lark-cli user auth is valid, but this workflow still writes through tenant env for stable OpenAPI sheet access.",
        }
    return {
        "auth_mode": "tenant_env",
        "auth_note": "lark-cli user auth is unavailable or expired; falling back to ag-feishu-copilot tenant env credentials.",
    }


def get_tenant_access_token(api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> str:
    config = require_app_credentials()
    session = get_requests_session()
    try:
        response = session.post(
            f"{api_base_url}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": config.feishu_app_id, "app_secret": config.feishu_app_secret},
            timeout=30,
        )
    except Exception as err:
        raise wrap_request_error("tenant_access_token", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to get tenant access token: {payload}")
    token = payload.get("tenant_access_token", "")
    if not token:
        raise RuntimeError("Tenant access token missing in response")
    return token


def get_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def fetch_sheet_metas(spreadsheet_token: str, api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> list[dict]:
    token = get_tenant_access_token(api_base_url)
    session = get_requests_session()
    try:
        response = session.get(
            f"{api_base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo",
            headers=get_headers(token),
            timeout=30,
        )
    except Exception as err:
        raise wrap_request_error("fetch_sheet_metas", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to fetch sheet meta: {payload}")
    return payload["data"]["sheets"]


def select_sheet_meta(spreadsheet_token: str, sheet_id: str = "", sheet_title: str = "", api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> tuple[str, str, int, int]:
    sheets = fetch_sheet_metas(spreadsheet_token, api_base_url=api_base_url)
    if sheet_id:
        matches = [sheet for sheet in sheets if sheet.get("sheetId") == sheet_id]
    elif sheet_title:
        matches = [sheet for sheet in sheets if normalize_text(sheet.get("title")) == sheet_title]
    else:
        matches = sheets[:1]

    if not matches:
        available = [{"sheet_id": sheet.get("sheetId"), "title": sheet.get("title")} for sheet in sheets]
        raise RuntimeError(
            "Unable to select target sheet. "
            f"Requested sheet_id={sheet_id!r}, sheet_title={sheet_title!r}. Available sheets: {available}"
        )

    sheet = matches[0]
    return (
        sheet["sheetId"],
        normalize_text(sheet.get("title")),
        int(sheet.get("rowCount", 0)),
        int(sheet.get("columnCount", 0)),
    )


def fetch_values(spreadsheet_token: str, sheet_id: str, row_count: int, column_count: int, api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> list[list]:
    token = get_tenant_access_token(api_base_url)
    session = get_requests_session()
    end_col = col_idx_to_letter(column_count - 1)
    target_range = f"{sheet_id}!A1:{end_col}{max(row_count, 1)}"
    try:
        response = session.get(
            f"{api_base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{target_range}",
            headers=get_headers(token),
            timeout=60,
        )
    except Exception as err:
        raise wrap_request_error("fetch_values", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to fetch values: {payload}")
    return payload["data"]["valueRange"].get("values", [])


def export_backup_xlsx(output_dir: Path, values: list[list]) -> dict:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = output_dir / f"feishu_s3_replyops_backup_{timestamp}.xlsx"
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
        "local_backup_path": str(backup_path),
        "local_backup_size": backup_path.stat().st_size,
        "format": "xlsx",
        "method": "openapi-read-to-xlsx",
    }


def build_header_map(header: list) -> dict[str, int]:
    mapping = {}
    for idx, cell in enumerate(header):
        name = normalize_text(cell)
        if name and name not in mapping:
            mapping[name] = idx
    for canonical, aliases in HEADER_ALIASES.items():
        if canonical in mapping:
            continue
        for alias in aliases:
            if alias in mapping:
                mapping[canonical] = mapping[alias]
                break
    return mapping


def build_append_duplicate_sets(values: list[list], header_map: dict[str, int]) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    idx_account = header_map["账号ID"]
    idx_url = header_map["账号链接"]
    idx_name = header_map["频道/作者名称"]
    idx_contact = header_map["联系方式"]
    account_ids: set[str] = set()
    account_urls: set[str] = set()
    name_email_pairs: set[tuple[str, str]] = set()
    for row in values[1:]:
        account_key = normalize_key(row[idx_account]) if idx_account < len(row) else ""
        if account_key:
            account_ids.add(account_key)
        url_key = normalize_key(row[idx_url]) if idx_url < len(row) else ""
        if url_key:
            account_urls.add(url_key)
        name_key = normalize_name(row[idx_name]) if idx_name < len(row) else ""
        email_key = ""
        if idx_contact < len(row):
            emails = extract_emails(row[idx_contact])
            if emails:
                email_key = emails[0]
        if name_key and email_key:
            name_email_pairs.add((name_key, email_key))
    return account_ids, account_urls, name_email_pairs


def pick_first(source_row: dict, *keys: str) -> str:
    for key in keys:
        value = normalize_text(source_row.get(key, ""))
        if value:
            return value
    return ""


def merge_missing_fields(base_row: dict, candidate_row: dict, source_label: str = "") -> bool:
    changed = False
    for field_name, aliases in ENRICH_FIELD_ALIASES.items():
        if normalize_text(base_row.get(field_name, "")):
            continue
        for alias in aliases:
            value = normalize_text(candidate_row.get(alias, ""))
            if value:
                base_row[field_name] = value
                changed = True
                break
    if changed and source_label:
        note = normalize_text(base_row.get("联系方式备注", ""))
        note_tag = f"enriched:{source_label}"
        if note_tag not in note:
            base_row["联系方式备注"] = f"{note} | {note_tag}".strip(" |")
    return changed


def format_follower_count(value: str) -> str:
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


def build_append_row(master_header: list, header_map: dict[str, int], source_row: dict, write_date: str) -> list[str]:
    output = [""] * len(master_header)
    projected = project_append_fields(source_row, write_date)
    for field_name, field_value in projected.items():
        if field_name not in header_map:
            continue
        output[header_map[field_name]] = field_value
    return output


def project_append_fields(source_row: dict, write_date: str) -> dict[str, str]:
    return {
        "分区": write_date,
        "账号ID": pick_first(source_row, "账号ID"),
        "频道/作者名称": pick_first(source_row, "频道/作者名称"),
        "Mail1邮件发送": "Y",
        "Mail1 邮件回复": "Y",
        "报价标准化": pick_first(source_row, "latest_price_normalized"),
        "报价原文": pick_first(source_row, "latest_price_raw"),
        "平台": pick_first(source_row, "平台"),
        "多平台标记": pick_first(source_row, "多平台标记"),
        "账号链接": pick_first(source_row, "账号链接"),
        "语言": pick_first(source_row, "语言"),
        "博主国家": pick_first(source_row, "博主国家"),
        "粉丝数": format_follower_count(pick_first(source_row, "粉丝数")),
        "账号类目标签__平台抓取": pick_first(source_row, "账号类目标签__平台抓取", "账号类目标签"),
        "置顶最高播放": format_follower_count(pick_first(source_row, "置顶最高播放")),
        "原价": pick_first(source_row, "原价"),
        "账号简介": pick_first(source_row, "账号简介"),
        "账号简介__平台抓取": pick_first(source_row, "账号简介__平台抓取", "账号简介"),
        "联系方式": pick_first(source_row, "联系方式", "Reply_Contact_Email"),
        "联系方式备注": pick_first(source_row, "联系方式备注"),
        "外链__平台抓取": pick_first(source_row, "外链__平台抓取"),
    }


def append_gate_missing_fields(projected: dict[str, str]) -> list[str]:
    missing = []
    for field_name in MANDATORY_APPEND_FIELDS:
        if not normalize_text(projected.get(field_name, "")):
            missing.append(field_name)
    return missing


def find_append_start_row(values: list[list]) -> int:
    last_non_empty = 0
    for idx, row in enumerate(values, start=1):
        if any(normalize_text(cell) for cell in row):
            last_non_empty = idx
    return last_non_empty + 1


def append_rows(spreadsheet_token: str, sheet_id: str, start_row: int, rows: list[list[str]], api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> dict:
    token = get_tenant_access_token(api_base_url)
    session = get_requests_session()
    end_col = col_idx_to_letter(len(rows[0]) - 1)
    end_row = start_row + len(rows) - 1
    target_range = f"{sheet_id}!A{start_row}:{end_col}{end_row}"
    try:
        response = session.post(
            f"{api_base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
            headers=get_headers(token),
            json={"valueRanges": [{"range": target_range, "values": rows}]},
            timeout=60,
        )
    except Exception as err:
        raise wrap_request_error("append_rows", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to append rows: {payload}")
    payload["target_range"] = target_range
    return payload


def write_batch(spreadsheet_token: str, updates: list[dict], api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> dict:
    token = get_tenant_access_token(api_base_url)
    session = get_requests_session()
    try:
        response = session.post(
            f"{api_base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
            headers=get_headers(token),
            json={"valueRanges": updates},
            timeout=60,
        )
    except Exception as err:
        raise wrap_request_error("write_batch", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to batch update values: {payload}")
    return payload


def rewrite_data_block(spreadsheet_token: str, sheet_id: str, header: list, rows: list[list], api_base_url: str = DEFAULT_OPENAPI_BASE_URL) -> dict | None:
    if not rows:
        return None
    token = get_tenant_access_token(api_base_url)
    session = get_requests_session()
    end_col = col_idx_to_letter(len(header) - 1)
    end_row = len(rows) + 1
    target_range = f"{sheet_id}!A2:{end_col}{end_row}"
    try:
        response = session.post(
            f"{api_base_url}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
            headers=get_headers(token),
            json={"valueRanges": [{"range": target_range, "values": rows}]},
            timeout=60,
        )
    except Exception as err:
        raise wrap_request_error("rewrite_data_block", err) from err
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(f"Failed to rewrite data block: {payload}")
    payload["target_range"] = target_range
    return payload


def latest_incremental_date(rows: list[dict]) -> str:
    candidates: list[str] = []
    for row in rows:
        for key in ("Capture_At", "Gmail_Draft_Created_At", "Sent_Status_Updated_At"):
            date_only = parse_date_only(row.get(key, ""))
            if date_only:
                candidates.append(date_only)
    return max(candidates) if candidates else ""


def load_source_rows(source_csv: Path, source_mode: str, incremental_date: str = "") -> tuple[list[dict], dict, list[dict]]:
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    is_manifest = "manifest_status" in (rows[0].keys() if rows else []) if rows else False
    selected_incremental_date = incremental_date
    if source_mode == "incremental_only" and not is_manifest and not selected_incremental_date:
        selected_incremental_date = latest_incremental_date(rows)

    usable = []
    seen = set()
    canonical_rows = {}
    filtered_rows: list[dict] = []
    for row in rows:
        price_norm = normalize_text(row.get("latest_price_normalized", ""))
        if not is_real_price_value(price_norm):
            filtered_rows.append(
                {
                    "reason": "no_real_price",
                    "频道/作者名称": normalize_text(row.get("频道/作者名称", "")),
                    "Reply_Contact_Email": normalize_text(row.get("Reply_Contact_Email", "")),
                    "Reply_Thread_ID": normalize_text(row.get("Reply_Thread_ID", "")),
                }
            )
            continue
        if not row_belongs_to_s3_replyops(row):
            filtered_rows.append(
                {
                    "reason": "not_s3_replyops_scope",
                    "频道/作者名称": normalize_text(row.get("频道/作者名称", "")),
                    "Reply_Contact_Email": normalize_text(row.get("Reply_Contact_Email", "")),
                    "Reply_Thread_ID": normalize_text(row.get("Reply_Thread_ID", "")),
                }
            )
            continue
        if source_mode == "incremental_only" and not is_manifest:
            row_date = ""
            for key in ("Capture_At", "Gmail_Draft_Created_At", "Sent_Status_Updated_At"):
                row_date = parse_date_only(row.get(key, ""))
                if row_date:
                    break
            if selected_incremental_date and row_date != selected_incremental_date:
                filtered_rows.append(
                    {
                        "reason": f"outside_incremental_date:{selected_incremental_date}",
                        "频道/作者名称": normalize_text(row.get("频道/作者名称", "")),
                        "Reply_Contact_Email": normalize_text(row.get("Reply_Contact_Email", "")),
                        "Reply_Thread_ID": normalize_text(row.get("Reply_Thread_ID", "")),
                    }
                )
                continue
        item = dict(row)
        item["账号ID"] = normalize_text(row.get("账号ID", ""))
        item["频道/作者名称"] = normalize_text(row.get("频道/作者名称", ""))
        item["Reply_Contact_Email"] = normalize_text(row.get("Reply_Contact_Email", ""))
        item["latest_price_normalized"] = price_norm
        item["latest_price_raw"] = normalize_text(row.get("latest_price_raw", ""))
        canonical_key = canonical_duplicate_key(item)
        if canonical_key:
            existing = canonical_rows.get(canonical_key)
            if existing is None or completeness_score(item) > completeness_score(existing):
                canonical_rows[canonical_key] = item
            else:
                filtered_rows.append(
                    {
                        "reason": "canonical_duplicate_lower_completeness",
                        "频道/作者名称": item["频道/作者名称"],
                        "Reply_Contact_Email": item["Reply_Contact_Email"],
                        "Reply_Thread_ID": normalize_text(item.get("Reply_Thread_ID", "")),
                    }
                )
            continue
        dedupe_key = (
            normalize_key(item["账号ID"]),
            normalize_creator_name(item["频道/作者名称"]),
            normalize_key(item["Reply_Contact_Email"]),
            normalize_text(item["latest_price_normalized"]),
            normalize_text(item["latest_price_raw"]),
        )
        if dedupe_key in seen:
            filtered_rows.append(
                {
                    "reason": "duplicate_same_identity_and_price",
                    "频道/作者名称": item["频道/作者名称"],
                    "Reply_Contact_Email": item["Reply_Contact_Email"],
                    "Reply_Thread_ID": normalize_text(item.get("Reply_Thread_ID", "")),
                }
            )
            continue
        seen.add(dedupe_key)
        usable.append(item)
    usable.extend(canonical_rows.values())
    usable.sort(
        key=lambda item: (
            parse_date_only(item.get("Capture_At", ""))
            or parse_date_only(item.get("Gmail_Draft_Created_At", ""))
            or parse_date_only(item.get("Sent_Status_Updated_At", "")),
            normalize_creator_name(item.get("频道/作者名称", "")),
        )
    )
    meta = {
        "source_mode": source_mode,
        "source_is_manifest": is_manifest,
        "selected_incremental_date": selected_incremental_date,
        "raw_rows": len(rows),
        "usable_rows_after_scope": len(usable),
        "filtered_rows": len(filtered_rows),
    }
    return usable, meta, filtered_rows


def peer_master_csvs(source_csv: Path, limit: int = 25) -> list[Path]:
    csvs = []
    if LIST_MASTER_ROOT.exists():
        for path in sorted(LIST_MASTER_ROOT.rglob("*.csv")):
            if path == source_csv:
                continue
            csvs.append(path)
            if len(csvs) >= limit:
                break
    return csvs


def peer_master_enrichment(source_row: dict, csv_paths: list[Path]) -> dict:
    source_email = extract_emails(source_row.get("Reply_Contact_Email", "")) or extract_emails(source_row.get("联系方式", ""))
    source_name = normalize_creator_name(source_row.get("频道/作者名称", ""))
    source_account = normalize_key(source_row.get("账号ID", ""))
    source_thread = normalize_text(source_row.get("Reply_Thread_ID", ""))
    for csv_path in csv_paths:
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            continue
        same_account: list[dict] = []
        same_email: list[dict] = []
        same_name: list[dict] = []
        for row in rows:
            row_thread = normalize_text(row.get("Reply_Thread_ID", ""))
            if source_thread and row_thread == source_thread:
                continue
            row_account = normalize_key(row.get("账号ID", "") or row.get("username", "") or row.get("creator_handle", ""))
            if source_account and row_account and source_account == row_account:
                same_account.append(row)
                continue
            row_emails = extract_emails(row.get("Reply_Contact_Email", "")) or extract_emails(row.get("联系方式", ""))
            if source_email and row_emails and source_email[0] == row_emails[0]:
                same_email.append(row)
                continue
            row_name = normalize_creator_name(row.get("频道/作者名称", "") or row.get("creator_name", "") or row.get("name", ""))
            if source_name and row_name and source_name == row_name:
                same_name.append(row)
        for label, candidates in (
            (f"peer_master_account:{csv_path.name}", same_account),
            (f"peer_master_email:{csv_path.name}", same_email),
            (f"peer_master_name:{csv_path.name}", same_name),
        ):
            candidates.sort(key=completeness_score, reverse=True)
            for candidate in candidates[:3]:
                merge_missing_fields(source_row, candidate, label)
    return source_row


def recent_workbench_csvs(limit: int = 60, date_limit: int = 14) -> list[Path]:
    if not WORKBENCH_ROOT.exists():
        return []
    date_dirs = [
        path for path in WORKBENCH_ROOT.iterdir() if path.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}$", path.name)
    ]
    date_dirs.sort(reverse=True)
    csv_paths: list[Path] = []
    for date_dir in date_dirs[:date_limit]:
        for csv_path in sorted(date_dir.rglob("*.csv")):
            try:
                if csv_path.stat().st_size > 8 * 1024 * 1024:
                    continue
            except OSError:
                continue
            csv_paths.append(csv_path)
            if len(csv_paths) >= limit:
                return csv_paths
    return csv_paths


def workbench_enrichment(source_row: dict, csv_paths: list[Path]) -> dict:
    source_account = normalize_key(source_row.get("账号ID", ""))
    source_name = normalize_creator_name(source_row.get("频道/作者名称", ""))
    source_emails = extract_emails(source_row.get("Reply_Contact_Email", "")) or extract_emails(source_row.get("联系方式", ""))
    for csv_path in csv_paths:
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            continue
        best_candidate = None
        best_score = -1
        for row in rows:
            candidate_score = -1
            if source_account:
                row_account = normalize_key(
                    row.get("账号ID") or row.get("username") or row.get("creator_handle") or row.get("handle") or ""
                )
                if row_account and row_account == source_account:
                    candidate_score = 5
            if candidate_score < 0 and source_emails:
                row_emails = extract_emails(row.get("联系方式", "")) or extract_emails(row.get("Reply_Contact_Email", ""))
                if row_emails and row_emails[0] == source_emails[0]:
                    candidate_score = 4
            if candidate_score < 0 and source_name:
                row_name = normalize_creator_name(
                    row.get("频道/作者名称") or row.get("creator_name") or row.get("name") or ""
                )
                if row_name and row_name == source_name:
                    candidate_score = 3
            if candidate_score > best_score:
                best_candidate = row
                best_score = candidate_score
        if best_candidate is not None and best_score >= 3:
            merge_missing_fields(source_row, best_candidate, csv_path.name)
    return source_row


def build_target_indexes(values: list[list], header_map: dict[str, int]) -> tuple[dict, dict, dict]:
    idx_account = header_map["账号ID"]
    idx_name = header_map["频道/作者名称"]
    idx_contact = header_map["联系方式"]
    by_account = {}
    by_name = {}
    by_email = {}
    for row_num, row in enumerate(values[1:], start=2):
        account_id = normalize_key(row[idx_account]) if idx_account < len(row) else ""
        name = normalize_creator_name(row[idx_name]) if idx_name < len(row) else ""
        contact = normalize_text(row[idx_contact]) if idx_contact < len(row) else ""
        record = {"row_num": row_num}
        if account_id:
            by_account[account_id] = record
        if name:
            by_name.setdefault(name, []).append(record)
        for email in extract_emails(contact):
            by_email.setdefault(email, []).append(record)
    return by_account, by_name, by_email


def get_cell(row: list, idx: int) -> str:
    if idx >= len(row):
        return ""
    return normalize_text(row[idx])


def build_updates_for_row(sheet_id: str, row_num: int, header_map: dict[str, int], current_row: list, source_row: dict) -> tuple[list[dict], dict]:
    updates = []
    stats = {"reply_new": 0, "price_updated": 0}
    targets = [
        ("Mail1 邮件回复", "Y", True),
        ("报价标准化", source_row["latest_price_normalized"], False),
        ("报价原文", source_row["latest_price_raw"], False),
    ]
    for column_name, new_value, count_as_reply in targets:
        idx = header_map[column_name]
        old_value = get_cell(current_row, idx)
        if normalize_text(new_value) == old_value:
            continue
        col_letter = col_idx_to_letter(idx)
        updates.append({"range": f"{sheet_id}!{col_letter}{row_num}:{col_letter}{row_num}", "values": [[new_value]]})
        if count_as_reply:
            if old_value.upper() != "Y" and normalize_text(new_value).upper() == "Y":
                stats["reply_new"] += 1
        elif normalize_text(new_value):
            stats["price_updated"] += 1
    return updates, stats


def count_reply_total(values: list[list], header_map: dict[str, int]) -> int:
    reply_idx = header_map["Mail1 邮件回复"]
    total = 0
    for row in values[1:]:
        if reply_idx < len(row) and normalize_text(row[reply_idx]).upper() == "Y":
            total += 1
    return total


def count_top_contiguous_reply_block(values: list[list], header_map: dict[str, int]) -> int:
    reply_idx = header_map["Mail1 邮件回复"]
    total = 0
    for row in values[1:]:
        if reply_idx < len(row) and normalize_text(row[reply_idx]).upper() == "Y":
            total += 1
            continue
        break
    return total


def simulate_post_apply_values(values: list[list], header_map: dict[str, int], match_rows: list[dict], staged_append_rows: list[list[str]]) -> list[list]:
    simulated = [list(row) for row in values]
    row_width = len(values[0]) if values else 0
    reply_idx = header_map["Mail1 邮件回复"]
    price_norm_idx = header_map["报价标准化"]
    price_raw_idx = header_map["报价原文"]
    for item in match_rows:
        row_idx = item["row_num"] - 1
        if row_idx >= len(simulated):
            continue
        row = list(simulated[row_idx])
        if len(row) < row_width:
            row.extend([""] * (row_width - len(row)))
        row[reply_idx] = "Y"
        row[price_norm_idx] = item["source"]["latest_price_normalized"]
        row[price_raw_idx] = item["source"]["latest_price_raw"]
        simulated[row_idx] = row
    for row in staged_append_rows:
        padded = list(row)
        if len(padded) < row_width:
            padded.extend([""] * (row_width - len(padded)))
        simulated.append(padded)
    return simulated


def build_reply_pin_top_plan(values: list[list], header_map: dict[str, int]) -> dict:
    if not values:
        return {
            "reply_y_total": 0,
            "top_block_expected": 0,
            "reordered_rows": [],
            "move_rows": [],
            "top_preview_rows": [],
        }
    reply_idx = header_map["Mail1 邮件回复"]
    account_idx = header_map.get("账号ID", -1)
    name_idx = header_map.get("频道/作者名称", -1)
    row_width = len(values[0])
    records = []
    for old_row_num, row in enumerate(values[1:], start=2):
        padded = list(row)
        if len(padded) < row_width:
            padded.extend([""] * (row_width - len(padded)))
        reply_value = normalize_text(padded[reply_idx]).upper() if reply_idx < len(padded) else ""
        account_id = normalize_text(padded[account_idx]) if account_idx >= 0 and account_idx < len(padded) else ""
        name = normalize_text(padded[name_idx]) if name_idx >= 0 and name_idx < len(padded) else ""
        records.append(
            {
                "old_row_num": old_row_num,
                "reply": reply_value,
                "账号ID": account_id,
                "频道/作者名称": name,
                "is_reply_y": reply_value == "Y",
                "row": padded,
            }
        )
    y_rows = [item for item in records if item["is_reply_y"]]
    other_rows = [item for item in records if not item["is_reply_y"]]
    reordered = y_rows + other_rows
    move_rows = []
    top_preview_rows = []
    for new_row_num, item in enumerate(reordered, start=2):
        preview = {
            "new_row_num": new_row_num,
            "old_row_num": item["old_row_num"],
            "账号ID": item["账号ID"],
            "频道/作者名称": item["频道/作者名称"],
            "Mail1 邮件回复": item["reply"],
        }
        if len(top_preview_rows) < 50:
            top_preview_rows.append(preview)
        if item["old_row_num"] != new_row_num:
            move_rows.append(preview)
    return {
        "reply_y_total": len(y_rows),
        "top_block_expected": len(y_rows),
        "reordered_rows": [item["row"] for item in reordered],
        "move_rows": move_rows,
        "top_preview_rows": top_preview_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write S3 ReplyOps reply and pricing results back into the Feishu master.")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--source-mode", choices=["incremental_only", "full_history"], default="incremental_only")
    parser.add_argument("--incremental-date", default="")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--write-date", default=dt.date.today().isoformat())
    parser.add_argument("--api-base-url", default=DEFAULT_OPENAPI_BASE_URL)
    args = parser.parse_args()
    require_runtime_dependencies()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_csv = Path(args.source_csv).expanduser().resolve()
    api_base_url = args.api_base_url.rstrip("/")

    auth_info = resolve_auth_mode()
    spreadsheet_token = extract_spreadsheet_token(args.target_url)
    sheet_id, sheet_title, row_count, column_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
        api_base_url=api_base_url,
    )
    values = fetch_values(spreadsheet_token, sheet_id, row_count, column_count, api_base_url=api_base_url)
    if not values:
        raise RuntimeError("Target sheet returned no values")

    header = values[0]
    header_map = build_header_map(header)
    required_columns = {"分区", "账号ID", "频道/作者名称", "Mail1邮件发送", "Mail1 邮件回复", "报价标准化", "报价原文", "平台", "账号链接", "联系方式"}
    missing = sorted(required_columns - set(header_map))
    if missing:
        raise RuntimeError(f"Target sheet missing required columns: {missing}")

    source_rows, source_meta, filtered_rows = load_source_rows(source_csv, args.source_mode, args.incremental_date)
    peer_master_csv_paths = peer_master_csvs(source_csv)
    workbench_csv_paths = recent_workbench_csvs()
    source_email_counts = {}
    for source in source_rows:
        email_key = normalize_key(source["Reply_Contact_Email"])
        if email_key:
            source_email_counts[email_key] = source_email_counts.get(email_key, 0) + 1
    by_account, by_name, by_email = build_target_indexes(values, header_map)
    existing_ids, existing_urls, existing_name_email_pairs = build_append_duplicate_sets(values, header_map)

    candidate_rows = []
    unmatched_rows = []
    staged_append_rows = []
    append_samples = []
    append_blocked_rows = []
    review_rows = []
    for source in source_rows:
        source = dict(source)
        source = peer_master_enrichment(source, peer_master_csv_paths)
        source = workbench_enrichment(source, workbench_csv_paths)
        target = None
        match_method = ""

        account_key = normalize_key(source["账号ID"])
        if account_key and account_key in by_account:
            target = by_account[account_key]
            match_method = "account_id"
        else:
            name_key = normalize_creator_name(source["频道/作者名称"])
            name_matches = by_name.get(name_key, [])
            if len(name_matches) == 1:
                target = name_matches[0]
                match_method = "channel_name"
            else:
                email_key = normalize_key(source["Reply_Contact_Email"])
                email_matches = by_email.get(email_key, [])
                if email_key and source_email_counts.get(email_key, 0) == 1 and len(email_matches) == 1:
                    target = email_matches[0]
                    match_method = "reply_email"

        if target is None:
            unmatched_rows.append(source)
            account_id = normalize_key(source["账号ID"])
            account_url = normalize_key(source.get("账号链接", ""))
            name_key = normalize_creator_name(source["频道/作者名称"])
            email_key = normalize_key(source["Reply_Contact_Email"])
            pair_key = (name_key, email_key) if name_key and email_key else None
            if (account_id and account_id in existing_ids) or (account_url and account_url in existing_urls) or (pair_key and pair_key in existing_name_email_pairs):
                review_rows.append(
                    {
                        "reason": "ambiguous_existing_identity",
                        "账号ID": source["账号ID"],
                        "频道/作者名称": source["频道/作者名称"],
                        "Reply_Contact_Email": source["Reply_Contact_Email"],
                    }
                )
                continue
            projected = project_append_fields(source, args.write_date)
            missing_fields = append_gate_missing_fields(projected)
            if missing_fields:
                blocked = dict(projected)
                blocked["reason"] = "append_missing_required_fields"
                blocked["missing_fields"] = "|".join(missing_fields)
                blocked["Reply_Contact_Email"] = source["Reply_Contact_Email"]
                blocked["Reply_Thread_ID"] = normalize_text(source.get("Reply_Thread_ID", ""))
                append_blocked_rows.append(blocked)
                review_rows.append(
                    {
                        "reason": "append_missing_required_fields",
                        "missing_fields": "|".join(missing_fields),
                        "账号ID": projected.get("账号ID", ""),
                        "频道/作者名称": projected.get("频道/作者名称", ""),
                        "Reply_Contact_Email": source["Reply_Contact_Email"],
                    }
                )
                continue
            append_row = build_append_row(header, header_map, source, args.write_date)
            staged_append_rows.append(append_row)
            append_samples.append(source)
            if account_id:
                existing_ids.add(account_id)
            if account_url:
                existing_urls.add(account_url)
            if pair_key:
                existing_name_email_pairs.add(pair_key)
            continue

        current_row = values[target["row_num"] - 1]
        updates, stats = build_updates_for_row(sheet_id, target["row_num"], header_map, current_row, source)
        if not updates:
            continue
        candidate_rows.append(
            {
                "row_num": target["row_num"],
                "match_method": match_method,
                "source": source,
                "updates": updates,
                "stats": stats,
            }
        )

    priority = {"account_id": 0, "channel_name": 1, "reply_email": 2}
    match_rows_by_row = {}
    for item in candidate_rows:
        existing = match_rows_by_row.get(item["row_num"])
        if existing is None or priority[item["match_method"]] < priority[existing["match_method"]]:
            match_rows_by_row[item["row_num"]] = item
    match_rows = sorted(match_rows_by_row.values(), key=lambda item: item["row_num"])
    simulated_values = simulate_post_apply_values(values, header_map, match_rows, staged_append_rows)
    pin_top_plan = build_reply_pin_top_plan(simulated_values, header_map)

    preview_csv = output_dir / "s3_replyops_feishu_writeback_preview.csv"
    append_preview_csv = output_dir / "s3_replyops_feishu_append_preview.csv"
    append_blocked_preview_csv = output_dir / "s3_replyops_feishu_append_blocked_preview.csv"
    filtered_out_csv = output_dir / "s3_replyops_feishu_filtered_out.csv"
    pin_top_preview_csv = output_dir / "s3_replyops_feishu_pin_top_preview.csv"
    pin_top_top50_csv = output_dir / "s3_replyops_feishu_pin_top_top50.csv"
    preview_json = output_dir / "s3_replyops_feishu_writeback_preview.json"
    audit_json = output_dir / "s3_replyops_feishu_writeback_audit.json"

    with preview_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row_num",
                "match_method",
                "账号ID",
                "频道/作者名称",
                "Reply_Contact_Email",
                "new_reply_status",
                "new_price_normalized",
                "new_price_raw",
            ]
        )
        for item in match_rows:
            src = item["source"]
            writer.writerow(
                [
                    item["row_num"],
                    item["match_method"],
                    src["账号ID"],
                    src["频道/作者名称"],
                    src["Reply_Contact_Email"],
                    "Y",
                    src["latest_price_normalized"],
                    src["latest_price_raw"],
                ]
            )

    with append_preview_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([normalize_text(cell) for cell in header])
        writer.writerows(staged_append_rows)

    append_blocked_headers = [
        "reason",
        "missing_fields",
        "账号ID",
        "频道/作者名称",
        "平台",
        "账号链接",
        "语言",
        "粉丝数",
        "联系方式",
        "报价标准化",
        "报价原文",
        "Reply_Contact_Email",
        "Reply_Thread_ID",
    ]
    with append_blocked_preview_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=append_blocked_headers)
        writer.writeheader()
        for row in append_blocked_rows:
            writer.writerow({key: normalize_text(row.get(key, "")) for key in append_blocked_headers})

    filtered_headers = ["reason", "频道/作者名称", "Reply_Contact_Email", "Reply_Thread_ID"]
    with filtered_out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=filtered_headers)
        writer.writeheader()
        for row in filtered_rows:
            writer.writerow({key: normalize_text(row.get(key, "")) for key in filtered_headers})

    with pin_top_preview_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["old_row_num", "new_row_num", "账号ID", "频道/作者名称", "Mail1 邮件回复"])
        for item in pin_top_plan["move_rows"]:
            writer.writerow(
                [
                    item["old_row_num"],
                    item["new_row_num"],
                    item["账号ID"],
                    item["频道/作者名称"],
                    item["Mail1 邮件回复"],
                ]
            )

    with pin_top_top50_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["new_row_num", "old_row_num", "账号ID", "频道/作者名称", "Mail1 邮件回复"])
        for item in pin_top_plan["top_preview_rows"]:
            writer.writerow(
                [
                    item["new_row_num"],
                    item["old_row_num"],
                    item["账号ID"],
                    item["频道/作者名称"],
                    item["Mail1 邮件回复"],
                ]
            )

    preview_json.write_text(
        json.dumps(
            {
                "source_csv": str(source_csv),
                "source_meta": source_meta,
                "target_url": args.target_url,
                "api_base_url": api_base_url,
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "mode": args.mode,
                "auth": auth_info,
                "source_rows_with_real_price": len(source_rows),
                "matched_rows": len(match_rows),
                "staged_append_rows": len(staged_append_rows),
                "append_blocked_rows": len(append_blocked_rows),
                "filtered_out_rows": len(filtered_rows),
                "review_rows": len(review_rows),
                "match_method_breakdown": {
                    key: sum(1 for item in match_rows if item["match_method"] == key)
                    for key in ("account_id", "channel_name", "reply_email")
                },
                "rows_that_would_move_after_pin_top": len(pin_top_plan["move_rows"]),
                "mail1_reply_y_total_after_pin_top": pin_top_plan["reply_y_total"],
                "top_block_expected_after_pin_top": pin_top_plan["top_block_expected"],
                "preview_csv": str(preview_csv),
                "append_preview_csv": str(append_preview_csv),
                "append_blocked_preview_csv": str(append_blocked_preview_csv),
                "filtered_out_csv": str(filtered_out_csv),
                "pin_top_preview_csv": str(pin_top_preview_csv),
                "pin_top_top50_csv": str(pin_top_top50_csv),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    backup_result = None
    write_result = None
    append_result = None
    pin_top_apply_result = None
    reply_new_total = 0
    price_update_total = 0
    append_start_row = find_append_start_row(values)
    if args.mode == "apply" and (match_rows or staged_append_rows):
        backup_result = export_backup_xlsx(output_dir, values)
        if match_rows:
            value_ranges = []
            for item in match_rows:
                value_ranges.extend(item["updates"])
                if item["stats"]["reply_new"]:
                    reply_new_total += 1
                if item["stats"]["price_updated"]:
                    price_update_total += 1
            write_result = write_batch(spreadsheet_token, value_ranges, api_base_url=api_base_url)
        if staged_append_rows:
            append_result = append_rows(spreadsheet_token, sheet_id, append_start_row, staged_append_rows, api_base_url=api_base_url)
            reply_new_total += len(staged_append_rows)
            price_update_total += len(staged_append_rows)

    refreshed_values = values
    if args.mode == "apply":
        _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(spreadsheet_token, sheet_id=sheet_id, api_base_url=api_base_url)
        refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count, api_base_url=api_base_url)
        live_pin_top_plan = build_reply_pin_top_plan(refreshed_values, header_map)
        if live_pin_top_plan["move_rows"]:
            pin_top_apply_result = rewrite_data_block(spreadsheet_token, sheet_id, header, live_pin_top_plan["reordered_rows"], api_base_url=api_base_url)
            _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(spreadsheet_token, sheet_id=sheet_id, api_base_url=api_base_url)
            refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count, api_base_url=api_base_url)

    audit = {
        "source_csv": str(source_csv),
        "source_meta": source_meta,
        "target_url": args.target_url,
        "api_base_url": api_base_url,
        "sheet_id": sheet_id,
        "sheet_title": sheet_title,
        "mode": args.mode,
        "auth": auth_info,
        "source_rows_with_real_price": len(source_rows),
        "matched_rows": len(match_rows),
        "staged_append_rows": len(staged_append_rows),
        "append_blocked_rows": len(append_blocked_rows),
        "filtered_out_rows": len(filtered_rows),
        "review_rows": len(review_rows),
        "match_method_breakdown": {
            key: sum(1 for item in match_rows if item["match_method"] == key)
            for key in ("account_id", "channel_name", "reply_email")
        },
        "append_start_row": append_start_row,
        "backup_result": backup_result,
        "write_result": write_result,
        "append_result": append_result,
        "pin_top_apply_result": pin_top_apply_result,
        "stats": {
            "Mail1 已回复总数": count_reply_total(refreshed_values, header_map),
            "Mail1 已回复今日新增": reply_new_total,
            "报价今日新写入/更新": price_update_total,
        },
        "pin_top": {
            "rows_that_would_move_after_pin_top": len(pin_top_plan["move_rows"]),
            "mail1_reply_y_total_after_pin_top": pin_top_plan["reply_y_total"],
            "top_block_expected_after_pin_top": pin_top_plan["top_block_expected"],
            "top_contiguous_y_block_after_apply": count_top_contiguous_reply_block(refreshed_values, header_map),
        },
        "matched_samples": [
            {
                "row_num": item["row_num"],
                "match_method": item["match_method"],
                "账号ID": item["source"]["账号ID"],
                "频道/作者名称": item["source"]["频道/作者名称"],
                "Reply_Contact_Email": item["source"]["Reply_Contact_Email"],
            }
            for item in match_rows[:20]
        ],
        "append_samples": append_samples[:20],
        "append_blocked_samples": append_blocked_rows[:20],
        "filtered_out_samples": filtered_rows[:20],
        "review_samples": review_rows[:20],
        "artifacts": {
            "preview_csv": str(preview_csv),
            "append_preview_csv": str(append_preview_csv),
            "append_blocked_preview_csv": str(append_blocked_preview_csv),
            "filtered_out_csv": str(filtered_out_csv),
            "pin_top_preview_csv": str(pin_top_preview_csv),
            "pin_top_top50_csv": str(pin_top_top50_csv),
            "preview_json": str(preview_json),
            "audit_json": str(audit_json),
        },
    }
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
