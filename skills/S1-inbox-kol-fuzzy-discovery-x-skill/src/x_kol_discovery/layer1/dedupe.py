from __future__ import annotations


def dedupe_raw_rows(raw_rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in raw_rows:
        username = str(row.get("username") or "").strip().lower()
        tweet_id = str(row.get("tweet_id") or "").strip()
        key = f"{username}:{tweet_id}"
        if not username or not tweet_id or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def unique_usernames(raw_rows: list[dict]) -> list[str]:
    return sorted({str(row.get("username") or "").strip().lower() for row in raw_rows if row.get("username")})

