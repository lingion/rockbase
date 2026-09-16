from __future__ import annotations

from typing import Any

from tiktok_kol_discovery.io_utils import safe_text


def aggregate_to_layer1_candidates(rows: list[dict[str, Any]], *, min_views_for_l2: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        handle = safe_text(row.get("author_unique_id") or row.get("creator_handle"))
        if not handle:
            continue

        record = grouped.setdefault(
            handle,
            {
                "platform": "tiktok",
                "row_type": "creator_summary",
                "creator_handle": handle,
                "display_name": safe_text(row.get("nickname") or row.get("display_name")),
                "matched_queries": "",
                "matched_content_count": 0,
                "max_views": 0,
                "max_likes": 0,
                "max_comments": 0,
                "sample_contents": "",
                "top_content_url": "",
                "source_content_ids": "",
                "provider_source": safe_text(row.get("provider_source")) or "tiktok_api_search",
                "discovery_route": "content_first",
                "content_tags_or_hashtags": "",
                "l2_eligible": "no",
                "l2_skip_reason": "below_views_gate",
                "author_unique_id": handle,
                "author_id": safe_text(row.get("author_id")),
                "nickname": safe_text(row.get("nickname")),
                "sec_uid": safe_text(row.get("sec_uid")),
            },
        )

        record["matched_content_count"] = int(record["matched_content_count"]) + 1
        views = int(row.get("view_count") or 0)
        likes = int(row.get("like_count") or 0)
        comments = int(row.get("comment_count") or 0)
        record["max_views"] = max(int(record["max_views"]), views)
        record["max_likes"] = max(int(record["max_likes"]), likes)
        record["max_comments"] = max(int(record["max_comments"]), comments)

        matched_query = safe_text(row.get("matched_query_text"))
        if matched_query:
            existing = [part for part in safe_text(record["matched_queries"]).split(" | ") if part]
            if matched_query not in existing:
                existing.append(matched_query)
            record["matched_queries"] = " | ".join(existing)

        content_id = safe_text(row.get("content_id"))
        if content_id:
            existing_ids = [part for part in safe_text(record["source_content_ids"]).split(" | ") if part]
            if content_id not in existing_ids:
                existing_ids.append(content_id)
            record["source_content_ids"] = " | ".join(existing_ids)

        title = safe_text(row.get("content_title") or row.get("theme_text"))
        if title:
            samples = [part for part in safe_text(record["sample_contents"]).split(" || ") if part]
            if title not in samples and len(samples) < 3:
                samples.append(title)
            record["sample_contents"] = " || ".join(samples)

        current_top = int(record["max_views"])
        if views >= current_top and safe_text(row.get("content_url")):
            record["top_content_url"] = safe_text(row.get("content_url"))

        tags = safe_text(row.get("content_tags_or_hashtags"))
        if tags:
            record["content_tags_or_hashtags"] = tags

    for record in grouped.values():
        if int(record["max_views"]) >= min_views_for_l2:
            record["l2_eligible"] = "yes"
            record["l2_skip_reason"] = ""

    return sorted(grouped.values(), key=lambda item: int(item.get("max_views") or 0), reverse=True)
