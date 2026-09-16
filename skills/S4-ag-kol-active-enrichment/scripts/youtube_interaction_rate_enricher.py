from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv


GLOBAL_ENV = Path("${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env")
LEGACY_ENVS = [
    Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-kol-scraper/.env"),
    Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🕸️ Net/ag-kol-scraper/.env"),
]
BASE_URL = "https://api.scrapecreators.com/v1"


def load_api_env() -> Optional[str]:
    for path in [GLOBAL_ENV, *LEGACY_ENVS]:
        if path.exists():
            load_dotenv(path, override=True)
            return str(path)
    load_dotenv(override=True)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill YouTube interaction rate using the latest 3 non-Shorts videos.")
    parser.add_argument("--xlsx", required=True, help="Target Excel path")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process after filtering; 0 means no limit")
    parser.add_argument("--only-missing", action="store_true", help="Only fill rows where 互动率 is empty")
    parser.add_argument("--video-count", type=int, default=3, help="How many recent non-Shorts videos to average")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Workbench date folder for logs and backups")
    return parser.parse_args()


def normalize_channel_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    url = url.split("?")[0].rstrip("/")
    if url.endswith("/videos"):
        url = url[:-7]
    return url


def workbench_root(xlsx_path: Path, date_str: str) -> Path:
    root = xlsx_path.resolve().parents[1]
    return root / "workbench" / date_str


def backup_file(xlsx_path: Path, date_str: str) -> Path:
    root = workbench_root(xlsx_path, date_str)
    root.mkdir(parents=True, exist_ok=True)
    backup = root / f"{xlsx_path.stem}_yt_er_bak_{datetime.now().strftime('%H%M%S')}{xlsx_path.suffix}"
    backup.write_bytes(xlsx_path.read_bytes())
    return backup


def get_channel(session: requests.Session, url: str) -> dict:
    response = session.get(f"{BASE_URL}/youtube/channel", params={"url": url}, timeout=30)
    response.raise_for_status()
    return response.json()


def get_video(session: requests.Session, url: str) -> dict:
    response = session.get(f"{BASE_URL}/youtube/video", params={"url": url}, timeout=30)
    response.raise_for_status()
    return response.json()


def latest_videos_from_page(channel_url: str, limit: int) -> list[str]:
    videos_url = normalize_channel_url(channel_url) + "/videos"
    text = requests.get(videos_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    ids: list[str] = []
    for match in re.finditer(r'"videoId":"([A-Za-z0-9_-]{11})"', text):
        vid = match.group(1)
        if vid not in ids:
            ids.append(vid)
        if len(ids) >= limit * 8:
            break
    return [f"https://www.youtube.com/watch?v={vid}" for vid in ids]


def calc_video_er(payload: dict) -> Optional[float]:
    views = payload.get("viewCountInt")
    likes = payload.get("likeCountInt")
    comments = payload.get("commentCountInt")
    if not isinstance(views, int) or views <= 0:
        return None
    likes = likes if isinstance(likes, int) else 0
    comments = comments if isinstance(comments, int) else 0
    return (likes + comments) / views


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    args = parse_args()
    env_source = load_api_env()
    api_key = os.getenv("SCRAPECREATORS_API_KEY")
    if not api_key:
        raise RuntimeError(f"SCRAPECREATORS_API_KEY 未找到，env_source={env_source}")

    xlsx_path = Path(args.xlsx).expanduser().resolve()
    backup_path = backup_file(xlsx_path, args.date)
    df = pd.read_excel(xlsx_path)

    if "互动率" in df.columns:
        df["互动率"] = df["互动率"].astype("object")

    target = df[df["平台"].astype(str).str.strip().eq("YouTube")].copy()
    if args.only_missing:
        target = target[target["互动率"].fillna("").astype(str).str.strip().eq("")]
    if args.limit and args.limit > 0:
        target = target.head(args.limit)

    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    updates = []
    for idx in target.index.tolist():
        row = df.loc[idx]
        channel_url = normalize_channel_url(str(row.get("账号链接", "")))
        if not channel_url:
            continue

        # Channel API is kept for diagnostics and future extensions.
        channel_payload = get_channel(session, channel_url)
        candidate_urls = latest_videos_from_page(channel_url, args.video_count)

        ers: list[float] = []
        video_details = []
        first_video_url = ""
        for video_url in candidate_urls:
            payload = get_video(session, video_url)
            if str(payload.get("type", "")).lower() == "shorts":
                continue
            er = calc_video_er(payload)
            if er is None:
                continue
            ers.append(er)
            if not first_video_url:
                first_video_url = video_url
            video_details.append(
                {
                    "video_url": video_url,
                    "viewCountInt": payload.get("viewCountInt"),
                    "likeCountInt": payload.get("likeCountInt"),
                    "commentCountInt": payload.get("commentCountInt"),
                    "er": format_pct(er),
                }
            )
            if len(ers) >= args.video_count:
                break

        if not ers:
            continue

        avg_er = statistics.mean(ers)
        df.at[idx, "互动率"] = format_pct(avg_er)
        if "视频链接" in df.columns and not str(df.at[idx, "视频链接"] or "").strip() and first_video_url:
            df.at[idx, "视频链接"] = first_video_url

        updates.append(
            {
                "row": int(idx) + 2,
                "name": str(row.get("频道/作者名称", "") or ""),
                "channel_url": channel_url,
                "channel_id": channel_payload.get("channelId"),
                "avg_er": format_pct(avg_er),
                "videos": video_details,
            }
        )

    df.to_excel(xlsx_path, index=False)

    output_dir = workbench_root(xlsx_path, args.date)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    summary_path = output_dir / f"youtube_interaction_rate_enrichment_{stamp}.json"
    summary_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "env_source": env_source,
                "xlsx_path": str(xlsx_path),
                "backup_path": str(backup_path),
                "processed_count": len(updates),
                "video_count_rule": args.video_count,
                "updates": updates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "backup_path": str(backup_path),
                "summary_path": str(summary_path),
                "processed_count": len(updates),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for item in updates:
        print(item["name"], item["avg_er"])


if __name__ == "__main__":
    main()
