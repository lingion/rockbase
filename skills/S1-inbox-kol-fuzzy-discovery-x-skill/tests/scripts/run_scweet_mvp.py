from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common_env import load_simple_env, tests_root


QUERY_SPECS: list[tuple[str, str]] = [
    (
        "openclaw_core_ai",
        '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools") -crypto -trader -airdrop',
    ),
    (
        "openclaw_workflow",
        '"OpenClaw" (workflow OR productivity OR coding OR devtools OR build) -crypto -trader -airdrop',
    ),
    (
        "openclaw_roles",
        '"OpenClaw" (builder OR founder OR engineer OR researcher OR creator) -crypto -trader -airdrop',
    ),
    (
        "openclaw_content",
        '"OpenClaw" (tutorial OR demo OR review OR usecase OR walkthrough) -crypto -trader -airdrop',
    ),
    (
        "openclaw_product",
        '"OpenClaw" (startup OR SaaS OR product OR team OR launch) -crypto -trader -airdrop',
    ),
    (
        "openclaw_agentic",
        '"OpenClaw" (agentic OR copilot OR copilots OR assistant OR assistants OR operators) -crypto -trader -airdrop',
    ),
]

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

ROLE_KEYWORDS = {"founder", "builder", "engineer", "researcher", "creator", "developer"}
BAD_KEYWORDS = {
    "crypto",
    "trader",
    "airdrop",
    "memecoin",
    "pump",
    "signals",
    "polymarket",
    "gold",
    "forex",
}


@dataclass
class RunConfig:
    since: str = "2026-03-01"
    until: str = "2026-03-31"
    per_query_limit: int = 90
    shortlist_target: int = 100
    min_followers_for_shortlist: int = 1000
    user_info_batch_size: int = 20


def _root_paths() -> tuple[Path, Path]:
    tests_dir = tests_root()
    project_root = tests_dir.parents[3]
    return tests_dir, project_root


def _workbench_dir(project_root: Path) -> Path:
    out_dir = project_root / "workbench" / "2026-03-31"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _scweet_bin() -> str:
    candidate = Path(sys.executable).with_name("scweet")
    if candidate.exists():
        return str(candidate)
    return "scweet"


def _run_json_command(cmd: list[str]) -> list[dict[str, Any]]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd[:-1])}\n{proc.stderr[:1500]}")
    if not proc.stdout.strip():
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON output from command: {' '.join(cmd[:-1])}") from exc
    if isinstance(payload, list):
        return payload
    raise RuntimeError(f"Expected list JSON from command: {' '.join(cmd[:-1])}")


def _redacted_command(cmd: list[str], auth_token: str) -> str:
    return " ".join(part if part != auth_token else "[REDACTED_TOKEN]" for part in cmd)


def _search_rows(auth_token: str, db_path: Path, query_name: str, query: str, config: RunConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cmd = [
        _scweet_bin(),
        "--auth-token",
        auth_token,
        "--db-path",
        str(db_path),
        "search",
        query,
        "--lang",
        "en",
        "--since",
        config.since,
        "--until",
        config.until,
        "--limit",
        str(config.per_query_limit),
        "--pretty",
    ]
    started = datetime.now(UTC).isoformat()
    rows = _run_json_command(cmd)
    run_meta = {
        "query_name": query_name,
        "query": query,
        "command": _redacted_command(cmd, auth_token),
        "started_utc": started,
        "ended_utc": datetime.now(UTC).isoformat(),
        "result_count": len(rows),
    }
    return rows, run_meta


def _batched(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fetch_user_info(auth_token: str, db_path: Path, usernames: list[str], config: RunConfig) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    profiles: dict[str, dict[str, Any]] = {}
    batch_meta: list[dict[str, Any]] = []
    for chunk in _batched(usernames, config.user_info_batch_size):
        cmd = [
            _scweet_bin(),
            "--auth-token",
            auth_token,
            "--db-path",
            str(db_path),
            "user-info",
            *chunk,
            "--pretty",
        ]
        rows = _run_json_command(cmd)
        for row in rows:
            username = str(row.get("username") or "").strip().lower()
            if username:
                profiles[username] = row
        batch_meta.append(
            {
                "user_count": len(chunk),
                "resolved_count": len(rows),
                "command": _redacted_command(cmd, auth_token),
            }
        )
    return profiles, batch_meta


def _safe_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _keyword_hits(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def _tweet_score(tweet: dict[str, Any]) -> float:
    likes = int(tweet.get("likes") or 0)
    retweets = int(tweet.get("retweets") or 0)
    comments = int(tweet.get("comments") or 0)
    text = _safe_text(tweet.get("text"))
    return likes + retweets * 3 + comments * 2 + _keyword_hits(text, TOPIC_KEYWORDS) * 5


def _profile_score(description: str, followers: int, verified: bool, blue_verified: bool) -> float:
    score = 0.0
    score += min(_keyword_hits(description, ROLE_KEYWORDS) * 8, 24)
    if followers >= 1000:
        score += 12
    if followers >= 5000:
        score += 6
    if followers >= 20000:
        score += 4
    if verified or blue_verified:
        score += 6
    if _keyword_hits(description, BAD_KEYWORDS):
        score -= 18
    return score


def _activity_score(max_likes: int, max_retweets: int, tweet_count: int) -> float:
    engagement_score = min(math.log10(max(max_likes + max_retweets * 5, 1)) * 18, 42)
    volume_score = min(tweet_count * 2.2, 18)
    return round(engagement_score + volume_score, 2)


def _topic_score(sample_posts: str, matched_queries: str, description: str) -> float:
    text = " ".join([sample_posts, matched_queries, description]).lower()
    score = min(_keyword_hits(text, TOPIC_KEYWORDS) * 4.5, 45)
    if "openclaw" in text:
        score += 8
    if _keyword_hits(text, BAD_KEYWORDS):
        score -= 16
    return round(max(score, 0), 2)


def _recommended_action(overall_score: float, followers_count: int, bad_keyword_hits: int) -> str:
    if bad_keyword_hits > 0:
        return "drop"
    if followers_count >= 1000 and overall_score >= 60:
        return "keep"
    if overall_score >= 42:
        return "review"
    return "drop"


def _normalize_rows(
    raw_rows: list[dict[str, Any]],
    profile_map: dict[str, dict[str, Any]],
    config: RunConfig,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    tweet_ids_seen: set[str] = set()
    for row in raw_rows:
        tweet_id = str(row.get("tweet_id") or "").strip()
        username = str(
            row.get("username")
            or ((row.get("user") or {}).get("screen_name"))
            or ""
        ).strip().lower()
        if not tweet_id or not username:
            continue
        dedupe_key = f"{username}:{tweet_id}"
        if dedupe_key in tweet_ids_seen:
            continue
        tweet_ids_seen.add(dedupe_key)
        slot = grouped.setdefault(
            username,
            {
                "username": username,
                "display_name": _safe_text(
                    row.get("display_name") or ((row.get("user") or {}).get("name"))
                ),
                "query_names": set(),
                "query_texts": set(),
                "tweet_count": 0,
                "max_likes": 0,
                "max_retweets": 0,
                "max_comments": 0,
                "source_tweet_ids": [],
                "top_tweet_url": "",
                "sample_posts": [],
                "_best_score": -1.0,
            },
        )
        slot["query_names"].add(_safe_text(row.get("query_name")))
        slot["query_texts"].add(_safe_text(row.get("query_text")))
        slot["tweet_count"] += 1
        likes = int(row.get("likes") or 0)
        retweets = int(row.get("retweets") or 0)
        comments = int(row.get("comments") or 0)
        slot["max_likes"] = max(int(slot["max_likes"]), likes)
        slot["max_retweets"] = max(int(slot["max_retweets"]), retweets)
        slot["max_comments"] = max(int(slot["max_comments"]), comments)
        slot["source_tweet_ids"].append(tweet_id)

        score = _tweet_score(row)
        text = _safe_text(row.get("text"))
        tweet_url = _safe_text(row.get("tweet_url"))
        if score > float(slot["_best_score"]):
            slot["_best_score"] = score
            slot["top_tweet_url"] = tweet_url
        if text and len(slot["sample_posts"]) < 3:
            slot["sample_posts"].append(text[:220])

    normalized: list[dict[str, Any]] = []
    for username, slot in grouped.items():
        profile = profile_map.get(username, {})
        description = _safe_text(profile.get("description"))
        followers = int(profile.get("followers_count") or 0)
        following = int(profile.get("following_count") or 0)
        statuses = int(profile.get("statuses_count") or 0)
        verified = bool(profile.get("verified", False))
        blue_verified = bool(profile.get("blue_verified", False))
        location = _safe_text(profile.get("location"))
        display_name = _safe_text(profile.get("name")) or _safe_text(slot.get("display_name"))
        sample_posts = " || ".join(slot["sample_posts"])
        matched_queries = " | ".join(sorted(slot["query_names"]))
        bad_hits = _keyword_hits(" ".join([description, sample_posts]), BAD_KEYWORDS)
        topic_match_score = _topic_score(sample_posts, matched_queries, description)
        profile_match_score = round(_profile_score(description, followers, verified, blue_verified), 2)
        activity_score = _activity_score(int(slot["max_likes"]), int(slot["max_retweets"]), int(slot["tweet_count"]))
        overall_score = round(topic_match_score + profile_match_score + activity_score, 2)
        recommended_action = _recommended_action(overall_score, followers, bad_hits)
        if followers < config.min_followers_for_shortlist and recommended_action == "keep":
            recommended_action = "review"

        normalized.append(
            {
                "username": username,
                "display_name": display_name,
                "bio": description,
                "location_raw": location,
                "followers_count": followers,
                "following_count": following,
                "tweet_count": int(slot["tweet_count"]),
                "statuses_count": statuses,
                "verified": verified,
                "blue_verified": blue_verified,
                "profile_match_score": profile_match_score,
                "topic_match_score": topic_match_score,
                "activity_score": activity_score,
                "overall_score": overall_score,
                "recommended_action": recommended_action,
                "matched_queries": matched_queries,
                "sample_posts": sample_posts,
                "top_tweet_url": slot["top_tweet_url"],
                "profile_url": f"https://x.com/{username}",
                "source_tweet_ids": ",".join(slot["source_tweet_ids"][:20]),
                "bad_keyword_hits": bad_hits,
                "provider_source": "scweet",
            }
        )

    normalized.sort(
        key=lambda row: (
            0 if row["recommended_action"] == "keep" else 1 if row["recommended_action"] == "review" else 2,
            -float(row["overall_score"]),
            -int(row["followers_count"]),
            -int(row["tweet_count"]),
        )
    )
    return normalized


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(
    path: Path,
    config: RunConfig,
    search_meta: list[dict[str, Any]],
    user_info_meta: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    normalized_rows: list[dict[str, Any]],
    shortlist_rows: list[dict[str, Any]],
    file_map: dict[str, Path],
) -> None:
    keep_count = sum(1 for row in normalized_rows if row["recommended_action"] == "keep")
    review_count = sum(1 for row in normalized_rows if row["recommended_action"] == "review")
    lines = [
        "---",
        "tags:",
        "  - SocialAgency",
        "  - Skills",
        "  - X",
        "  - KOLDiscovery",
        "  - MVP",
        f"date: 2026-03-31",
        "status: active",
        "---",
        "",
        "# 2026-03-31 X KOL MVP Summary",
        "",
        "## 目标",
        "",
        "- 主题：英语区，最近讨论 OpenClaw 相关 AI / agent / automation / developer tools 话题的 KOL",
        f"- shortlist 目标数量：{config.shortlist_target}",
        f"- shortlist 最低粉丝门槛：{config.min_followers_for_shortlist}",
        "",
        "## 本轮产出",
        "",
        f"- raw tweets: {len(raw_rows)}",
        f"- normalized candidates: {len(normalized_rows)}",
        f"- shortlist rows: {len(shortlist_rows)}",
        f"- keep candidates: {keep_count}",
        f"- review candidates: {review_count}",
        "",
        "## Query 覆盖",
        "",
    ]
    for meta in search_meta:
        lines.append(f"- `{meta['query_name']}`: {meta['result_count']} tweets")
    lines.extend(
        [
            "",
            "## User Info 补全",
            "",
            f"- user-info batches: {len(user_info_meta)}",
            f"- user-info resolved profiles: {sum(item['resolved_count'] for item in user_info_meta)}",
            "",
            "## 文件落盘",
            "",
        ]
    )
    for label, file_path in file_map.items():
        lines.append(f"- `{label}`: {file_path.name}")
    lines.extend(
        [
            "",
            "## 当前判断",
            "",
            "- 本轮 MVP 默认 provider 仍是 `Scweet`。",
            "- 当前 shortlist 为 `Scweet search -> user-level aggregate -> Scweet user-info enrichment -> basic scoring` 的最小闭环。",
            "- `followers_count < 1000` 的账号不会直接进 `keep`，但可能仍进入 `review` 便于后续人工复核。",
            "- `crypto / trader / airdrop / memecoin` 等噪音关键词会显著降权。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    config = RunConfig()
    tests_dir, project_root = _root_paths()
    out_dir = _workbench_dir(project_root)
    env = load_simple_env(tests_dir / ".env.layer1.local")
    auth_token = env["X_AUTH_TOKEN"]
    search_db_path = out_dir / "scweet_search_state_2026-03-31.db"
    user_info_db_path = out_dir / "scweet_userinfo_state_2026-03-31.db"
    if search_db_path.exists():
        search_db_path.unlink()
    if user_info_db_path.exists():
        user_info_db_path.unlink()

    timestamp = "2026-03-31"
    raw_json_path = out_dir / f"x_kol_mvp_raw_candidates_{timestamp}.json"
    raw_csv_path = out_dir / f"x_kol_mvp_raw_candidates_{timestamp}.csv"
    normalized_csv_path = out_dir / f"x_kol_mvp_normalized_candidates_{timestamp}.csv"
    shortlist_csv_path = out_dir / f"x_kol_mvp_shortlist_{config.shortlist_target}_{timestamp}.csv"
    summary_md_path = out_dir / f"x_kol_mvp_summary_{timestamp}.md"

    raw_rows: list[dict[str, Any]] = []
    search_meta: list[dict[str, Any]] = []
    for query_name, query_text in QUERY_SPECS:
        rows, meta = _search_rows(auth_token, search_db_path, query_name, query_text, config)
        search_meta.append(meta)
        for row in rows:
            raw_rows.append(
                {
                    "provider": "scweet",
                    "query_name": query_name,
                    "query_text": query_text,
                    "tweet_id": row.get("tweet_id"),
                    "username": ((row.get("user") or {}).get("screen_name") or "").lower(),
                    "display_name": (row.get("user") or {}).get("name") or "",
                    "timestamp": row.get("timestamp") or "",
                    "text": _safe_text(row.get("text")),
                    "comments": int(row.get("comments") or 0),
                    "likes": int(row.get("likes") or 0),
                    "retweets": int(row.get("retweets") or 0),
                    "tweet_url": row.get("tweet_url") or "",
                    "raw": json.dumps(row, ensure_ascii=False),
                }
            )

    candidate_usernames = sorted(
        {
            row["username"]
            for row in raw_rows
            if row["username"] and _keyword_hits(" ".join([row["text"], row["username"]]), BAD_KEYWORDS) == 0
        }
    )
    profile_map, user_info_meta = _fetch_user_info(auth_token, user_info_db_path, candidate_usernames, config)
    normalized_rows = _normalize_rows(raw_rows, profile_map, config)

    shortlist_rows = [
        row
        for row in normalized_rows
        if row["recommended_action"] in {"keep", "review"}
    ][: config.shortlist_target]

    raw_json_path.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(UTC).isoformat(),
                "config": {
                    "since": config.since,
                    "until": config.until,
                    "per_query_limit": config.per_query_limit,
                    "shortlist_target": config.shortlist_target,
                    "queries": QUERY_SPECS,
                },
                "search_meta": search_meta,
                "rows": raw_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(raw_csv_path, raw_rows)
    _write_csv(normalized_csv_path, normalized_rows)
    _write_csv(shortlist_csv_path, shortlist_rows)
    _write_summary(
        summary_md_path,
        config,
        search_meta,
        user_info_meta,
        raw_rows,
        normalized_rows,
        shortlist_rows,
        {
            "raw_json": raw_json_path,
            "raw_csv": raw_csv_path,
            "normalized_csv": normalized_csv_path,
            "shortlist_csv": shortlist_csv_path,
            "summary_md": summary_md_path,
        },
    )

    print(summary_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
