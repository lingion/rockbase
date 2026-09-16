from __future__ import annotations

from typing import Any

from x_kol_discovery.io_utils import safe_text


TOPIC_KEYWORDS = {
    "openclaw",
    "ai",
    "agent",
    "agents",
    "agentic",
    "automation",
    "developer",
    "devtools",
    "workflow",
    "builder",
    "founder",
    "engineer",
    "researcher",
    "coding",
    "copilot",
    "assistant",
    "assistants",
    "operator",
    "operators",
}


def keyword_hits(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def parse_views_count(row: dict[str, Any]) -> int:
    raw = row.get("raw")
    if not isinstance(raw, dict):
        return 0
    views = raw.get("views")
    if isinstance(views, dict):
        count = views.get("count")
        if count is None:
            return 0
        try:
            return int(str(count).replace(",", "").strip())
        except ValueError:
            return 0
    return 0


def parse_bird_views_count(row: dict[str, Any]) -> int:
    raw = row.get("_raw")
    if not isinstance(raw, dict):
        return 0
    views = raw.get("views")
    if not isinstance(views, dict):
        return 0
    count = views.get("count")
    if count is None:
        return 0
    try:
        return int(str(count).replace(",", "").strip())
    except ValueError:
        return 0


def raw_search_rows_to_records(rows: list[dict[str, Any]], query_name: str, query_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "provider": "scweet",
                "query_name": query_name,
                "query_text": query_text,
                "tweet_id": row.get("tweet_id"),
                "username": str(((row.get("user") or {}).get("screen_name")) or "").lower(),
                "display_name": (row.get("user") or {}).get("name") or "",
                "timestamp": row.get("timestamp") or "",
                "text": safe_text(row.get("text")),
                "comments": int(row.get("comments") or 0),
                "likes": int(row.get("likes") or 0),
                "retweets": int(row.get("retweets") or 0),
                "views_count": parse_views_count(row),
                "tweet_url": row.get("tweet_url") or "",
                "raw": row,
            }
        )
    return out


def bird_search_rows_to_records(rows: list[dict[str, Any]], query_name: str, query_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        author = row.get("author") or {}
        username = str(author.get("username") or "").lower()
        tweet_id = str(row.get("id") or "")
        out.append(
            {
                "provider": "bird_cli",
                "query_name": query_name,
                "query_text": query_text,
                "tweet_id": tweet_id,
                "username": username,
                "display_name": author.get("name") or "",
                "timestamp": row.get("createdAt") or "",
                "text": safe_text(row.get("text")),
                "comments": int(row.get("replyCount") or 0),
                "likes": int(row.get("likeCount") or 0),
                "retweets": int(row.get("retweetCount") or 0),
                "views_count": parse_bird_views_count(row),
                "tweet_url": f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "",
                "raw": row,
            }
        )
    return out


def tweet_score(tweet: dict[str, Any]) -> float:
    likes = int(tweet.get("likes") or 0)
    retweets = int(tweet.get("retweets") or 0)
    comments = int(tweet.get("comments") or 0)
    text = safe_text(tweet.get("text"))
    return likes + retweets * 3 + comments * 2 + keyword_hits(text, TOPIC_KEYWORDS) * 5


def aggregate_to_layer1_candidates(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        username = str(row.get("username") or "").strip().lower()
        tweet_id = str(row.get("tweet_id") or "").strip()
        if not username or not tweet_id:
            continue
        slot = grouped.setdefault(
            username,
            {
                "username": username,
                "display_name": safe_text(row.get("display_name")),
                "matched_queries": set(),
                "tweet_count": 0,
                "max_views": 0,
                "max_likes": 0,
                "max_retweets": 0,
                "max_comments": 0,
                "sample_posts": [],
                "top_tweet_url": "",
                "top_tweet_timestamp": "",
                "top_tweet_text": "",
                "source_tweet_ids": [],
                "_best_score": -1.0,
                "_provider_sources": set(),
            },
        )
        slot["_provider_sources"].add(safe_text(row.get("provider")) or "scweet")
        slot["matched_queries"].add(safe_text(row.get("query_name")))
        slot["tweet_count"] += 1
        slot["max_views"] = max(int(slot["max_views"]), int(row.get("views_count") or 0))
        slot["max_likes"] = max(int(slot["max_likes"]), int(row.get("likes") or 0))
        slot["max_retweets"] = max(int(slot["max_retweets"]), int(row.get("retweets") or 0))
        slot["max_comments"] = max(int(slot["max_comments"]), int(row.get("comments") or 0))
        slot["source_tweet_ids"].append(tweet_id)
        text = safe_text(row.get("text"))
        if text and len(slot["sample_posts"]) < 3:
            slot["sample_posts"].append(text[:220])
        score = tweet_score(row)
        if score > float(slot["_best_score"]):
            slot["_best_score"] = score
            slot["top_tweet_url"] = safe_text(row.get("tweet_url"))
            slot["top_tweet_timestamp"] = safe_text(row.get("timestamp"))
            slot["top_tweet_text"] = text[:280]

    candidates: list[dict[str, Any]] = []
    for username, slot in grouped.items():
        candidates.append(
            {
                "username": username,
                "display_name": safe_text(slot["display_name"]),
                "matched_queries": " | ".join(sorted(slot["matched_queries"])),
                "tweet_count": int(slot["tweet_count"]),
                "max_views": int(slot["max_views"]),
                "max_likes": int(slot["max_likes"]),
                "max_retweets": int(slot["max_retweets"]),
                "max_comments": int(slot["max_comments"]),
                "sample_posts": " || ".join(slot["sample_posts"]),
                "top_tweet_url": safe_text(slot["top_tweet_url"]),
                "top_tweet_timestamp": safe_text(slot["top_tweet_timestamp"]),
                "top_tweet_text": safe_text(slot["top_tweet_text"]),
                "source_tweet_ids": ",".join(slot["source_tweet_ids"][:20]),
                "provider_source": " | ".join(sorted(slot["_provider_sources"])) or "scweet",
            }
        )
    candidates.sort(
        key=lambda row: (
            -int(row["max_views"]),
            -int(row["max_likes"]),
            -int(row["max_retweets"]),
            -int(row["max_comments"]),
            -int(row["tweet_count"]),
            row["username"],
        )
    )
    return candidates
