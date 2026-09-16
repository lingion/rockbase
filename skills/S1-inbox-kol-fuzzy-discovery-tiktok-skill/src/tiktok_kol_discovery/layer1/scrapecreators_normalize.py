from __future__ import annotations

import re
from typing import Any

from tiktok_kol_discovery.io_utils import safe_text

HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")


def _nested(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _author_info(item: dict[str, Any]) -> dict[str, Any]:
    return (
        item.get("author")
        or item.get("authorInfo")
        or _nested(item, "aweme_info", "author")
        or _nested(item, "aweme_info", "authorInfo")
        or {}
    )


def _stats(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("stats") or _nested(item, "aweme_info", "statistics") or _nested(item, "statistics") or {}


def _hashtags(item: dict[str, Any]) -> str:
    candidates = []
    for source in (
        item.get("hashtags"),
        item.get("textExtra"),
        _nested(item, "aweme_info", "textExtra"),
    ):
        if isinstance(source, list):
            for entry in source:
                if isinstance(entry, dict):
                    tag = entry.get("hashtag_name") or entry.get("hashtagName") or entry.get("hashtag")
                    if tag:
                        candidates.append(str(tag))
                elif entry:
                    candidates.append(str(entry))
    desc = safe_text(
        item.get("desc")
        or item.get("description")
        or item.get("title")
        or _nested(item, "aweme_info", "desc")
        or _nested(item, "aweme_info", "description")
        or _nested(item, "aweme_info", "title")
    )
    for match in HASHTAG_RE.findall(desc):
        if match:
            candidates.append(match)
    return " | ".join(dict.fromkeys(candidates))


def normalize_search_item(
    item: dict[str, Any],
    *,
    query_name: str,
    query_text: str,
    provider_source: str,
    min_views_for_l2: int,
) -> dict[str, Any]:
    aweme = item.get("aweme_info") if isinstance(item.get("aweme_info"), dict) else item
    author = _author_info(aweme)
    stats = _stats(aweme)

    content_id = safe_text(aweme.get("aweme_id") or aweme.get("id"))
    desc = safe_text(aweme.get("desc") or aweme.get("description") or aweme.get("title"))
    handle = safe_text(author.get("unique_id") or author.get("uniqueId") or author.get("author_unique_id"))
    author_id = safe_text(author.get("uid") or author.get("id") or author.get("author_id"))
    nickname = safe_text(author.get("nickname"))
    sec_uid = safe_text(author.get("sec_uid") or author.get("secUid"))
    view_count = int(stats.get("play_count") or stats.get("playCount") or stats.get("view_count") or 0)
    like_count = int(stats.get("digg_count") or stats.get("diggCount") or stats.get("like_count") or 0)
    comment_count = int(stats.get("comment_count") or stats.get("commentCount") or 0)
    share_count = int(stats.get("share_count") or stats.get("shareCount") or 0)
    collect_count = int(stats.get("collect_count") or stats.get("collectCount") or 0)
    region = safe_text(aweme.get("region"))
    duration = aweme.get("duration") or aweme.get("video_duration") or 0
    music_title = safe_text(_nested(aweme, "music", "title") or aweme.get("music_title"))
    cover_url = safe_text(_nested(aweme, "video", "cover", "url_list", 0) if False else "")
    if not cover_url:
        cover = _nested(aweme, "video", "cover")
        if isinstance(cover, dict):
            urls = cover.get("url_list") or []
            if urls:
                cover_url = safe_text(urls[0])

    content_url = ""
    if handle and content_id:
        content_url = f"https://www.tiktok.com/@{handle}/video/{content_id}"

    return {
        "platform": "tiktok",
        "row_type": "content",
        "content_id": content_id,
        "content_title": desc,
        "theme_text": desc,
        "content_url": content_url,
        "creator_handle": handle,
        "display_name": nickname,
        "matched_query_name": query_name,
        "matched_query_text": query_text,
        "matched_queries": query_text,
        "matched_content_count": 1,
        "view_count": view_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "max_views": view_count,
        "max_likes": like_count,
        "max_comments": comment_count,
        "sample_contents": desc,
        "top_content_url": content_url,
        "source_content_ids": content_id,
        "provider_source": provider_source,
        "discovery_route": "content_first",
        "content_tags_or_hashtags": _hashtags(aweme),
        "l2_eligible": "yes" if view_count >= min_views_for_l2 else "no",
        "l2_skip_reason": "" if view_count >= min_views_for_l2 else "below_views_gate",
        "author_unique_id": handle,
        "author_id": author_id,
        "nickname": nickname,
        "sec_uid": sec_uid,
        "create_time": safe_text(aweme.get("create_time") or aweme.get("createTime")),
        "share_count": share_count,
        "collect_count": collect_count,
        "music_title": music_title,
        "region": region,
        "is_ad": safe_text(aweme.get("is_ad") or aweme.get("isAd")),
        "aweme_type": safe_text(aweme.get("aweme_type") or aweme.get("awemeType")),
        "cover_url": cover_url,
        "duration": duration,
    }
