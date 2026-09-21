from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv


GLOBAL_ENV = Path("${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env")
BASE_URL = "https://api.scrapecreators.com/v1/instagram/profile"
PLATFORM = "Instagram"


def load_api_env() -> Optional[str]:
    if GLOBAL_ENV.exists():
        load_dotenv(GLOBAL_ENV, override=True)
        return str(GLOBAL_ENV)
    load_dotenv(override=True)
    return None


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Instagram profile data from ScrapeCreators API into workbench JSON.")
    parser.add_argument("--csv", required=True, help="Target S1 CSV path")
    parser.add_argument("--rows", default="", help="Comma-separated physical row numbers to fetch")
    parser.add_argument("--limit", type=int, default=20, help="Max Instagram rows when --rows is empty")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Workbench date folder")
    parser.add_argument("--prefix", default="instagram_scrapecreators_batch", help="Output filename prefix")
    parser.add_argument("--delay-seconds", type=float, default=0.35, help="Delay between API requests")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="Per-request timeout")
    parser.add_argument("--api-key", default="", help="ScrapeCreators API key. Overrides SCRAPECREATORS_API_KEY env.")
    return parser


def parse_args() -> argparse.Namespace:
    return _build_argparser().parse_args()


def workbench_root(csv_path: Path, date_str: str) -> Path:
    root = csv_path.resolve().parents[2]
    return root / "workbench" / date_str


def parse_rows(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def extract_handle(url: str, fallback_handle: str) -> str:
    match = re.search(r"instagram\.com/([^/?#]+)", url)
    if match:
        return match.group(1).strip()
    return clean_text(fallback_handle).lstrip("@")


def row_snapshot(row_no: int, row: pd.Series) -> dict[str, str]:
    return {
        "row": row_no,
        "platform": clean_text(row.get("平台")),
        "handle": clean_text(row.get("账号ID")),
        "author_name": clean_text(row.get("频道/作者名称")),
        "url": clean_text(row.get("账号链接")),
        "followers": clean_text(row.get("粉丝数")),
        "contact": clean_text(row.get("联系方式")),
        "contact_note": clean_text(row.get("联系方式备注")),
        "external_links": clean_text(row.get("外链__平台抓取")),
        "bio": clean_text(row.get("账号简介__平台抓取")),
    }


def select_rows(df: pd.DataFrame, requested_rows: list[int], limit: int) -> list[tuple[int, pd.Series]]:
    selected: list[tuple[int, pd.Series]] = []
    if requested_rows:
        for row_no in requested_rows:
            idx = row_no - 1
            if idx < 0 or idx >= len(df):
                continue
            row = df.iloc[idx]
            if clean_text(row.get("平台")) != PLATFORM:
                continue
            selected.append((row_no, row))
        return selected

    for idx, row in df.iterrows():
        if clean_text(row.get("平台")) != PLATFORM:
            continue
        selected.append((idx + 1, row))
        if len(selected) >= limit:
            break
    return selected


def extract_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text or "", re.I)
    return match.group(0) if match else ""


def is_usable_payload(http_status: int, payload: object) -> bool:
    if http_status != 200 or not isinstance(payload, dict):
        return False
    if not payload.get("success"):
        return False
    user = payload.get("data", {}).get("user", {})
    if not isinstance(user, dict):
        return False
    if payload.get("accountDoesNotExist") or payload.get("errorStatus") == 404:
        return False
    return bool(user.get("username") or user.get("full_name"))


def main() -> None:
    args = parse_args()
    env_source = load_api_env()
    api_key = args.api_key or os.getenv("SCRAPECREATORS_API_KEY")
    if not api_key:
        raise RuntimeError(f"SCRAPECREATORS_API_KEY 未找到，env_source={env_source}")

    csv_path = Path(args.csv).expanduser().resolve()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    rows = select_rows(df, parse_rows(args.rows), args.limit)

    output_dir = workbench_root(csv_path, args.date)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S_%f")
    raw_path = output_dir / f"{args.prefix}_{timestamp}_raw.json"
    summary_path = output_dir / f"{args.prefix}_{timestamp}_summary.json"

    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    raw_items = []
    summary_items = []

    for row_no, row in rows:
        url = clean_text(row.get("账号链接"))
        handle = extract_handle(url, clean_text(row.get("账号ID")))
        before = row_snapshot(row_no, row)
        try:
            response = session.get(BASE_URL, params={"handle": handle}, timeout=args.timeout_seconds)
            is_json = response.headers.get("content-type", "").startswith("application/json")
            payload = response.json() if is_json else {"raw_text": response.text[:1000]}
        except Exception as exc:
            summary_items.append({"row": row_no, "url": url, "status": "request_error", "reason": str(exc), "before": before})
            continue

        user = payload.get("data", {}).get("user", {}) if isinstance(payload, dict) else {}
        bio = clean_text((user or {}).get("biography"))
        email = clean_text((user or {}).get("public_email")) or extract_email(bio)
        links = (user or {}).get("bio_links") or []
        usable = is_usable_payload(response.status_code, payload)

        raw_items.append({"row": row_no, "url": url, "handle": handle, "before": before, "http_status": response.status_code, "payload": payload})
        summary_items.append(
            {
                "row": row_no,
                "url": url,
                "status": "ok" if usable else "api_failed",
                "before": before,
                "api_extract": {
                    "handle": (user or {}).get("username") or handle,
                    "name": (user or {}).get("full_name"),
                    "follower_count": (user or {}).get("follower_count"),
                    "email": email,
                    "bio_preview": bio[:200],
                    "links_count": len(links) + (1 if clean_text((user or {}).get("external_url")) else 0),
                },
            }
        )
        time.sleep(args.delay_seconds)

    raw_report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "env_source": env_source, "csv_path": str(csv_path), "rows_requested": [row_no for row_no, _ in rows], "items": raw_items}
    summary_report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "env_source": env_source, "csv_path": str(csv_path), "rows_requested": [row_no for row_no, _ in rows], "items": summary_items}
    raw_path.write_text(json.dumps(raw_report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"raw_path": str(raw_path), "summary_path": str(summary_path), "count": len(summary_items)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
