from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from typing import Any

import requests

from youtube_kol_discovery.io_utils import get_env_value, safe_text


class YouTubeProvider:
    def __init__(self, *, region_code: str = "US") -> None:
        self.region_code = region_code
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def collect_search(self, *, query_name: str, query_text: str, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
        if shutil.which("yt-dlp") is None:
            return [], ["yt-dlp not found in PATH"]
        template = "%(id)s\t%(title)s\t%(channel)s\t%(channel_id)s\t%(view_count)s\t%(release_timestamp)s"
        command = ["yt-dlp", "--flat-playlist", "--print", template, f"ytsearch{limit}:{query_text}"]
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = safe_text(exc.stderr) or str(exc)
            return [], [f"yt-dlp search failed: {stderr}"]

        rows: list[dict[str, Any]] = []
        for line in [item for item in completed.stdout.splitlines() if item.strip()]:
            video_id, title, channel, channel_id, views, release_ts = (line.split("\t") + ["", "", "", "", "", ""])[:6]
            rows.append(
                {
                    "provider": "youtube.yt_dlp_search",
                    "discovery_route": "content_first.search",
                    "query_name": query_name,
                    "query_text": query_text,
                    "video_id": video_id,
                    "title": title.strip(),
                    "channel_id": channel_id.strip(),
                    "channel_title": channel.strip(),
                    "published_at": self._to_iso_datetime(release_ts),
                    "view_count": self._to_int(views),
                    "like_count": 0,
                    "comment_count": 0,
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                    "tags": [],
                    "raw": {"release_timestamp": release_ts},
                }
            )
        return rows, []

    def collect_discover(self, *, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
        api_key = self._get_api_key()
        if not api_key:
            return [], ["YOUTUBE_API_KEY missing; discover downgraded to search-only mode"]
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": self.region_code,
            "maxResults": min(max(limit, 1), 50),
            "key": api_key,
        }
        try:
            response = self.session.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            return [], [f"YouTube discover API request failed: {exc}"]

        rows: list[dict[str, Any]] = []
        for entry in payload.get("items", [])[:limit]:
            snippet = entry.get("snippet") or {}
            statistics = entry.get("statistics") or {}
            tags = [safe_text(item) for item in (snippet.get("tags") or []) if safe_text(item)]
            rows.append(
                {
                    "provider": "youtube.api_most_popular",
                    "discovery_route": "content_first.discover",
                    "query_name": "most_popular",
                    "query_text": "",
                    "video_id": safe_text(entry.get("id")),
                    "title": safe_text(snippet.get("title")),
                    "channel_id": safe_text(snippet.get("channelId")),
                    "channel_title": safe_text(snippet.get("channelTitle")),
                    "published_at": safe_text(snippet.get("publishedAt")),
                    "view_count": self._to_int(statistics.get("viewCount")),
                    "like_count": self._to_int(statistics.get("likeCount")),
                    "comment_count": self._to_int(statistics.get("commentCount")),
                    "url": f"https://www.youtube.com/watch?v={safe_text(entry.get('id'))}",
                    "tags": tags[:10],
                    "raw": entry,
                }
            )
        return rows, []

    def _to_int(self, value: object) -> int:
        if value in (None, "", "NA"):
            return 0
        return int(str(value).replace(",", "").strip())

    def _to_iso_datetime(self, value: str) -> str:
        if value in ("", "NA"):
            return ""
        return datetime.fromtimestamp(int(value), tz=UTC).isoformat()

    def _get_api_key(self) -> str | None:
        value = get_env_value("YOUTUBE_API_KEY", "YT_API_KEY", "GOOGLE_API_KEY")
        return value or None
