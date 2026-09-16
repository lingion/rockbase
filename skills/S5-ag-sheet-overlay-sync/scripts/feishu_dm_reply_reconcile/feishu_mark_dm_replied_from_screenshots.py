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


DEFAULT_SCREENSHOT_NAMES = []
DEFAULT_EVIDENCE_MODE = "manual_name_list"


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


def normalize_name(value: str) -> str:
    text = normalize_text(value).lower()
    text = text.replace("&", "and")
    text = text.replace("|", " ")
    text = text.replace(",", " ")
    text = re.sub(r"\bphd\b", "", text)
    text = re.sub(r"[@._\\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff ]+", "", text)
    text = re.sub(r"\s+", "", text)
    return text


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


def compute_sheet_stats(values: list[list], reply_column: str) -> dict[str, int]:
    header = [normalize_text(cell) for cell in values[0]]
    idx = {name: i for i, name in enumerate(header)}
    account_idx = idx["账号ID"]
    sent_idx = idx["DM 发送状态"]
    reply_idx = idx[reply_column]

    counts = {
        "表格名单总数": 0,
        "已发送 DM总数": 0,
        "DM 未开通数量": 0,
        "DM 已回复总数": 0,
    }
    for row in values[1:]:
        account = normalize_text(row[account_idx]) if account_idx < len(row) else ""
        sent = normalize_text(row[sent_idx]) if sent_idx < len(row) else ""
        replied = normalize_text(row[reply_idx]) if reply_idx < len(row) else ""
        if account:
            counts["表格名单总数"] += 1
        if sent.upper() == "Y":
            counts["已发送 DM总数"] += 1
        if sent == "DM 未开通":
            counts["DM 未开通数量"] += 1
        if replied.upper() == "Y":
            counts["DM 已回复总数"] += 1
    return counts


def build_business_summary(
    summary_date: str,
    sheet_stats: dict[str, int],
    today_new_sent: int,
    today_new_reply: int,
    reply_column: str,
) -> str:
    # Fixed user-facing wording:
    # - sent count includes only DM 发送状态 = Y
    # - DM 未开通 is tracked separately and must not be merged into sent total
    reply_total_label = "DM 已回复总数"
    reply_new_label = "DM 已回复今日新增"
    summary_title = "今日 X-DM 状态更新"
    if reply_column == "DM二次回复状态":
        reply_total_label = "DM 二次回复总数"
        reply_new_label = "DM 二次回复今日新增"
        summary_title = "今日 X-DM 二次回复状态更新"
    return "\n".join(
        [
            f"{summary_title} - {summary_date}",
            f"表格名单总数：{sheet_stats['表格名单总数']}",
            f"已发送 DM总数：{sheet_stats['已发送 DM总数']}",
            f"已发送 DM今日新增：{today_new_sent}",
            f"{reply_total_label}：{sheet_stats['DM 已回复总数']}",
            f"{reply_new_label}：{today_new_reply}",
        ]
    )


def build_technical_summary(
    *,
    screenshot_name_count: int,
    matched_count: int,
    already_y_count: int,
    new_y_count: int,
    unmatched_count: int,
    ambiguous_count: int,
) -> str:
    return "\n".join(
        [
            "技术摘要：",
            f"截图名字总数：{screenshot_name_count}",
            f"命中 master 数量：{matched_count}",
            f"本来已经是 Y 的数量：{already_y_count}",
            f"今日新写入 Y 的数量：{new_y_count}",
            f"未命中数量：{unmatched_count}",
            f"歧义匹配数量：{ambiguous_count}",
        ]
    )


def build_run_verdict(
    *,
    mode: str,
    planned_new_y_count: int,
    already_y_count: int,
    unmatched_count: int,
    ambiguous_count: int,
) -> str:
    if ambiguous_count > 0:
        return (
            f"Run Verdict: 暂不建议自动写入。当前有 {ambiguous_count} 个歧义匹配，"
            "应先人工复核后再 apply。"
        )
    if mode == "dry-run":
        if planned_new_y_count == 0 and unmatched_count > 0:
            return (
                f"Run Verdict: 无需 apply。当前没有新的 `DM 回复状态 = Y` 需要写入，"
                f"但仍有 {unmatched_count} 个未命中名字建议人工复核。"
            )
        if unmatched_count > 0:
            return (
                f"Run Verdict: 可以 apply，但建议先看一眼 {unmatched_count} 个未命中名字。"
                f"当前预计新写入 {planned_new_y_count} 个 `DM 回复状态 = Y`。"
            )
        if planned_new_y_count == 0 and already_y_count > 0:
            return "Run Verdict: 无需 apply。命中的名字都已经是 `DM 回复状态 = Y`。"
        return (
            f"Run Verdict: 可以安全 apply。当前无歧义匹配，预计新写入 "
            f"{planned_new_y_count} 个 `DM 回复状态 = Y`。"
        )
    if planned_new_y_count == 0 and already_y_count > 0:
        return "Run Verdict: 本次无需新增写入，命中的名字此前已经回填过。"
    if unmatched_count > 0:
        return (
            f"Run Verdict: 已完成写入，另有 {unmatched_count} 个未命中名字未被回填，"
            "建议后续单独核对昵称漂移或主表缺失。"
        )
    return f"Run Verdict: 已完成写入，本次新增回填 {planned_new_y_count} 个 `DM 回复状态 = Y`。"


def export_backup_xlsx(spreadsheet_token: str, output_dir: Path, values: list[list]) -> dict:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = output_dir / f"feishu_master_reply_status_backup_{timestamp}.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Master"
    max_cols = max((len(row) for row in values), default=0)
    for row in values:
        padded = row + [""] * (max_cols - len(row))
        worksheet.append([normalize_text(cell) for cell in padded])
    workbook.save(backup_path)
    return {
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


def resolve_reply_column_idx(
    values: list[list],
    header: list[str],
    reply_column: str,
    *,
    allow_create: bool,
) -> tuple[int, bool]:
    idx = {name: i for i, name in enumerate(header)}
    if reply_column in idx:
        return idx[reply_column], False
    if not allow_create:
        raise KeyError(f"Reply column not found: {reply_column}")
    for i, name in enumerate(header):
        if normalize_text(name) == "":
            return i, True
    raise RuntimeError(
        f"Reply column {reply_column!r} not found and there is no blank header slot available."
    )


def build_row_index(values: list[list], header: list[str], reply_column: str) -> tuple[dict[str, list[dict]], int]:
    idx = {name: i for i, name in enumerate(header)}
    name_idx = idx["频道/作者名称"]
    account_idx = idx["账号ID"]
    reply_idx = idx[reply_column]
    index: dict[str, list[dict]] = {}
    for row_num, row in enumerate(values[1:], start=2):
        author = normalize_text(row[name_idx]) if name_idx < len(row) else ""
        account = normalize_text(row[account_idx]) if account_idx < len(row) else ""
        reply = normalize_text(row[reply_idx]) if reply_idx < len(row) else ""
        keys = {normalize_name(author), normalize_name(account.lstrip("@"))}
        for key in keys:
            if not key:
                continue
            index.setdefault(key, []).append(
                {
                    "row": row_num,
                    "频道/作者名称": author,
                    "账号ID": account,
                    "DM 回复状态": reply,
                }
            )
    return index, reply_idx


def load_names(args) -> list[str]:
    names: list[str] = []
    if getattr(args, "name", None):
        names.extend(args.name)
    if getattr(args, "names_file", ""):
        path = Path(args.names_file).expanduser().resolve()
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                names.append(text)
    if getattr(args, "names_json", ""):
        path = Path(args.names_json).expanduser().resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("--names-json must point to a JSON array of names")
        for item in payload:
            text = normalize_text(item)
            if text:
                names.append(text)
    if not names:
        names = list(DEFAULT_SCREENSHOT_NAMES)

    deduped = []
    seen = set()
    for item in names:
        text = normalize_text(item)
        if not text:
            continue
        key = normalize_name(text)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def load_same_day_send_increment(output_dir: Path) -> int:
    audit_path = output_dir / "feishu_master_append_audit.json"
    if not audit_path.exists():
        return 0
    try:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    stats = payload.get("stats") or {}
    raw_value = stats.get("已发送 DM 数量今日新增多少", 0)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark DM reply status from screenshot names")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--evidence-mode",
        choices=["inbox_list", "thread_detail", "manual_name_list"],
        default=DEFAULT_EVIDENCE_MODE,
        help="how the names were derived; affects workflow semantics and reporting",
    )
    parser.add_argument("--name", action="append", default=[], help="single screenshot/extracted name; can be passed multiple times")
    parser.add_argument("--names-file", default="", help="UTF-8 text file with one name per line")
    parser.add_argument("--names-json", default="", help="JSON file containing an array of names")
    parser.add_argument("--reply-column", default="DM 回复状态", help="reply status column to write back")
    parser.add_argument(
        "--create-reply-column-if-missing",
        action="store_true",
        help="create the reply column by occupying the first blank header cell when missing",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    same_day_send_increment = load_same_day_send_increment(output_dir)
    input_names = load_names(args)
    if not input_names:
        raise ValueError("No names provided. Use --name, --names-file, or --names-json.")

    spreadsheet_token = extract_spreadsheet_token(args.target_url)
    sheet_id, sheet_title, row_count, column_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
    )

    values = fetch_values(spreadsheet_token, sheet_id, row_count, column_count)
    header = [normalize_text(cell) for cell in values[0]]
    reply_idx, created_reply_column = resolve_reply_column_idx(
        values,
        header,
        args.reply_column,
        allow_create=args.create_reply_column_if_missing,
    )
    if created_reply_column:
        header[reply_idx] = args.reply_column
        values[0][reply_idx] = args.reply_column
    row_index, reply_idx = build_row_index(values, header, args.reply_column)

    matched = []
    already_y = []
    updated = []
    unmatched = []
    ambiguous = []

    seen_rows = set()
    for raw_name in input_names:
        key = normalize_name(raw_name)
        hits = row_index.get(key, [])
        if not hits:
            unmatched.append(raw_name)
            continue
        if len(hits) > 1:
            unresolved = [h for h in hits if h["row"] not in seen_rows]
            if len(unresolved) > 1:
                ambiguous.append({"screenshot_name": raw_name, "matches": unresolved})
                continue
            hits = unresolved or hits[:1]
        hit = hits[0]
        seen_rows.add(hit["row"])
        matched.append({"screenshot_name": raw_name, **hit})
        if normalize_text(hit["DM 回复状态"]).upper() == "Y":
            already_y.append({"screenshot_name": raw_name, **hit})
        elif normalize_text(hit["DM 回复状态"]) == "":
            updated.append({"screenshot_name": raw_name, **hit})

    backup_result = None
    write_results = []
    if args.mode == "apply" and updated:
        backup_result = export_backup_xlsx(spreadsheet_token, output_dir, values)
        if created_reply_column:
            write_results.append(
                {
                    "row": 1,
                    "column": args.reply_column,
                    "result": write_cell(spreadsheet_token, sheet_id, 1, reply_idx, args.reply_column),
                }
            )
        for item in updated:
            write_results.append(
                {
                    "row": item["row"],
                    "账号ID": item["账号ID"],
                    "result": write_cell(spreadsheet_token, sheet_id, item["row"], reply_idx, "Y"),
                }
            )

    refreshed_values = values
    if args.mode == "apply":
        _, _, refreshed_row_count, refreshed_col_count = select_sheet_meta(
            spreadsheet_token,
            sheet_id=sheet_id,
        )
        refreshed_values = fetch_values(spreadsheet_token, sheet_id, refreshed_row_count, refreshed_col_count)

    refreshed_header = [normalize_text(cell) for cell in refreshed_values[0]]
    refreshed_idx = {name: i for i, name in enumerate(refreshed_header)}
    verification = []
    for item in updated[:20]:
        row = refreshed_values[item["row"] - 1] if item["row"] - 1 < len(refreshed_values) else []
        verification.append(
            {
                "row": item["row"],
                "screenshot_name": item["screenshot_name"],
                "账号ID": normalize_text(row[refreshed_idx["账号ID"]]) if refreshed_idx["账号ID"] < len(row) else "",
                "频道/作者名称": normalize_text(row[refreshed_idx["频道/作者名称"]]) if refreshed_idx["频道/作者名称"] < len(row) else "",
                args.reply_column: normalize_text(row[refreshed_idx[args.reply_column]]) if refreshed_idx[args.reply_column] < len(row) else "",
            }
        )

    sheet_stats = compute_sheet_stats(refreshed_values, args.reply_column)
    business_summary = build_business_summary(
        dt.datetime.now().strftime("%Y-%m-%d"),
        sheet_stats=sheet_stats,
        today_new_sent=same_day_send_increment,
        today_new_reply=len(updated) if args.mode == "apply" else 0,
        reply_column=args.reply_column,
    )
    technical_summary = build_technical_summary(
        screenshot_name_count=len(input_names),
        matched_count=len(matched),
        already_y_count=len(already_y),
        new_y_count=len(updated) if args.mode == "apply" else len(updated),
        unmatched_count=len(unmatched),
        ambiguous_count=len(ambiguous),
    )
    run_verdict = build_run_verdict(
        mode=args.mode,
        planned_new_y_count=len(updated),
        already_y_count=len(already_y),
        unmatched_count=len(unmatched),
        ambiguous_count=len(ambiguous),
    )

    result = {
        "target_url": args.target_url,
        "sheet_id": sheet_id,
        "sheet_title": sheet_title,
        "mode": args.mode,
        "evidence_mode": args.evidence_mode,
        "reply_column": args.reply_column,
        "reply_column_created": created_reply_column,
        "screenshot_name_count": len(input_names),
        "matched_count": len(matched),
        "already_y_count": len(already_y),
        "today_new_y_count": len(updated) if args.mode == "apply" else 0,
        "planned_new_y_count": len(updated),
        "unmatched_count": len(unmatched),
        "ambiguous_count": len(ambiguous),
        "backup_result": backup_result,
        "updated_examples": updated[:20],
        "already_y_examples": already_y[:20],
        "unmatched_examples": unmatched[:20],
        "ambiguous_examples": ambiguous[:10],
        "verification_sample": verification,
        "stats_method": {
            "表格名单总数": "target sheet中账号ID非空的总行数",
            "已发送 DM总数": "target sheet中DM 发送状态 = Y 的总行数，不含DM 未开通",
            "已发送 DM今日新增": "同日send sync新增的DM 发送状态 = Y 数量；优先从output-dir中的feishu_master_append_audit.json继承，缺失时返回0",
            "DM 已回复总数": f"本次执行后 target sheet中{args.reply_column} = Y 的总行数",
            "DM 已回复今日新增": f"本次执行中从空白写成Y的{args.reply_column}数量",
        },
        "output_expression": [
            "今日 X-DM 状态更新 - YYYY-MM-DD",
            "表格名单总数：",
            "已发送 DM总数：",
            "已发送 DM今日新增：",
            "DM 已回复总数：",
            "DM 已回复今日新增：",
        ],
        "business_summary": business_summary,
        "technical_summary": technical_summary,
        "run_verdict": run_verdict,
        "business_summary_context": {
            "DM 未开通数量": sheet_stats["DM 未开通数量"],
            "note": "DM 未开通数量单独统计，不并入已发送 DM总数",
        },
        "evidence_mode_note": {
            "inbox_list": "X DM 会话列表中的名字按回复候选处理，不再按预览里的 You: 二次否定。",
            "thread_detail": "单条会话截图只应传入明确有对方回复证据的名字。",
            "manual_name_list": "外部已整理好的名字列表，脚本按回复候选处理。",
        }[args.evidence_mode],
    }

    report_path = output_dir / "feishu_mark_dm_replied_from_screenshots_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
