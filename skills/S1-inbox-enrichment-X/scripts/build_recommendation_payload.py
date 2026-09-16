from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from load_env import default_workbench_dir


def normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def load_handle_manifest_map(out_dir: Path) -> dict[str, str]:
    manifest_files = sorted(out_dir.glob("x_api_manifest_*.json"))
    if not manifest_files:
        raise FileNotFoundError(f"未在 {out_dir} 找到 x_api_manifest_*.json")

    handle_to_file: dict[str, str] = {}
    for manifest_file in manifest_files:
        items = json.loads(manifest_file.read_text(encoding="utf-8"))
        for item in items:
            handle = normalize_handle(item.get("handle", ""))
            file_path = item.get("file", "")
            if handle and file_path:
                handle_to_file[handle] = file_path
    return handle_to_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--product", required=True)
    parser.add_argument("--workbench-date", default="")
    args = parser.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    out_dir = default_workbench_dir(args.workbench_date or None)
    handle_to_file = load_handle_manifest_map(out_dir)

    items = []
    for _, row in df.iterrows():
        handle = normalize_handle(row.get("账号ID", ""))
        if not handle or handle not in handle_to_file:
            continue
        payload = json.loads(Path(handle_to_file[handle]).read_text(encoding="utf-8"))
        tweets = payload["response_json"].get("tweets", [])
        items.append(
            {
                "handle": "@" + handle,
                "product": args.product,
                "profile_name": row.get("频道/作者名称", ""),
                "bio": row.get("账号简介__平台抓取", ""),
                "recent_avg_views_10": row.get("近期10条均播", ""),
                "recent_avg_er_view_10": row.get("近10条平均ER（按曝光）", ""),
                "recent_avg_er_followers_10": row.get("近10条平均ER（按粉丝）", ""),
                "tweet_count": len(tweets),
                "tweets_json_file": handle_to_file[handle],
            }
        )

    out_file = out_dir / f"x_recommendation_input_{args.product}.json"
    out_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out_file), "count": len(items)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
