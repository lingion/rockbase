from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from instagram_kol_discovery.io_utils import (
    INSTAGRAM_L1_FLEX_FIELDS,
    INSTAGRAM_L1_REQUIRED_FIELDS,
    get_env_value,
    safe_text,
    workbench_dir,
    write_csv,
    write_json,
)


HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")


def _request_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _hashtags(caption: str) -> str:
    return " | ".join(dict.fromkeys(HASHTAG_RE.findall(caption or "")))


def main() -> None:
    api_key = get_env_value("SCRAPECREATORS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPECREATORS_API_KEY")

    run_date = "2026-04-10"
    output_dir = workbench_dir(run_date)
    query_name = "brand_core"
    query_text = "accio"
    min_views = 2000
    min_followers = 2000

    search_url = "https://api.scrapecreators.com/v2/instagram/reels/search?" + urllib.parse.urlencode({"query": query_text})
    search_payload = _request_json(search_url, api_key)
    reels = search_payload.get("reels") or []

    content_rows: list[dict[str, object]] = []
    creators: dict[str, dict[str, object]] = {}
    profile_cache: dict[str, dict] = {}

    for reel in reels:
        owner = reel.get("owner") or {}
        handle = safe_text(owner.get("username"))
        if not handle:
            continue
        caption = safe_text(reel.get("caption"))
        view_count = int(reel.get("video_view_count") or reel.get("video_play_count") or 0)
        like_count = int(reel.get("like_count") or 0)
        comment_count = int(reel.get("comment_count") or 0)
        shortcode = safe_text(reel.get("shortcode"))
        content_url = safe_text(reel.get("url"))
        content_id = safe_text(reel.get("id"))
        row = {
            "platform": "instagram",
            "row_type": "content",
            "content_id": content_id,
            "shortcode": shortcode,
            "content_title": caption,
            "theme_text": caption,
            "content_url": content_url,
            "creator_handle": handle,
            "display_name": safe_text(owner.get("full_name")),
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
            "sample_contents": caption,
            "top_content_url": content_url,
            "source_content_ids": content_id,
            "provider_source": "scrapecreators.instagram.reels_search",
            "discovery_route": "content_first",
            "content_tags_or_hashtags": _hashtags(caption),
            "l2_eligible": "yes" if view_count >= min_views else "no",
            "l2_skip_reason": "" if view_count >= min_views else "below_views_gate",
            "owner_id": safe_text(owner.get("id")),
            "profile_url": f"https://www.instagram.com/{handle}/",
            "is_video": safe_text(reel.get("is_video")),
            "video_duration": safe_text(reel.get("video_duration")),
            "thumbnail_src": safe_text(reel.get("thumbnail_src")),
        }
        content_rows.append(row)

        agg = creators.setdefault(
            handle,
            {
                "platform": "instagram",
                "row_type": "creator_summary",
                "creator_handle": handle,
                "display_name": safe_text(owner.get("full_name")),
                "matched_queries": "",
                "matched_content_count": 0,
                "max_views": 0,
                "max_likes": 0,
                "max_comments": 0,
                "sample_contents": "",
                "top_content_url": "",
                "source_content_ids": "",
                "provider_source": "scrapecreators.instagram.reels_search",
                "discovery_route": "content_first",
                "content_tags_or_hashtags": "",
                "l2_eligible": "no",
                "l2_skip_reason": "below_views_gate",
                "profile_url": f"https://www.instagram.com/{handle}/",
                "followers_count": "",
                "bio": "",
                "external_links": "",
            },
        )
        agg["matched_content_count"] = int(agg["matched_content_count"]) + 1
        agg["max_views"] = max(int(agg["max_views"]), view_count)
        agg["max_likes"] = max(int(agg["max_likes"]), like_count)
        agg["max_comments"] = max(int(agg["max_comments"]), comment_count)
        existing_queries = [part for part in safe_text(agg["matched_queries"]).split(" | ") if part]
        if query_text not in existing_queries:
            existing_queries.append(query_text)
        agg["matched_queries"] = " | ".join(existing_queries)
        sample_parts = [part for part in safe_text(agg["sample_contents"]).split(" || ") if part]
        if caption and caption not in sample_parts and len(sample_parts) < 3:
            sample_parts.append(caption)
        agg["sample_contents"] = " || ".join(sample_parts)
        if view_count >= int(agg["max_views"]) and content_url:
            agg["top_content_url"] = content_url
        id_parts = [part for part in safe_text(agg["source_content_ids"]).split(" | ") if part]
        if content_id and content_id not in id_parts:
            id_parts.append(content_id)
        agg["source_content_ids"] = " | ".join(id_parts)
        if row["content_tags_or_hashtags"]:
            agg["content_tags_or_hashtags"] = row["content_tags_or_hashtags"]

    candidate_rows: list[dict[str, object]] = []
    for handle, agg in creators.items():
        if int(agg["max_views"]) >= min_views:
            agg["l2_eligible"] = "yes"
            agg["l2_skip_reason"] = ""
        profile_url = "https://api.scrapecreators.com/v1/instagram/profile?" + urllib.parse.urlencode({"handle": handle})
        try:
            profile_payload = _request_json(profile_url, api_key)
            profile_cache[handle] = profile_payload
            user = (profile_payload.get("data") or {}).get("user") or {}
            followers = int((((user.get("edge_followed_by") or {}).get("count")) or 0))
            agg["followers_count"] = followers
            agg["bio"] = safe_text(user.get("biography"))
            agg["external_links"] = safe_text(user.get("external_url"))
        except Exception as exc:
            agg["followers_count"] = ""
            agg["bio"] = ""
            agg["external_links"] = ""
            agg["profile_error"] = safe_text(exc)
        agg["profile_l2_eligible"] = "yes" if int(agg.get("followers_count") or 0) >= min_followers else "no"
        candidate_rows.append(agg)

    candidate_rows.sort(key=lambda row: (-int(row.get("followers_count") or 0), -int(row.get("max_views") or 0)))
    unified_rows = content_rows + candidate_rows

    raw_json = output_dir / f"instagram_accio_scrapecreators_raw_{run_date}.json"
    unified_csv = output_dir / f"instagram_accio_scrapecreators_L1_unified_{run_date}.csv"
    candidates_csv = output_dir / f"instagram_accio_scrapecreators_L1_candidates_{run_date}.csv"
    summary_json = output_dir / f"instagram_accio_scrapecreators_summary_{run_date}.json"

    write_json(raw_json, {"search_payload": search_payload, "profile_payloads": profile_cache})
    write_csv(unified_csv, unified_rows, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_csv(candidates_csv, candidate_rows, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_json(
        summary_json,
        {
            "query": query_text,
            "reels_count": len(reels),
            "creator_candidates": len(candidate_rows),
            "views_gate_2000": sum(1 for row in candidate_rows if row.get("l2_eligible") == "yes"),
            "followers_gate_2000": sum(1 for row in candidate_rows if row.get("profile_l2_eligible") == "yes"),
        },
    )
    print(candidates_csv)


if __name__ == "__main__":
    main()
