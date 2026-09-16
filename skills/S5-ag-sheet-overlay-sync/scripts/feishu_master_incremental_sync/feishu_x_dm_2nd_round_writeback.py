#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from feishu_x_target_config import get_x_target_defaults
from feishu_master_partial_overlay_writeback import extract_spreadsheet_token, fetch_values, normalize_text, select_sheet_meta

DEFAULTS = get_x_target_defaults()
DEFAULT_TARGET_URL = DEFAULTS["target_url"]
DEFAULT_SHEET_ID = DEFAULTS["sheet_id"]
DEFAULT_SHEET_TITLE = DEFAULTS["sheet_title"]


def compute_second_round_stats(values: list[list]) -> dict[str, int]:
    header = [normalize_text(cell) for cell in values[0]] if values else []
    header_map = {name: idx for idx, name in enumerate(header)}
    account_idx = header_map.get("账号ID")
    second_round_idx = header_map.get("DM二次发送状态")

    stats = {
        "表格名单总数": 0,
        "二轮状态已写入总数": 0,
        "二轮发送成功总数": 0,
        "二轮 DM 未开通总数": 0,
    }
    if account_idx is None or second_round_idx is None:
        return stats

    for row in values[1:]:
        account = normalize_text(row[account_idx]) if account_idx < len(row) else ""
        second_round = normalize_text(row[second_round_idx]) if second_round_idx < len(row) else ""
        if account:
            stats["表格名单总数"] += 1
        if second_round:
            stats["二轮状态已写入总数"] += 1
        if second_round == "Y":
            stats["二轮发送成功总数"] += 1
        if second_round == "DM 未开通":
            stats["二轮 DM 未开通总数"] += 1
    return stats


def build_business_summary(summary_date: str, stats: dict[str, int], today_new_written: int) -> str:
    return "\n".join(
        [
            f"今日 X-DM 二轮写回 - {summary_date}",
            f"表格名单总数：{stats['表格名单总数']}",
            f"二轮状态已写入总数：{stats['二轮状态已写入总数']}",
            f"二轮状态今日新增写入：{today_new_written}",
            f"二轮发送成功总数：{stats['二轮发送成功总数']}",
            f"二轮 DM 未开通总数：{stats['二轮 DM 未开通总数']}",
        ]
    )


def build_technical_summary(result: dict) -> str:
    return "\n".join(
        [
            "技术摘要：",
            f"源表行数：{result.get('source_rows', 0)}",
            f"命中 Feishu 行数：{result.get('matched_rows', 0)}",
            f"实际变更行数：{result.get('changed_rows', 0)}",
            f"实际变更单元格数：{result.get('changed_cells', 0)}",
            f"未命中数量：{result.get('unmatched_count', 0)}",
            f"歧义匹配数量：{result.get('ambiguous_count', 0)}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write local DM二次发送状态 values back into existing Feishu master rows."
    )
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL)
    parser.add_argument("--sheet-id", default=DEFAULT_SHEET_ID)
    parser.add_argument("--sheet-title", default=DEFAULT_SHEET_TITLE)
    args = parser.parse_args()

    script_path = Path(__file__).with_name("feishu_master_partial_overlay_writeback.py")
    cmd = [
        sys.executable,
        str(script_path),
        "--source-csv",
        args.source_csv,
        "--target-url",
        args.target_url,
        "--sheet-id",
        args.sheet_id,
        "--mode",
        args.mode,
        "--output-dir",
        args.output_dir,
        "--write-columns",
        "DM二次发送状态",
    ]
    if args.sheet_title:
        cmd.extend(["--sheet-title", args.sheet_title])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        raise SystemExit(result.returncode)

    payload = json.loads(result.stdout)
    spreadsheet_token = extract_spreadsheet_token(args.target_url)
    sheet_id, sheet_title, row_count, column_count = select_sheet_meta(
        spreadsheet_token,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
    )
    values = fetch_values(spreadsheet_token, sheet_id, row_count, column_count)
    stats = compute_second_round_stats(values)
    today_new_written = int(payload.get("changed_rows", 0)) if args.mode == "apply" else 0

    enriched = {
        **payload,
        "stats": stats | {"二轮状态今日新增写入": today_new_written},
        "output_expression": [
            "今日 X-DM 二轮写回 - YYYY-MM-DD",
            "表格名单总数：",
            "二轮状态已写入总数：",
            "二轮状态今日新增写入：",
            "二轮发送成功总数：",
            "二轮 DM 未开通总数：",
        ],
        "business_summary": build_business_summary(dt.datetime.now().strftime("%Y-%m-%d"), stats, today_new_written),
        "technical_summary": build_technical_summary(payload),
    }
    print(json.dumps(enriched, ensure_ascii=False, indent=2))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
