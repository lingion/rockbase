from __future__ import annotations

import argparse
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
from instagram_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates
from instagram_kol_discovery.task_spec import build_search_queries_from_spec, load_task_spec, task_spec_to_config


HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")


def _request_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _hashtags(caption: str) -> str:
    return " | ".join(dict.fromkeys(HASHTAG_RE.findall(caption or "")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Instagram KOL Layer1 via ScrapeCreators reels search.")
    parser.add_argument("--spec", required=True, help="Path to the task spec JSON.")
    parser.add_argument("--run-date", default="", help="Optional run date override.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--label", default="", help="Optional file label suffix, e.g. round2.")
    args = parser.parse_args()

    api_key = get_env_value("SCRAPECREATORS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPECREATORS_API_KEY")

    spec, _ = load_task_spec(args.spec)
    config = task_spec_to_config(spec, run_date=args.run_date or None)
    search_queries = build_search_queries_from_spec(spec)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workbench_dir(config.run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_payloads: list[dict[str, object]] = []
    content_rows: list[dict[str, object]] = []
    runlog: dict[str, object] = {
        "platform": "instagram",
        "run_date": config.run_date,
        "provider": "scrapecreators.instagram.reels_search",
        "events": [],
    }

    for search_query in search_queries:
        search_url = "https://api.scrapecreators.com/v2/instagram/reels/search?" + urllib.parse.urlencode({"query": search_query.query})
        search_payload = _request_json(search_url, api_key)
        reels = search_payload.get("reels") or []
        raw_payloads.append(
            {
                "query_name": search_query.name,
                "query_text": search_query.query,
                "search_payload": search_payload,
            }
        )
        runlog["events"].append(
            {
                "step": "search_reels",
                "query_name": search_query.name,
                "query_text": search_query.query,
                "result_count": len(reels),
                "credits_remaining": search_payload.get("credits_remaining"),
            }
        )
        for reel in reels[: search_query.limit]:
            owner = reel.get("owner") or {}
            handle = safe_text(owner.get("username"))
            if not handle:
                continue
            caption = safe_text(reel.get("caption"))
            view_count = int(reel.get("video_view_count") or reel.get("video_play_count") or 0)
            like_count = int(reel.get("like_count") or 0)
            comment_count = int(reel.get("comment_count") or 0)
            content_rows.append(
                {
                    "platform": "instagram",
                    "row_type": "content",
                    "content_id": safe_text(reel.get("id")),
                    "shortcode": safe_text(reel.get("shortcode")),
                    "content_title": caption,
                    "theme_text": caption,
                    "content_url": safe_text(reel.get("url")),
                    "creator_handle": handle,
                    "display_name": safe_text(owner.get("full_name")),
                    "matched_query_name": search_query.name,
                    "matched_query_text": search_query.query,
                    "matched_queries": search_query.query,
                    "matched_content_count": 1,
                    "view_count": view_count,
                    "like_count": like_count,
                    "comment_count": comment_count,
                    "max_views": view_count,
                    "max_likes": like_count,
                    "max_comments": comment_count,
                    "sample_contents": caption,
                    "top_content_url": safe_text(reel.get("url")),
                    "source_content_ids": safe_text(reel.get("id")),
                    "provider_source": "scrapecreators.instagram.reels_search",
                    "discovery_route": "content_first",
                    "content_tags_or_hashtags": _hashtags(caption),
                    "l2_eligible": "yes" if view_count >= config.min_content_views_for_l2 else "no",
                    "l2_skip_reason": "" if view_count >= config.min_content_views_for_l2 else f"below_views_gate_{config.min_content_views_for_l2}",
                    "owner_id": safe_text(owner.get("id")),
                    "profile_url": f"https://www.instagram.com/{handle}/",
                    "followers_count": safe_text(owner.get("follower_count")),
                    "is_video": safe_text(reel.get("is_video")),
                    "video_duration": safe_text(reel.get("video_duration")),
                    "thumbnail_src": safe_text(reel.get("thumbnail_src")),
                }
            )

    candidates = aggregate_to_layer1_candidates(content_rows, min_views_for_l2=config.min_content_views_for_l2)
    unified_rows = content_rows + candidates

    label = f"_{safe_text(args.label)}" if safe_text(args.label) else ""
    raw_json_path = output_dir / f"instagram_kol_L1_raw{label}_{config.run_date}.json"
    unified_csv_path = output_dir / f"instagram_kol_L1_unified{label}_{config.run_date}.csv"
    candidate_csv_path = output_dir / f"instagram_kol_L1_candidates{label}_{config.run_date}.csv"
    runlog_path = output_dir / f"instagram_kol_L1_runlog{label}_{config.run_date}.json"

    write_json(raw_json_path, raw_payloads)
    write_csv(unified_csv_path, unified_rows, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_csv(candidate_csv_path, candidates, preferred_fields=INSTAGRAM_L1_REQUIRED_FIELDS + INSTAGRAM_L1_FLEX_FIELDS)
    write_json(runlog_path, runlog)

    print(candidate_csv_path)


if __name__ == "__main__":
    main()
