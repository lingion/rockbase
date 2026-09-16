#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import Workbook

AG_FEISHU_COPILOT_SCRIPTS = Path(
    "${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot/scripts"
)
if str(AG_FEISHU_COPILOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AG_FEISHU_COPILOT_SCRIPTS))

from runtime_config import require_app_credentials  # noqa: F401

from feishu_master_incremental_sync import (
    append_rows,
    build_existing_sets,
    build_header_index_map,
    col_idx_to_letter,  # noqa: F401
    extract_spreadsheet_token,
    fetch_values,
    get_tenant_access_token,  # noqa: F401
    normalize_key,
    normalize_text,
    select_sheet_meta,
)


MAIL1_SENT_FIELD_CANDIDATES = ("Mail1发送", "Mail1邮件发送", "Mail1发出状态")
MAIL1_REPLY_FIELD_CANDIDATES = ("Mail1 回复", "Mail1回复", "Mail1 邮件回复")


def first_present_header(header_map: dict[str, list[int]], *names: str) -> str:
    for name in names:
        if name in header_map:
            return name
    return ""


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


def parse_follower_count(value) -> Optional[float]:
    text = normalize_text(value)
    if not text:
        return None
    compact = text.replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", compact)
    if not match:
        return None
    number = float(match.group(1))
    lower = compact.lower()
    if lower.endswith("m"):
        number *= 1_000_000
    elif lower.endswith("k"):
        number *= 1_000
    return number


def normalize_language(value, default_language: str) -> str:
    text = normalize_text(value)
    if not text:
        return default_language
    mapping = {
        "英语": "English",
        "英文": "English",
        "english": "English",
        "中文": "Chinese",
        "汉语": "Chinese",
        "chinese": "Chinese",
        "日语": "Japanese",
        "日文": "Japanese",
        "japanese": "Japanese",
    }
    return mapping.get(text.strip().lower(), text)


def pick_first(row: dict, *keys: str) -> str:
    for key in keys:
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    return ""


def extract_public_account_id(row: dict) -> str:
    for key in ("账号ID", "public_handle", "scrapecreators_handle"):
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    profile_url = normalize_text(row.get("profile_url", ""))
    handle_match = re.search(r"youtube\.com/(@[^/?#]+)", profile_url, re.I)
    if handle_match:
        return handle_match.group(1)
    creator_handle = normalize_text(row.get("creator_handle", ""))
    if creator_handle:
        return creator_handle
    return ""


def derive_tag_field(row: dict) -> str:
    for key in ("账号类目标签__平台抓取", "scrapecreators_tags", "content_tags_or_hashtags", "matched_queries"):
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    return ""


def derive_country(row: dict) -> str:
    for key in ("博主国家", "country", "country_include"):
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    return ""


def load_manifest_done_rows(manifest_csv: Path) -> tuple[set[str], set[str]]:
    emails: set[str] = set()
    row_ids: set[str] = set()
    with manifest_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            status = normalize_text(row.get("status", "")).lower()
            if status not in {"done", "sampled", "sent"}:
                continue
            email = normalize_text(row.get("to", "")).lower()
            row_id = normalize_text(row.get("row_id", ""))
            if email:
                emails.add(email)
            if row_id:
                row_ids.add(row_id)
    return emails, row_ids


EMAIL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._%+-]*@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)
BLOCKED_TLDS = {"avif", "gif", "jpeg", "jpg", "png", "svg", "webp"}
BLOCKED_EMAIL_DOMAINS = {"amazon.com", "cal.com", "companyco.com", "sentry.io", "skool.com", "wixpress.com"}


def pick_email_value(row: dict) -> str:
    return normalize_text(row.get("email", "")) or normalize_text(row.get("联系方式", "")) or normalize_text(row.get("contact_value", ""))


def is_plausible_outreach_email(value: str) -> bool:
    text = normalize_text(value).strip()
    if not text:
        return False
    if not EMAIL_RE.fullmatch(text):
        return False
    domain = text.split("@", 1)[1].lower()
    suffix = domain.rsplit(".", 1)[-1]
    if suffix in BLOCKED_TLDS:
        return False
    if domain in BLOCKED_EMAIL_DOMAINS or domain.endswith(".sentry.io"):
        return False
    return True


def load_source_rows(source_csv: Path, manifest_csv: Path | None) -> list[dict]:
    df = pd.read_csv(source_csv, encoding="utf-8-sig").fillna("")
    records = df.to_dict(orient="records")
    manifest_emails: set[str] = set()
    manifest_row_ids: set[str] = set()
    if manifest_csv:
        manifest_emails, manifest_row_ids = load_manifest_done_rows(manifest_csv)

    deduped: list[dict] = []
    seen: set[str] = set()
    for index_1_based, row in enumerate(records, start=2):
        if normalize_text(row.get("manual_clean_decision", "")).lower() == "drop":
            continue
        if normalize_text(row.get("email_qc_flag", "")).lower() in {"dirty", "invalid", "suspect"}:
            continue
        follower_count = parse_follower_count(pick_first(row, "followers_count", "粉丝数"))
        if follower_count is None or follower_count <= 1000:
            continue
        email = pick_email_value(row).lower()
        if not is_plausible_outreach_email(email):
            continue
        if manifest_csv and email not in manifest_emails and str(index_1_based) not in manifest_row_ids:
            continue
        key = normalize_key(row.get("profile_url", "")) or normalize_key(row.get("creator_handle", "")) or email
        if key in seen:
            continue
        seen.add(key)
        row["_source_row_id"] = str(index_1_based)
        deduped.append(row)
    return deduped


def project_row(source_row: dict, master_header: list, header_map: dict[str, list[int]], write_date: str, default_language: str) -> list[str]:
    output = [""] * len(master_header)

    projected = {
        "分区": write_date,
        "账号ID": extract_public_account_id(source_row),
        "频道/作者名称": pick_first(source_row, "display_name", "频道/作者名称"),
        "报价标准化": pick_first(source_row, "报价标准化"),
        "报价原文": pick_first(source_row, "报价原文"),
        "平台": pick_first(source_row, "platform", "平台") or "YouTube",
        "多平台标记": pick_first(source_row, "多平台标记"),
        "账号链接": pick_first(source_row, "profile_url", "账号链接"),
        "语言": normalize_language(pick_first(source_row, "language", "语言"), default_language),
        "博主国家": derive_country(source_row),
        "粉丝数": format_follower_count(pick_first(source_row, "followers_count", "粉丝数")),
        "账号类目标签__平台抓取": derive_tag_field(source_row),
        "置顶最高播放": format_follower_count(pick_first(source_row, "max_views", "置顶最高播放")) if pick_first(source_row, "max_views", "置顶最高播放") else "",
        "原价": pick_first(source_row, "原价"),
        "账号简介": pick_first(source_row, "bio", "账号简介"),
        "账号简介__平台抓取": pick_first(source_row, "bio", "账号简介__平台抓取", "账号简介"),
        "联系方式": pick_email_value(source_row),
        "联系方式备注": pick_first(source_row, "contact_note", "联系方式备注", "email_qc_flag"),
        "外链__平台抓取": pick_first(source_row, "external_links", "外链__平台抓取"),
    }

    for field_name, field_value in projected.items():
        for idx in header_map.get(field_name, []):
            output[idx] = field_value

    for field_name in MAIL1_SENT_FIELD_CANDIDATES:
        for idx in header_map.get(field_name, []):
            output[idx] = "Y"
    for field_name in MAIL1_REPLY_FIELD_CANDIDATES:
        for idx in header_map.get(field_name, []):
            output[idx] = ""
    return output


def find_append_start_row(values: list[list]) -> int:
    last_non_empty = 0
    for idx, row in enumerate(values, start=1):
        if any(normalize_text(cell) for cell in row):
            last_non_empty = idx
    return last_non_empty + 1


def export_backup_xlsx(output_dir: Path, values: list[list]) -> dict:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = output_dir / f"feishu_mail1_master_backup_{timestamp}.xlsx"
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


def write_preview_csv(path: Path, header: list, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([normalize_text(cell) for cell in header])
        writer.writerows(rows)


def write_error_report(path: Path, args: argparse.Namespace, exc: Exception) -> None:
    payload = {
        "workflow": "WF_feishu_Gmail_Mail1_append",
        "mode": args.mode,
        "source_csv": args.source_csv,
        "draft_manifest_csv": args.draft_manifest_csv,
        "target_url": args.target_url,
        "sheet_id": args.sheet_id,
        "sheet_title": args.sheet_title,
        "write_date": args.write_date,
        "source_date": args.source_date,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_stats(values: list[list], header_map: dict[str, list[int]], appended_rows: list[list[str]]) -> dict:
    account_idx = header_map.get("账号ID", [None])[0]
    sent_field = first_present_header(header_map, *MAIL1_SENT_FIELD_CANDIDATES)
    reply_field = first_present_header(header_map, *MAIL1_REPLY_FIELD_CANDIDATES)
    sent_idx = header_map.get(sent_field, [None])[0] if sent_field else None
    reply_idx = header_map.get(reply_field, [None])[0] if reply_field else None

    total_accounts = 0
    total_sent = 0
    total_replied = 0
    for row in values[1:]:
        account = normalize_text(row[account_idx]) if account_idx is not None and account_idx < len(row) else ""
        sent = normalize_text(row[sent_idx]) if sent_idx is not None and sent_idx < len(row) else ""
        replied = normalize_text(row[reply_idx]) if reply_idx is not None and reply_idx < len(row) else ""
        if account:
            total_accounts += 1
        if sent.upper() == "Y":
            total_sent += 1
        if replied.upper() == "Y":
            total_replied += 1

    today_new_accounts = len(appended_rows)
    today_new_sent = 0
    today_new_replied = 0
    for row in appended_rows:
        if sent_idx is not None and sent_idx < len(row) and normalize_text(row[sent_idx]).upper() == "Y":
            today_new_sent += 1
        if reply_idx is not None and reply_idx < len(row) and normalize_text(row[reply_idx]).upper() == "Y":
            today_new_replied += 1

    return {
        "表格一共多少账号": total_accounts,
        "今日新增多少账号": today_new_accounts,
        "Mail1发送 一共多少": total_sent,
        "Mail1发送 今日新增多少": today_new_sent,
        "Mail1 回复 一共多少": total_replied,
        "Mail1 回复 今日新增多少": today_new_replied,
    }


def verify_rows(refreshed_values: list[list], header_map: dict[str, list[int]], start_row: int, staged_rows: list[list[str]]) -> list[dict]:
    sent_field = first_present_header(header_map, *MAIL1_SENT_FIELD_CANDIDATES)
    verification = []
    for row_num in range(start_row, start_row + min(len(staged_rows), 20)):
        row = refreshed_values[row_num - 1] if row_num - 1 < len(refreshed_values) else []
        verification.append(
            {
                "row": row_num,
                "账号ID": normalize_text(row[header_map["账号ID"][0]]) if header_map.get("账号ID") and header_map["账号ID"][0] < len(row) else "",
                "频道/作者名称": normalize_text(row[header_map["频道/作者名称"][0]]) if header_map.get("频道/作者名称") and header_map["频道/作者名称"][0] < len(row) else "",
                "Mail1发送": normalize_text(row[header_map[sent_field][0]]) if sent_field and header_map[sent_field][0] < len(row) else "",
                "联系方式": normalize_text(row[header_map["联系方式"][0]]) if header_map.get("联系方式") and header_map["联系方式"][0] < len(row) else "",
            }
        )
    return verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Append confirmed Gmail Mail1 rows into a Feishu master sheet.")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--draft-manifest-csv", default="", help="Optional draft manifest used to filter only confirmed drafted rows.")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--write-date", default=dt.date.today().isoformat(), help="Date written into Feishu column `分区`; should be the actual sync/write date.")
    parser.add_argument("--source-date", default="", help="Optional source batch date for audit context only; not written into Feishu `分区`.")
    parser.add_argument("--default-language", default="English")
    args = parser.parse_args()

    source_csv = Path(args.source_csv).expanduser().resolve()
    draft_manifest_csv = Path(args.draft_manifest_csv).expanduser().resolve() if args.draft_manifest_csv else None
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    error_json = output_dir / "feishu_mail1_append_error.json"

    try:
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
        missing_columns = sorted(
            col
            for col in {"账号ID", "频道/作者名称", "账号链接", "联系方式"}
            if col not in header_map
        )
        if not first_present_header(header_map, *MAIL1_SENT_FIELD_CANDIDATES):
            missing_columns.append("Mail1发送列")
        if not first_present_header(header_map, *MAIL1_REPLY_FIELD_CANDIDATES):
            missing_columns.append("Mail1回复列")
        if missing_columns:
            raise RuntimeError(f"Target sheet missing required columns: {missing_columns}")

        existing_ids, existing_urls = build_existing_sets(values, header_map)
        source_rows = load_source_rows(source_csv, draft_manifest_csv)

        staged_rows = []
        skipped_rows = []
        for row in source_rows:
            account_id = normalize_key(extract_public_account_id(row))
            account_url = normalize_key(row.get("profile_url", "")) or normalize_key(row.get("账号链接", ""))
            if (account_id and account_id in existing_ids) or (account_url and account_url in existing_urls):
                skipped_rows.append(
                    {
                        "账号ID": extract_public_account_id(row),
                        "频道/作者名称": normalize_text(row.get("display_name", "")),
                        "联系方式": normalize_text(row.get("email", "")),
                        "reason": "exists_in_target",
                    }
                )
                continue
            projected = project_row(row, master_header, header_map, args.write_date, args.default_language)
            staged_rows.append(projected)
            if account_id:
                existing_ids.add(account_id)
            if account_url:
                existing_urls.add(account_url)

        append_start_row = find_append_start_row(values)
        preview_csv = output_dir / "feishu_mail1_append_preview.csv"
        preview_json = output_dir / "feishu_mail1_append_preview.json"
        audit_json = output_dir / "feishu_mail1_append_audit.json"
        write_preview_csv(preview_csv, master_header, staged_rows)
        preview_json.write_text(
            json.dumps(
                {
                    "source_csv": str(source_csv),
                    "draft_manifest_csv": str(draft_manifest_csv) if draft_manifest_csv else "",
                    "target_url": args.target_url,
                    "sheet_id": sheet_id,
                    "sheet_title": sheet_title,
                    "mode": args.mode,
                    "write_date": args.write_date,
                    "source_date": args.source_date,
                    "append_start_row": append_start_row,
                    "source_eligible_rows": len(source_rows),
                    "staged_count": len(staged_rows),
                    "skipped_count": len(skipped_rows),
                    "rows_preview": staged_rows[:10],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        backup_result = None
        append_result = None
        if args.mode == "apply" and staged_rows:
            backup_result = export_backup_xlsx(output_dir, values)
            append_result = append_rows(spreadsheet_token, sheet_id, append_start_row, staged_rows)

        _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(spreadsheet_token, sheet_id=sheet_id)
        refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count)
        stats = compute_stats(refreshed_values, header_map, staged_rows if args.mode == "apply" else [])
        verification = []
        if args.mode == "apply" and staged_rows:
            verification = verify_rows(refreshed_values, header_map, append_start_row, staged_rows)

        audit = {
            "source_csv": str(source_csv),
            "draft_manifest_csv": str(draft_manifest_csv) if draft_manifest_csv else "",
            "target_url": args.target_url,
            "sheet_id": sheet_id,
            "sheet_title": sheet_title,
            "mode": args.mode,
            "write_date": args.write_date,
            "source_date": args.source_date,
            "target_rows_before": row_count,
            "target_rows_after": refreshed_row_count,
            "target_columns": column_count,
            "source_eligible_rows": len(source_rows),
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
        if error_json.exists():
            error_json.unlink()
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    except Exception as exc:
        write_error_report(error_json, args, exc)
        raise


if __name__ == "__main__":
    main()
