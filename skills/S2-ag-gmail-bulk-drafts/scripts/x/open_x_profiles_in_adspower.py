#!/usr/bin/env python3
"""
Open X profile URLs from the Rockbase S2 cold DM sheet inside an AdsPower profile.

Workflow:
1. Read target rows from the CSV.
2. Reuse an active AdsPower profile if available.
3. Otherwise start the target profile through the local AdsPower API.
4. Connect to the returned debug port with Playwright CDP.
5. Open each X URL in order and print the opened order as JSON lines.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Dict, List, Sequence
from urllib import error, parse, request

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import read_csv_rows


DEFAULT_API_BASE = "http://127.0.0.1:50325"
DEFAULT_USER_ID = "k19xcq1m"
DEFAULT_API_TIMEOUT = 30
DEFAULT_PAGE_TIMEOUT_MS = 60000


def api_get_json(url: str, timeout: int = DEFAULT_API_TIMEOUT) -> dict:
    with request.urlopen(url, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def get_active_profile(api_base: str, user_id: str, timeout: int) -> dict | None:
    payload = api_get_json(f"{api_base}/api/v1/browser/local-active", timeout=timeout)
    items = payload.get("data", {}).get("list", [])
    for item in items:
        if item.get("user_id") == user_id:
            return item
    return None


def start_profile(api_base: str, user_id: str, timeout: int) -> dict:
    query = parse.urlencode({"user_id": user_id})
    payload = api_get_json(f"{api_base}/api/v1/browser/start?{query}", timeout=timeout)
    data = payload.get("data", {})
    if not data:
        raise RuntimeError(f"AdsPower start returned no data: {payload}")
    return data


def ensure_profile(api_base: str, user_id: str, timeout: int) -> dict:
    active = get_active_profile(api_base, user_id, timeout)
    if active:
        return active
    return start_profile(api_base, user_id, timeout)


def parse_rows_arg(raw: str) -> List[int]:
    values: List[int] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        values.append(int(piece))
    return values


def collect_targets(
    rows: Sequence[Dict[str, str]],
    start_row: int,
    count: int,
    explicit_rows: Sequence[int] | None,
) -> List[Dict[str, str]]:
    targets: List[Dict[str, str]] = []
    requested = set(explicit_rows or [])
    for idx, row in enumerate(rows):
        sheet_row_number = idx + 2
        if requested:
            if sheet_row_number not in requested:
                continue
        else:
            if sheet_row_number < start_row:
                continue
            if len(targets) >= count:
                break
        url = (row.get("账号链接", "") or "").strip()
        if not url:
            raise ValueError(f"row {sheet_row_number}: empty 账号链接")
        targets.append(
            {
                "sheet_row_number": sheet_row_number,
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "账号链接": url,
            }
        )
    if requested:
        found = {item["sheet_row_number"] for item in targets}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"missing requested rows: {missing}")
        targets.sort(key=lambda item: item["sheet_row_number"])
    return targets


async def open_targets(debug_port: str, targets: Sequence[Dict[str, str]], page_timeout_ms: int) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        for item in targets:
            page = await context.new_page()
            await page.goto(item["账号链接"], wait_until="domcontentloaded", timeout=page_timeout_ms)
            print(
                json.dumps(
                    {
                        "sheet_row_number": item["sheet_row_number"],
                        "账号ID": item["账号ID"],
                        "频道/作者名称": item["频道/作者名称"],
                        "opened": item["账号链接"],
                    },
                    ensure_ascii=False,
                )
            )
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Open X profile rows inside AdsPower via local API + CDP.")
    parser.add_argument("--input", required=True, help="Source CSV path.")
    parser.add_argument("--start-row", type=int, default=2, help="Start from this sheet row number.")
    parser.add_argument("--count", type=int, default=5, help="How many consecutive rows to open.")
    parser.add_argument("--rows", default="", help="Optional explicit sheet row numbers, comma-separated.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"AdsPower local API base. Default: {DEFAULT_API_BASE}")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help=f"AdsPower profile user_id. Default: {DEFAULT_USER_ID}")
    parser.add_argument("--api-timeout", type=int, default=DEFAULT_API_TIMEOUT, help=f"API timeout seconds. Default: {DEFAULT_API_TIMEOUT}")
    parser.add_argument("--page-timeout-ms", type=int, default=DEFAULT_PAGE_TIMEOUT_MS, help=f"Per-page timeout in milliseconds. Default: {DEFAULT_PAGE_TIMEOUT_MS}")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    _, rows = read_csv_rows(input_path)
    explicit_rows = parse_rows_arg(args.rows) if args.rows else None
    targets = collect_targets(rows, args.start_row, args.count, explicit_rows)
    if not targets:
        raise SystemExit("no target rows selected")

    try:
        profile = ensure_profile(args.api_base, args.user_id, args.api_timeout)
    except error.URLError as exc:
        raise SystemExit(
            "failed to reach AdsPower local API. "
            f"Check whether AdsPower local API is enabled at {args.api_base}. "
            f"Original error: {exc}"
        ) from exc

    debug_port = str(profile.get("debug_port", "")).strip()
    if not debug_port:
        raise SystemExit(f"AdsPower profile returned no debug_port: {profile}")

    print(
        json.dumps(
            {
                "input": str(input_path),
                "user_id": args.user_id,
                "debug_port": debug_port,
                "selected_rows": [item["sheet_row_number"] for item in targets],
                "selected_handles": [item["账号ID"] for item in targets],
            },
            ensure_ascii=False,
        )
    )
    asyncio.run(open_targets(debug_port, targets, args.page_timeout_ms))


if __name__ == "__main__":
    main()
