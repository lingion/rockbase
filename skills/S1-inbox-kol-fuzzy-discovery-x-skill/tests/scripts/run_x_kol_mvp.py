from __future__ import annotations

import csv
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from common_env import load_simple_env, tests_root
from Scweet import Scweet
from Scweet.config import ScweetConfig


POSITIVE_TERMS = {
    "openclaw",
    "ai",
    "agent",
    "agents",
    "automation",
    "workflow",
    "developer",
    "developers",
    "devtools",
    "builder",
    "builders",
    "founder",
    "founders",
    "coding",
    "engineer",
    "engineering",
    "software",
    "startup",
    "productivity",
}

NEGATIVE_TERMS = {
    "crypto",
    "trader",
    "trading",
    "gold",
    "polymarket",
    "airdrop",
    "memecoin",
    "nft",
    "solana",
    "bitcoin",
    "btc",
    "eth",
}


@dataclass(frozen=True)
class SearchPlan:
    label: str
    query: str
    limit: int = 120
    display_type: str = "Top"
    min_likes: int | None = None
    min_retweets: int | None = None


SEARCH_PLANS = [
    SearchPlan(
        label="openclaw_core",
        query='"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools")',
        limit=120,
        display_type="Top",
    ),
    SearchPlan(
        label="openclaw_builders",
        query='"OpenClaw" (builders OR founders OR developers OR engineers)',
        limit=120,
        display_type="Top",
    ),
    SearchPlan(
        label="openclaw_workflows",
        query='"OpenClaw" (workflow OR workflows OR productivity OR automations)',
        limit=120,
        display_type="Top",
    ),
    SearchPlan(
        label="openclaw_reviews",
        query='"OpenClaw" (tutorial OR guide OR review OR demo OR walkthrough)',
        limit=120,
        display_type="Top",
    ),
    SearchPlan(
        label="openclaw_latest",
        query='"OpenClaw" (AI OR agents OR automation)',
        limit=120,
        display_type="Latest",
        min_likes=3,
        min_retweets=1,
    ),
]


def _project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "workbench").exists():
        return cwd
    for parent in Path(__file__).resolve().parents:
        if parent.name == ".agent":
            continue
        if (parent / "workbench").exists():
            return parent
    raise FileNotFoundError("Could not locate project root containing workbench/")


def _workbench_dir(run_date: str) -> Path:
    return _project_root() / "workbench" / run_date


def _make_client(auth_token: str, db_path: Path) -> Scweet:
    return Scweet(
        auth_token=auth_token,
        db_path=str(db_path),
        config=ScweetConfig(concurrency=1),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    header: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                header.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _search(env_data: dict[str, str], plan: SearchPlan, db_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    error = ""
    try:
        cmd = [
            "bird",
            "--auth-token",
            env_data["X_AUTH_TOKEN"],
            "--ct0",
            env_data["X_CT0"],
            "--plain",
            "search",
            "--json",
            "-n",
            str(plan.limit),
            f"{plan.query} lang:en" if "lang:en" not in plan.query.lower() else plan.query,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "bird search failed")
        payload = json.loads(proc.stdout)
        for item in payload:
            author = item.get("author") or {}
            media_items = item.get("media") or []
            row = {
                "tweet_id": item.get("id") or "",
                "user": {
                    "screen_name": author.get("username") or "",
                    "name": author.get("name") or "",
                },
                "timestamp": item.get("createdAt") or "",
                "text": item.get("text") or "",
                "embedded_text": "",
                "emojis": "",
                "comments": _safe_int(item.get("replyCount")),
                "likes": _safe_int(item.get("likeCount")),
                "retweets": _safe_int(item.get("retweetCount")),
                "media": {
                    "image_links": [
                        media.get("url") or media.get("previewUrl") or ""
                        for media in media_items
                        if (media.get("url") or media.get("previewUrl"))
                    ]
                },
                "tweet_url": (
                    f"https://x.com/{author.get('username')}/status/{item.get('id')}"
                    if author.get("username") and item.get("id")
                    else ""
                ),
                "source_provider": "bird",
                "source_query_label": plan.label,
                "source_query": plan.query,
                "source_display_type": plan.display_type,
            }
            rows.append(row)
        returncode = 0
    except Exception as exc:
        error = str(exc)
        returncode = 1

    meta = {
        "label": plan.label,
        "query": plan.query,
        "display_type": plan.display_type,
        "limit": plan.limit,
        "min_likes": plan.min_likes,
        "min_retweets": plan.min_retweets,
        "returncode": returncode,
        "result_count": len(rows),
        "stderr_preview": error[:4000],
    }
    return rows, meta


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def _fetch_user_info(auth_token: str, usernames: list[str], db_path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    enriched: dict[str, dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []
    client = _make_client(auth_token, db_path)

    def _store(payload: list[dict[str, Any]]) -> None:
        for row in payload:
            username = (row.get("username") or "").strip()
            if username:
                enriched[username.lower()] = row

    for batch in _chunked(usernames, 25):
        payload: list[dict[str, Any]] = []
        error = ""
        returncode = 0
        try:
            payload = client.get_user_info(batch)
            _store(payload)
        except Exception as exc:
            returncode = 1
            error = str(exc)
        calls.append(
            {
                "batch_size": len(batch),
                "usernames": batch,
                "returncode": returncode,
                "result_count": len(payload),
                "stderr_preview": error[:2000],
            }
        )
        if returncode == 0 and not payload and len(batch) > 1:
            for username in batch:
                try:
                    single_payload = client.get_user_info([username])
                    _store(single_payload)
                    calls.append(
                        {
                            "batch_size": 1,
                            "usernames": [username],
                            "returncode": 0,
                            "result_count": len(single_payload),
                            "stderr_preview": "",
                        }
                    )
                except Exception as exc:
                    calls.append(
                        {
                            "batch_size": 1,
                            "usernames": [username],
                            "returncode": 1,
                            "result_count": 0,
                            "stderr_preview": str(exc)[:2000],
                        }
                    )
    return enriched, calls


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text_hits(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None


def _normalize_candidates(raw_rows: list[dict[str, Any]], user_info_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, dict[str, Any]] = {}

    for row in raw_rows:
        username = ((row.get("user") or {}).get("screen_name") or "").strip()
        if not username:
            continue

        key = username.lower()
        likes = _safe_int(row.get("likes"))
        retweets = _safe_int(row.get("retweets"))
        comments = _safe_int(row.get("comments"))
        timestamp = row.get("timestamp")
        timestamp_dt = _parse_timestamp(timestamp)
        text = row.get("text") or ""

        slot = by_user.setdefault(
            key,
            {
                "username": username,
                "display_name": (row.get("user") or {}).get("name") or "",
                "tweet_count": 0,
                "max_likes": 0,
                "max_retweets": 0,
                "max_comments": 0,
                "top_tweet_id": "",
                "top_tweet_url": "",
                "top_tweet_text": "",
                "latest_tweet_timestamp": "",
                "latest_tweet_ts": None,
                "source_query_labels": set(),
                "source_queries": set(),
                "openclaw_tweet_count": 0,
                "total_engagement": 0,
            },
        )

        slot["tweet_count"] = _safe_int(slot["tweet_count"]) + 1
        slot["max_likes"] = max(_safe_int(slot["max_likes"]), likes)
        slot["max_retweets"] = max(_safe_int(slot["max_retweets"]), retweets)
        slot["max_comments"] = max(_safe_int(slot["max_comments"]), comments)
        slot["total_engagement"] = _safe_int(slot["total_engagement"]) + likes + retweets + comments
        slot["source_query_labels"].add(row.get("source_query_label") or "")
        slot["source_queries"].add(row.get("source_query") or "")

        if "openclaw" in text.lower():
            slot["openclaw_tweet_count"] = _safe_int(slot["openclaw_tweet_count"]) + 1

        current_top_score = _safe_int(slot["max_likes"]) + (_safe_int(slot["max_retweets"]) * 2)
        candidate_top_score = likes + (retweets * 2)
        if not slot["top_tweet_id"] or candidate_top_score >= current_top_score:
            slot["top_tweet_id"] = row.get("tweet_id") or ""
            slot["top_tweet_url"] = row.get("tweet_url") or ""
            slot["top_tweet_text"] = text[:500]

        if timestamp_dt and (slot["latest_tweet_ts"] is None or timestamp_dt > slot["latest_tweet_ts"]):
            slot["latest_tweet_ts"] = timestamp_dt
            slot["latest_tweet_timestamp"] = timestamp or ""

    normalized: list[dict[str, Any]] = []
    for key, slot in by_user.items():
        info = user_info_map.get(key, {})
        bio = info.get("description") or ""
        profile_text = " ".join(
            [
                slot.get("display_name") or "",
                bio,
                slot.get("top_tweet_text") or "",
                " ".join(sorted(slot["source_query_labels"])),
            ]
        ).strip()
        positive_hits = _text_hits(profile_text, POSITIVE_TERMS)
        negative_hits = _text_hits(profile_text, NEGATIVE_TERMS)
        followers_count = _safe_int(info.get("followers_count"))
        score = (
            (_safe_int(slot["openclaw_tweet_count"]) * 10)
            + min(_safe_int(slot["tweet_count"]) * 2, 12)
            + min(positive_hits * 3, 18)
            - min(negative_hits * 5, 20)
            + min(int(math.log10(max(followers_count, 1) + 1) * 6), 24)
            + min(_safe_int(slot["max_likes"]) // 20, 20)
            + min(_safe_int(slot["max_retweets"]) // 10, 20)
        )
        normalized.append(
            {
                "username": slot["username"],
                "display_name": slot["display_name"],
                "followers_count": followers_count,
                "following_count": _safe_int(info.get("following_count")),
                "statuses_count": _safe_int(info.get("statuses_count")),
                "listed_count": _safe_int(info.get("listed_count")),
                "verified": bool(info.get("verified")),
                "blue_verified": bool(info.get("blue_verified")),
                "protected": bool(info.get("protected")),
                "location": info.get("location") or "",
                "bio": bio,
                "website_url": info.get("url") or "",
                "tweet_count": _safe_int(slot["tweet_count"]),
                "openclaw_tweet_count": _safe_int(slot["openclaw_tweet_count"]),
                "max_likes": _safe_int(slot["max_likes"]),
                "max_retweets": _safe_int(slot["max_retweets"]),
                "max_comments": _safe_int(slot["max_comments"]),
                "total_engagement": _safe_int(slot["total_engagement"]),
                "source_query_count": len(slot["source_query_labels"]),
                "source_query_labels": " | ".join(sorted(v for v in slot["source_query_labels"] if v)),
                "latest_tweet_timestamp": slot["latest_tweet_timestamp"],
                "top_tweet_id": slot["top_tweet_id"],
                "top_tweet_url": slot["top_tweet_url"],
                "top_tweet_text": slot["top_tweet_text"],
                "positive_hits": positive_hits,
                "negative_hits": negative_hits,
                "topic_score": score,
            }
        )

    normalized.sort(
        key=lambda row: (
            row["topic_score"],
            row["followers_count"],
            row["max_likes"],
            row["source_query_count"],
        ),
        reverse=True,
    )
    return normalized


def _build_shortlist(candidates: list[dict[str, Any]], target_size: int = 100) -> list[dict[str, Any]]:
    strict = [
        row
        for row in candidates
        if row["followers_count"] >= 1000
        and not row["protected"]
        and row["negative_hits"] <= max(1, row["positive_hits"])
        and row["topic_score"] >= 16
    ]
    if len(strict) >= target_size:
        return strict[:target_size]

    medium = [
        row
        for row in candidates
        if row["followers_count"] >= 1000
        and not row["protected"]
        and row["topic_score"] >= 10
    ]
    if len(medium) >= target_size:
        return medium[:target_size]

    fallback = [
        row
        for row in candidates
        if row["followers_count"] >= 1000 and not row["protected"]
    ]
    return fallback[:target_size]


def _build_summary(
    run_date: str,
    raw_rows: list[dict[str, Any]],
    normalized_rows: list[dict[str, Any]],
    shortlist_rows: list[dict[str, Any]],
    search_meta: list[dict[str, Any]],
    user_info_calls: list[dict[str, Any]],
) -> str:
    lines = [
        f"# X KOL MVP Summary - {run_date}",
        "",
        "## Goal",
        "",
        "- Produce an MVP shortlist of at least 100 X KOL candidates around OpenClaw / AI agents / automation / developer tools.",
        "",
        "## Search Runs",
        "",
    ]
    for item in search_meta:
        lines.extend(
            [
                f"- `{item['label']}`",
                f"  - query: `{item['query']}`",
                f"  - display_type: `{item['display_type']}`",
                f"  - limit: `{item['limit']}`",
                f"  - result_count: `{item['result_count']}`",
                f"  - returncode: `{item['returncode']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Output Counts",
            "",
            f"- raw tweet rows: `{len(raw_rows)}`",
            f"- normalized candidates: `{len(normalized_rows)}`",
            f"- shortlist rows: `{len(shortlist_rows)}`",
            "",
            "## User Info Enrichment",
            "",
            f"- user-info batch calls: `{len(user_info_calls)}`",
            f"- successful user-info calls: `{sum(1 for item in user_info_calls if item['returncode'] == 0)}`",
            "",
            "## Notes",
            "",
            "- Raw data preserves tweet-level discovery evidence.",
            "- Normalized data is the deduped candidate pool with profile enrichment and topic scoring.",
            "- Shortlist applies follower and relevance filters for a same-day MVP output.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    env_data = load_simple_env(tests_root() / ".env.layer1.local")
    run_date = date.today().isoformat()
    workbench_dir = _workbench_dir(run_date)
    workbench_dir.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict[str, Any]] = []
    search_meta: list[dict[str, Any]] = []
    for plan in SEARCH_PLANS:
        search_db_path = tests_root() / "results" / f"scweet_mvp_search_{plan.label}_{run_date}.db"
        rows, meta = _search(env_data, plan, search_db_path)
        raw_rows.extend(rows)
        search_meta.append(meta)

    usernames = sorted(
        {
            ((row.get("user") or {}).get("screen_name") or "").strip().lower()
            for row in raw_rows
            if ((row.get("user") or {}).get("screen_name") or "").strip()
        }
    )
    user_info_db_path = tests_root() / "results" / f"scweet_mvp_userinfo_{run_date}.db"
    user_info_map, user_info_calls = _fetch_user_info(env_data["X_AUTH_TOKEN"], usernames, user_info_db_path)
    normalized_rows = _normalize_candidates(raw_rows, user_info_map)
    shortlist_rows = _build_shortlist(normalized_rows, target_size=100)

    raw_json_path = workbench_dir / f"x_kol_mvp_raw_candidates_{run_date}.json"
    normalized_csv_path = workbench_dir / f"x_kol_mvp_normalized_candidates_{run_date}.csv"
    shortlist_csv_path = workbench_dir / f"x_kol_mvp_shortlist_{len(shortlist_rows)}_{run_date}.csv"
    summary_md_path = workbench_dir / f"x_kol_mvp_summary_{run_date}.md"
    run_log_json_path = workbench_dir / f"x_kol_mvp_runlog_{run_date}.json"

    _write_json(raw_json_path, raw_rows)
    _write_csv(normalized_csv_path, normalized_rows)
    _write_csv(shortlist_csv_path, shortlist_rows)
    _write_json(
        run_log_json_path,
        {
            "run_date": run_date,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "search_meta": search_meta,
            "user_info_calls": user_info_calls,
            "raw_count": len(raw_rows),
            "normalized_count": len(normalized_rows),
            "shortlist_count": len(shortlist_rows),
        },
    )
    summary_md_path.write_text(
        _build_summary(run_date, raw_rows, normalized_rows, shortlist_rows, search_meta, user_info_calls),
        encoding="utf-8",
    )

    print(json.dumps(
        {
            "raw_json": str(raw_json_path),
            "normalized_csv": str(normalized_csv_path),
            "shortlist_csv": str(shortlist_csv_path),
            "summary_md": str(summary_md_path),
            "runlog_json": str(run_log_json_path),
            "raw_count": len(raw_rows),
            "normalized_count": len(normalized_rows),
            "shortlist_count": len(shortlist_rows),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
