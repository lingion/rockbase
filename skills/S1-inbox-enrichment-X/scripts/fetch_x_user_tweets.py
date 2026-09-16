from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from load_env import default_workbench_dir, load_skill_env, require_api_key


BASE_URL = "https://api.scrapecreators.com/v1/twitter/user-tweets"


def normalize_handle(value: str) -> str:
    text = str(value or "").strip()
    return text.lstrip("@").strip()


def iter_handles(csv_path: Path, handle_col: str) -> Iterable[str]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if handle_col not in df.columns:
        raise ValueError(f"CSV 中未找到列: {handle_col}")
    for raw in df[handle_col].fillna("").tolist():
        handle = normalize_handle(raw)
        if handle:
            yield handle


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        yield values
        return
    for i in range(0, len(values), size):
        yield values[i : i + size]


def classify_result(status_code: int, response_json: dict | None, error: str = "") -> tuple[str, str]:
    if error:
        text = error.lower()
        if "proxyerror" in text or "connection" in text or "timeout" in text:
            return "network_error", error
        return "bad_payload", error

    payload = response_json or {}
    message = str(payload.get("message") or "").strip()
    tweets = payload.get("tweets") or []

    if status_code == 404:
        return "account_not_exist", message or "Account doesn't exist"
    if "account doesn't exist" in message.lower() or "account doesnt exist" in message.lower():
        return "account_not_exist", message
    if status_code >= 400:
        return "http_error", message or f"HTTP {status_code}"
    if not isinstance(payload, dict):
        return "bad_payload", "response_json is not an object"
    if len(tweets) == 0:
        return "empty", message or "API no tweets"
    return "ok", message


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, help="名单 CSV 路径")
    parser.add_argument("--handle-col", default="账号ID")
    parser.add_argument("--handles", nargs="*", default=[])
    parser.add_argument("--batch-name", default="x-layer2")
    parser.add_argument("--workbench-date", default="")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=10)
    args = parser.parse_args()

    load_skill_env()
    api_key = require_api_key()
    headers = {"x-api-key": api_key}

    handles = [normalize_handle(x) for x in args.handles if normalize_handle(x)]
    if args.csv:
        handles.extend(list(iter_handles(args.csv, args.handle_col)))
    handles = list(dict.fromkeys(handles))
    if not handles:
        raise ValueError("没有可抓取的 handle。")

    out_dir = default_workbench_dir(args.workbench_date or None)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    manifest_file = out_dir / f"x_api_manifest_{args.batch_name}.json"
    for batch_index, handle_batch in enumerate(chunked(handles, args.chunk_size), start=1):
        print(
            json.dumps(
                {
                    "batch_index": batch_index,
                    "batch_size": len(handle_batch),
                    "chunk_size": args.chunk_size,
                },
                ensure_ascii=False,
            )
        )
        for handle in handle_batch:
            out_file = out_dir / f"x_api_sample_{handle}.json"
            if args.skip_existing and out_file.exists():
                try:
                    existing = json.loads(out_file.read_text(encoding="utf-8"))
                    response_json = existing.get("response_json") or {}
                    tweet_count = len((response_json.get("tweets") or []))
                    status_code = int(existing.get("status_code", 200) or 200)
                    result_type, message = classify_result(
                        status_code=status_code,
                        response_json=response_json,
                        error=str(existing.get("error") or "").strip(),
                    )
                    manifest.append(
                        {
                            "handle": handle,
                            "file": str(out_file),
                            "status_code": status_code,
                            "tweet_count": tweet_count,
                            "result_type": result_type,
                            "message": message,
                            "batch_name": args.batch_name,
                            "batch_index": batch_index,
                            "skipped_existing": True,
                        }
                    )
                    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps({"handle": handle, "status": "skipped-existing"}, ensure_ascii=False))
                    continue
                except Exception:
                    pass

            try:
                response = requests.get(BASE_URL, headers=headers, params={"handle": handle}, timeout=args.timeout)
                payload = {
                    "handle": handle,
                    "status_code": response.status_code,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "endpoint": BASE_URL,
                    "params": {"handle": handle},
                    "response_json": response.json(),
                }
                out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                tweet_count = len(payload["response_json"].get("tweets", []))
                status_code = response.status_code
                result_type, message = classify_result(status_code=status_code, response_json=payload["response_json"])
            except Exception as exc:
                payload = {
                    "handle": handle,
                    "status_code": -1,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "endpoint": BASE_URL,
                    "params": {"handle": handle},
                    "error": repr(exc),
                }
                out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                tweet_count = 0
                status_code = -1
                result_type, message = classify_result(status_code=status_code, response_json=None, error=repr(exc))

            manifest.append(
                {
                    "handle": handle,
                    "file": str(out_file),
                    "status_code": status_code,
                    "tweet_count": tweet_count,
                    "result_type": result_type,
                    "message": message,
                    "batch_name": args.batch_name,
                    "batch_index": batch_index,
                    "skipped_existing": False,
                }
            )
            manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "handle": handle,
                        "status_code": status_code,
                        "tweet_count": tweet_count,
                        "result_type": result_type,
                    },
                    ensure_ascii=False,
                )
            )
    print(json.dumps({"manifest_file": str(manifest_file), "count": len(manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
