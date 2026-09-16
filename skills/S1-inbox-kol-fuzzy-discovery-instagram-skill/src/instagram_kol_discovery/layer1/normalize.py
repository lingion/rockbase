from __future__ import annotations

from typing import Any

from instagram_kol_discovery.io_utils import safe_text


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def aggregate_to_layer1_candidates(content_rows: list[dict[str, Any]], *, min_views_for_l2: int) -> list[dict[str, Any]]:
    creators: dict[str, dict[str, Any]] = {}
    for row in content_rows:
        handle = safe_text(row.get("creator_handle"))
        if not handle:
            continue
        agg = creators.setdefault(
            handle.lower(),
            {
                "platform": "instagram",
                "row_type": "creator_summary",
                "creator_handle": handle,
                "display_name": safe_text(row.get("display_name")),
                "matched_queries": "",
                "matched_content_count": 0,
                "max_views": 0,
                "max_likes": 0,
                "max_comments": 0,
                "sample_contents": "",
                "top_content_url": "",
                "source_content_ids": "",
                "provider_source": safe_text(row.get("provider_source")),
                "discovery_route": safe_text(row.get("discovery_route")) or "content_first",
                "content_tags_or_hashtags": "",
                "l2_eligible": "no",
                "l2_skip_reason": f"below_views_gate_{min_views_for_l2}",
                "profile_url": safe_text(row.get("profile_url")),
                "owner_id": safe_text(row.get("owner_id")),
                "followers_count": safe_text(row.get("followers_count")),
            },
        )
        agg["matched_content_count"] = int(agg["matched_content_count"]) + 1
        view_count = _to_int(row.get("view_count"))
        like_count = _to_int(row.get("like_count"))
        comment_count = _to_int(row.get("comment_count"))
        if view_count >= _to_int(agg.get("max_views")):
            agg["max_views"] = view_count
            agg["top_content_url"] = safe_text(row.get("content_url"))
        agg["max_likes"] = max(_to_int(agg.get("max_likes")), like_count)
        agg["max_comments"] = max(_to_int(agg.get("max_comments")), comment_count)
        if not safe_text(agg.get("display_name")):
            agg["display_name"] = safe_text(row.get("display_name"))
        if not safe_text(agg.get("profile_url")):
            agg["profile_url"] = safe_text(row.get("profile_url"))
        if not safe_text(agg.get("followers_count")) and safe_text(row.get("followers_count")):
            agg["followers_count"] = safe_text(row.get("followers_count"))
        if not safe_text(agg.get("owner_id")):
            agg["owner_id"] = safe_text(row.get("owner_id"))

        existing_queries = [part for part in safe_text(agg["matched_queries"]).split(" | ") if part]
        query_text = safe_text(row.get("matched_query_text"))
        if query_text and query_text not in existing_queries:
            existing_queries.append(query_text)
        agg["matched_queries"] = " | ".join(existing_queries)

        sample_parts = [part for part in safe_text(agg["sample_contents"]).split(" || ") if part]
        caption = safe_text(row.get("theme_text"))
        if caption and caption not in sample_parts and len(sample_parts) < 3:
            sample_parts.append(caption)
        agg["sample_contents"] = " || ".join(sample_parts)

        id_parts = [part for part in safe_text(agg["source_content_ids"]).split(" | ") if part]
        content_id = safe_text(row.get("content_id"))
        if content_id and content_id not in id_parts:
            id_parts.append(content_id)
        agg["source_content_ids"] = " | ".join(id_parts)

        tag_parts = [part for part in safe_text(agg["content_tags_or_hashtags"]).split(" | ") if part]
        for tag in [part for part in safe_text(row.get("content_tags_or_hashtags")).split(" | ") if part]:
            if tag not in tag_parts:
                tag_parts.append(tag)
        agg["content_tags_or_hashtags"] = " | ".join(tag_parts)

    rows = list(creators.values())
    for row in rows:
        if _to_int(row.get("max_views")) >= min_views_for_l2:
            row["l2_eligible"] = "yes"
            row["l2_skip_reason"] = ""
    rows.sort(key=lambda item: (-_to_int(item.get("max_views")), safe_text(item.get("creator_handle"))))
    return rows
