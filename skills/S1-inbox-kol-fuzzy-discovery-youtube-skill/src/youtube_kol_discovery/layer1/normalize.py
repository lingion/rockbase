from __future__ import annotations

from typing import Any

from youtube_kol_discovery.io_utils import safe_text


def _creator_handle(row: dict[str, Any]) -> str:
    channel_id = safe_text(row.get("channel_id"))
    if channel_id and channel_id.upper() != "NA":
        return channel_id
    title = safe_text(row.get("channel_title")).lower()
    slug = "-".join(part for part in title.replace("/", " ").split() if part)
    return f"channel_title:{slug}" if slug else ""


def aggregate_to_layer1_candidates(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        channel_id = _creator_handle(row)
        video_id = safe_text(row.get("video_id"))
        if not channel_id or not video_id:
            continue
        slot = grouped.setdefault(
            channel_id,
            {
                "platform": "youtube",
                "creator_handle": channel_id,
                "display_name": safe_text(row.get("channel_title")),
                "matched_queries": set(),
                "matched_content_count": 0,
                "max_views": 0,
                "max_likes": 0,
                "max_comments": 0,
                "sample_contents": [],
                "top_content_url": "",
                "top_content_title": "",
                "theme_text": "",
                "source_content_ids": [],
                "provider_source": set(),
                "discovery_route": set(),
                "content_tags_or_hashtags": set(),
                "channel_id": channel_id,
                "channel_title": safe_text(row.get("channel_title")),
            },
        )
        slot["matched_queries"].add(safe_text(row.get("query_name")) or "discover")
        slot["matched_content_count"] += 1
        slot["max_views"] = max(int(slot["max_views"]), int(row.get("view_count") or 0))
        slot["max_likes"] = max(int(slot["max_likes"]), int(row.get("like_count") or 0))
        slot["max_comments"] = max(int(slot["max_comments"]), int(row.get("comment_count") or 0))
        slot["source_content_ids"].append(video_id)
        slot["provider_source"].add(safe_text(row.get("provider")))
        slot["discovery_route"].add(safe_text(row.get("discovery_route")))
        for tag in row.get("tags") or []:
            cleaned = safe_text(tag)
            if cleaned:
                slot["content_tags_or_hashtags"].add(cleaned)
        title = safe_text(row.get("title"))
        if title and len(slot["sample_contents"]) < 3:
            slot["sample_contents"].append(title[:220])
        if int(row.get("view_count") or 0) >= int(slot["max_views"]):
            slot["top_content_url"] = safe_text(row.get("url"))
            slot["top_content_title"] = title[:220]
            slot["theme_text"] = title[:220]

    candidates: list[dict[str, Any]] = []
    for slot in grouped.values():
        candidates.append(
            {
                "platform": slot["platform"],
                "row_type": "creator_summary",
                "content_id": "",
                "content_title": "",
                "creator_handle": slot["creator_handle"],
                "display_name": slot["display_name"],
                "matched_query_name": "",
                "matched_query_text": "",
                "matched_queries": " | ".join(sorted(slot["matched_queries"])),
                "matched_content_count": int(slot["matched_content_count"]),
                "max_views": int(slot["max_views"]),
                "max_likes": int(slot["max_likes"]),
                "max_comments": int(slot["max_comments"]),
                "sample_contents": " || ".join(slot["sample_contents"]),
                "top_content_url": safe_text(slot["top_content_url"]),
                "content_url": safe_text(slot["top_content_url"]),
                "view_count": int(slot["max_views"]),
                "like_count": int(slot["max_likes"]),
                "comment_count": int(slot["max_comments"]),
                "top_content_title": safe_text(slot["top_content_title"]),
                "theme_text": safe_text(slot["theme_text"]),
                "source_content_ids": ",".join(slot["source_content_ids"][:20]),
                "provider_source": " | ".join(sorted(slot["provider_source"])),
                "discovery_route": " | ".join(sorted(slot["discovery_route"])),
                "content_tags_or_hashtags": " | ".join(sorted(slot["content_tags_or_hashtags"])),
                "channel_id": "" if str(slot["channel_id"]).startswith("channel_title:") else slot["channel_id"],
                "channel_title": slot["channel_title"],
                "l2_eligible": "yes" if int(slot["max_views"]) >= 1000 else "no",
                "l2_skip_reason": "" if int(slot["max_views"]) >= 1000 else "views_below_1000",
                "creator_max_views": int(slot["max_views"]),
                "creator_top_content_url": safe_text(slot["top_content_url"]),
            }
        )
    candidates.sort(
        key=lambda row: (
            -int(row["max_views"]),
            -int(row["max_likes"]),
            -int(row["max_comments"]),
            -int(row["matched_content_count"]),
            row["creator_handle"],
        )
    )
    return candidates
