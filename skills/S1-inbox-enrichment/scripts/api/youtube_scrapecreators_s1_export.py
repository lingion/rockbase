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
BASE_URL = "https://api.scrapecreators.com/v1/youtube/channel"
YOUTUBE_PLATFORM = "YouTube"


def build_candidate_artifact(rows, model_results, validation):
    """Thin adapter to the shared S1 candidate contract.

    Imported lazily so the exporter keeps working when rockbase is not on
    sys.path (standalone CLI usage).
    """
    try:
        from rockbase.llm_stage_contracts import build_candidate_artifact as _build
    except ImportError:  # pragma: no cover - standalone CLI path
        import sys as _sys
        from pathlib import Path as _Path
        _root = _Path(__file__).resolve().parents[4]
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from rockbase.llm_stage_contracts import build_candidate_artifact as _build
    return _build(rows, model_results, validation)


def load_api_env() -> Optional[str]:
    if GLOBAL_ENV.exists():
        load_dotenv(GLOBAL_ENV, override=True)
        return str(GLOBAL_ENV)
    load_dotenv(override=True)
    return None


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export YouTube channel data from ScrapeCreators API into workbench JSON.")
    parser.add_argument("--csv", required=True, help="Target S1 CSV path")
    parser.add_argument("--rows", default="", help="Comma-separated physical row numbers to fetch")
    parser.add_argument("--limit", type=int, default=20, help="Max YouTube rows when --rows is empty")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Workbench date folder")
    parser.add_argument("--prefix", default="youtube_scrapecreators_batch", help="Output filename prefix")
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


def row_snapshot(row_no: int, row: pd.Series) -> dict[str, str]:
    return {
        "row": row_no,
        "platform": str(row.get("平台", "") or ""),
        "handle": str(row.get("账号ID", "") or ""),
        "author_name": str(row.get("频道/作者名称", "") or ""),
        "url": str(row.get("账号链接", "") or ""),
        "followers": str(row.get("粉丝数", "") or ""),
        "contact": str(row.get("联系方式", "") or ""),
        "contact_note": str(row.get("联系方式备注", "") or ""),
        "external_links": str(row.get("外链__平台抓取", "") or ""),
        "bio": str(row.get("账号简介__平台抓取", "") or ""),
    }


def select_rows(df: pd.DataFrame, requested_rows: list[int], limit: int) -> list[tuple[int, pd.Series]]:
    selected: list[tuple[int, pd.Series]] = []
    if requested_rows:
        for row_no in requested_rows:
            idx = row_no - 1
            if idx < 0 or idx >= len(df):
                continue
            row = df.iloc[idx]
            if str(row.get("平台", "") or "").strip() != YOUTUBE_PLATFORM:
                continue
            if not str(row.get("账号链接", "") or "").strip():
                continue
            selected.append((row_no, row))
        return selected

    for idx, row in df.iterrows():
        if str(row.get("平台", "") or "").strip() != YOUTUBE_PLATFORM:
            continue
        if not str(row.get("账号链接", "") or "").strip():
            continue
        selected.append((idx + 1, row))
        if len(selected) >= limit:
            break
    return selected


def extract_email(description: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", description or "", re.I)
    return match.group(0) if match else ""


def is_usable_payload(http_status: int, payload: object) -> bool:
    if http_status != 200 or not isinstance(payload, dict):
        return False
    if not payload.get("success"):
        return False
    if payload.get("accountDoesNotExist") or payload.get("errorStatus") == 404:
        return False
    return True


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
        url = str(row.get("账号链接", "") or "").strip()
        before = row_snapshot(row_no, row)
        try:
            response = session.get(BASE_URL, params={"url": url}, timeout=args.timeout_seconds)
            is_json = response.headers.get("content-type", "").startswith("application/json")
            payload = response.json() if is_json else {"raw_text": response.text[:1000]}
        except Exception as exc:
            summary_items.append(
                {
                    "row": row_no,
                    "url": url,
                    "status": "request_error",
                    "reason": str(exc),
                    "before": before,
                }
            )
            continue

        api_data = payload if isinstance(payload, dict) else {}
        usable = is_usable_payload(response.status_code, payload)
        description = str(api_data.get("description") or "")
        email = str(api_data.get("email") or "").strip() or extract_email(description)

        raw_items.append(
            {
                "row": row_no,
                "url": url,
                "before": before,
                "http_status": response.status_code,
                "payload": payload,
            }
        )
        summary_items.append(
            {
                "row": row_no,
                "url": url,
                "status": "ok" if usable else "api_failed",
                "before": before,
                "api_extract": {
                    "handle": api_data.get("handle"),
                    "name": api_data.get("name"),
                    "subscriberCount": api_data.get("subscriberCount"),
                    "subscriberCountText": api_data.get("subscriberCountText"),
                    "email": email,
                    "description_preview": description[:200],
                    "links_count": len(api_data.get("links") or []),
                },
            }
        )
        time.sleep(args.delay_seconds)

    raw_report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "env_source": env_source,
        "csv_path": str(csv_path),
        "rows_requested": [row_no for row_no, _ in rows],
        "items": raw_items,
    }
    summary_report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "env_source": env_source,
        "csv_path": str(csv_path),
        "rows_requested": [row_no for row_no, _ in rows],
        "items": summary_items,
    }
    raw_path.write_text(json.dumps(raw_report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"raw_path": str(raw_path), "summary_path": str(summary_path), "count": len(summary_items)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
