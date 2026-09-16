from __future__ import annotations

from typing import Any

from x_kol_discovery.config import Layer1RunConfig
from x_kol_discovery.io_utils import safe_text
from x_kol_discovery.layer1.scweet_adapter import ScweetCliAdapter
from x_kol_discovery.layer2.scrapecreators_client import ScrapeCreatorsClient, extract_email, merge_links, normalize_followers


ROLE_KEYWORDS = {"founder", "builder", "engineer", "researcher", "creator", "developer"}
BAD_KEYWORDS = {"crypto", "trader", "airdrop", "memecoin", "pump", "signals", "polymarket", "gold", "forex"}
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


def _keyword_hits(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


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
    import math

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


def _recommended_action(overall_score: float, followers_count: int, bad_keyword_hits: int, min_followers_for_keep: int) -> str:
    if bad_keyword_hits > 0:
        return "drop"
    if followers_count >= min_followers_for_keep and overall_score >= 60:
        return "keep"
    if overall_score >= 42:
        return "review"
    return "drop"


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def sort_rows_by_followers_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = list(rows)
    ordered.sort(
        key=lambda row: (
            -_to_int(row.get("followers_count")),
            -float(row.get("overall_score") or 0),
            -_to_int(row.get("tweet_count")),
            safe_text(row.get("username")),
        )
    )
    return ordered


def _extract_scrapecreators_external_links(payload: dict[str, Any]) -> str:
    legacy = payload.get("legacy") or {}
    entities = legacy.get("entities") or {}
    values: list[str] = []
    for scope in ["url", "description"]:
        for item in ((entities.get(scope) or {}).get("urls") or []):
            link = safe_text(item.get("expanded_url") or item.get("url"))
            if link and link not in values:
                values.append(link)
    return " | ".join(values)


def _extract_scrapecreators_verified(payload: dict[str, Any]) -> bool:
    if isinstance(payload.get("verified"), bool):
        return bool(payload.get("verified"))
    verification = payload.get("verification") or {}
    if isinstance(verification, dict) and isinstance(verification.get("verified"), bool):
        return bool(verification.get("verified"))
    legacy = payload.get("legacy") or {}
    if isinstance(legacy.get("verified"), bool):
        return bool(legacy.get("verified"))
    return False


def _build_enriched_row(
    candidate: dict[str, Any],
    config: Layer1RunConfig,
    *,
    description: str,
    followers: int,
    following: int,
    statuses: int,
    verified: bool,
    blue_verified: bool,
    location: str,
    display_name: str,
    enrichment_provider: str,
    external_links: str = "",
    contact_value: str = "",
    contact_note: str = "",
) -> dict[str, Any]:
    username = str(candidate.get("username") or "").strip().lower()
    sample_posts = safe_text(candidate.get("sample_posts"))
    matched_queries = safe_text(candidate.get("matched_queries"))
    bad_hits = _keyword_hits(" ".join([description, sample_posts]), BAD_KEYWORDS)
    topic_match_score = _topic_score(sample_posts, matched_queries, description)
    profile_match_score = round(_profile_score(description, followers, verified, blue_verified), 2)
    activity_score = _activity_score(
        int(candidate.get("max_likes") or 0),
        int(candidate.get("max_retweets") or 0),
        int(candidate.get("tweet_count") or 0),
    )
    overall_score = round(topic_match_score + profile_match_score + activity_score, 2)
    recommended_action = _recommended_action(
        overall_score,
        followers,
        bad_hits,
        config.min_followers_for_keep,
    )
    row = dict(candidate)
    row.update(
        {
        "username": username,
        "display_name": display_name,
        "bio": description,
        "location_raw": location,
        "followers_count": followers,
        "following_count": following,
        "tweet_count": int(candidate.get("tweet_count") or 0),
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
        "top_tweet_url": safe_text(candidate.get("top_tweet_url")),
        "profile_url": f"https://x.com/{username}",
        "source_tweet_ids": safe_text(candidate.get("source_tweet_ids")),
        "bad_keyword_hits": bad_hits,
        "provider_source": safe_text(candidate.get("provider_source")) or "scweet",
        "enrichment_provider": enrichment_provider,
        "external_links": external_links,
        "contact_value": contact_value,
        "contact_note": contact_note,
        }
    )
    return row


def build_enriched_row_from_profile(
    candidate: dict[str, Any],
    config: Layer1RunConfig,
    *,
    description: str,
    followers: int,
    following: int,
    statuses: int,
    verified: bool,
    blue_verified: bool,
    location: str,
    display_name: str,
    enrichment_provider: str,
    external_links: str = "",
    contact_value: str = "",
    contact_note: str = "",
) -> dict[str, Any]:
    return _build_enriched_row(
        candidate,
        config,
        description=description,
        followers=followers,
        following=following,
        statuses=statuses,
        verified=verified,
        blue_verified=blue_verified,
        location=location,
        display_name=display_name,
        enrichment_provider=enrichment_provider,
        external_links=external_links,
        contact_value=contact_value,
        contact_note=contact_note,
    )


def build_layer2_default_row(candidate: dict[str, Any], config: Layer1RunConfig, *, eligible: bool) -> dict[str, Any]:
    username = str(candidate.get("username") or "").strip().lower()
    row = dict(candidate)
    row.update(
        {
            "bio": "",
            "location_raw": "",
            "followers_count": 0,
            "following_count": 0,
            "statuses_count": 0,
            "verified": False,
            "blue_verified": False,
            "profile_match_score": 0,
            "topic_match_score": 0,
            "activity_score": 0,
            "overall_score": 0,
            "recommended_action": "drop",
            "profile_url": f"https://x.com/{username}" if username else "",
            "bad_keyword_hits": 0,
            "provider_source": str(row.get("provider_source") or "scweet"),
            "enrichment_provider": "",
            "external_links": "",
            "contact_value": "",
            "contact_note": "",
            "layer2_eligible": "yes" if eligible else "no",
            "layer2_skip_reason": "" if eligible else f"max_views_below_{config.layer2_min_max_views}",
        }
    )
    return row


def combine_layer2_results(
    candidates: list[dict[str, Any]],
    enriched_candidates: list[dict[str, Any]],
    config: Layer1RunConfig,
) -> list[dict[str, Any]]:
    enriched_by_username = {str(row.get("username") or "").strip().lower(): row for row in enriched_candidates}
    final_enriched_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        username = str(candidate.get("username") or "").strip().lower()
        if username in enriched_by_username:
            row = dict(enriched_by_username[username])
            row["layer2_eligible"] = "yes"
            row["layer2_skip_reason"] = ""
            final_enriched_candidates.append(row)
            continue
        final_enriched_candidates.append(build_layer2_default_row(candidate, config, eligible=False))
    return final_enriched_candidates


def apply_layer2_views_gate(
    candidates: list[dict[str, Any]],
    min_max_views: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        max_views = _to_int(row.get("max_views"))
        row["layer2_eligible"] = "yes" if max_views >= min_max_views else "no"
        row["layer2_skip_reason"] = "" if max_views >= min_max_views else f"max_views_below_{min_max_views}"
        if max_views >= min_max_views:
            eligible.append(row)
        else:
            skipped.append(row)
    return eligible, skipped


class ScweetUserInfoEnricher:
    """Minimal runnable Layer2 enrichment using Scweet user-info."""

    def __init__(self, adapter: ScweetCliAdapter) -> None:
        self.adapter = adapter

    def enrich_candidates(
        self,
        candidates: list[dict[str, Any]],
        config: Layer1RunConfig,
        db_path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        usernames = [str(item.get("username") or "").strip().lower() for item in candidates if item.get("username")]
        profile_map, batch_meta = self.adapter.fetch_user_info(usernames, config=config, db_path=db_path)
        enriched: list[dict[str, Any]] = []
        for candidate in candidates:
            username = str(candidate.get("username") or "").strip().lower()
            profile = profile_map.get(username, {})
            description = safe_text(profile.get("description"))
            followers = int(profile.get("followers_count") or 0)
            following = int(profile.get("following_count") or 0)
            statuses = int(profile.get("statuses_count") or 0)
            verified = bool(profile.get("verified", False))
            blue_verified = bool(profile.get("blue_verified", False))
            location = safe_text(profile.get("location"))
            display_name = safe_text(profile.get("name")) or safe_text(candidate.get("display_name"))
            enriched.append(
                _build_enriched_row(
                    candidate,
                    config,
                    description=description,
                    followers=followers,
                    following=following,
                    statuses=statuses,
                    verified=verified,
                    blue_verified=blue_verified,
                    location=location,
                    display_name=display_name,
                    enrichment_provider="scweet_user_info",
                )
            )
        return sort_rows_by_followers_desc(enriched), batch_meta


def enrich_with_scweet_user_info(
    candidates: list[dict[str, Any]],
    adapter: ScweetCliAdapter,
    config: Layer1RunConfig,
    db_path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    enricher = ScweetUserInfoEnricher(adapter)
    return enricher.enrich_candidates(candidates, config=config, db_path=db_path)


def enrich_with_scrapecreators_twitter_profile(
    candidates: list[dict[str, Any]],
    config: Layer1RunConfig,
    client: ScrapeCreatorsClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    api = client or ScrapeCreatorsClient()
    enriched: list[dict[str, Any]] = []
    meta: list[dict[str, Any]] = []
    for candidate in candidates:
        username = str(candidate.get("username") or "").strip().lower()
        if not username:
            continue
        try:
            payload = api.get_twitter_profile(username)
            legacy = payload.get("legacy") or {}
            core = payload.get("core") or {}
            description = safe_text(legacy.get("description"))
            followers = _to_int(legacy.get("followers_count"))
            following = _to_int(legacy.get("friends_count"))
            statuses = _to_int(legacy.get("statuses_count"))
            verified = _extract_scrapecreators_verified(payload)
            blue_verified = bool(payload.get("is_blue_verified"))
            location = safe_text(legacy.get("location"))
            display_name = safe_text(core.get("name") or legacy.get("name")) or safe_text(candidate.get("display_name"))
            external_links = _extract_scrapecreators_external_links(payload)
            contact_value, contact_note_source = extract_email(description)
            contact_note = ""
            if contact_value:
                contact_note = f"来源: {contact_note_source} | 结果: 命中邮箱"
            enriched.append(
                _build_enriched_row(
                    candidate,
                    config,
                    description=description,
                    followers=followers,
                    following=following,
                    statuses=statuses,
                    verified=verified,
                    blue_verified=blue_verified,
                    location=location,
                    display_name=display_name,
                    enrichment_provider="scrapecreators_twitter_profile",
                    external_links=external_links,
                    contact_value=contact_value,
                    contact_note=contact_note,
                )
            )
            meta.append(
                {
                    "username": username,
                    "status": "ok",
                    "provider": "scrapecreators_twitter_profile",
                    "credits_remaining": payload.get("credits_remaining"),
                    "followers_count": followers,
                    "location_raw": location,
                    "external_links_count": len([item for item in external_links.split(" | ") if item]),
                    "has_contact_value": bool(contact_value),
                }
            )
        except Exception as exc:
            meta.append(
                {
                    "username": username,
                    "status": "request_error",
                    "provider": "scrapecreators_twitter_profile",
                    "error": str(exc),
                }
            )
    return sort_rows_by_followers_desc(enriched), meta


def build_layer2_payload_snapshot(
    provider: str,
    source_candidates_csv: str,
    enrichment_meta: list[dict[str, Any]],
    enriched_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "provider": provider,
        "source_candidates_csv": source_candidates_csv,
        "enrichment_meta": enrichment_meta,
        "items": enriched_candidates,
    }


def build_contact_enrichment_stub(candidate: dict[str, Any]) -> dict[str, Any]:
    bio = safe_text(candidate.get("bio"))
    email = safe_text(candidate.get("contact_value"))
    email_source = safe_text(candidate.get("contact_note"))
    if not email:
        email, email_source = extract_email(bio)
    existing_links = safe_text(candidate.get("external_links"))
    links = merge_links(existing_links, [])
    return {
        "username": safe_text(candidate.get("username")).lower(),
        "email": email,
        "email_source": email_source,
        "normalized_followers_text": normalize_followers(candidate.get("followers_count")),
        "merged_links": links,
    }
