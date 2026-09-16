from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from youtube_kol_discovery.io_utils import get_env_value, safe_text
from youtube_kol_discovery.layer2.contact_page_crawler import ContactPageCrawler
from youtube_kol_discovery.layer2.scrapecreators_client import (
    ScrapeCreatorsClient,
    contact_links_from_payload,
    extract_email,
    merge_links,
)


ROLE_KEYWORDS = {"founder", "builder", "creator", "engineer", "developer", "researcher"}
TOPIC_KEYWORDS = {
    "ai",
    "agent",
    "agents",
    "automation",
    "workflow",
    "tool",
    "tools",
    "devtools",
    "build",
    "builder",
    "coding",
    "nocode",
}
BAD_KEYWORDS = {"crypto", "trader", "forex", "signals", "memecoin", "airdrop"}
MIN_FOLLOWERS_FOR_L2 = 1000


@dataclass(frozen=True)
class Layer2GateDecision:
    layer2_eligible: str
    layer2_skip_reason: str
    recommended_action: str


def _keyword_hits(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def _profile_score(description: str, followers: int, verified: bool) -> float:
    score = 0.0
    score += min(_keyword_hits(description, ROLE_KEYWORDS) * 8, 24)
    if followers >= 1000:
        score += 10
    if followers >= 10000:
        score += 8
    if followers >= 100000:
        score += 8
    if verified:
        score += 6
    if _keyword_hits(description, BAD_KEYWORDS):
        score -= 18
    return round(score, 2)


def _topic_score(sample_contents: str, matched_queries: str, description: str) -> float:
    text = " ".join([sample_contents, matched_queries, description]).lower()
    score = min(_keyword_hits(text, TOPIC_KEYWORDS) * 4.5, 45)
    if _keyword_hits(text, BAD_KEYWORDS):
        score -= 16
    return round(max(score, 0), 2)


def _activity_score(max_views: int, max_likes: int, matched_content_count: int) -> float:
    import math

    engagement_score = min(math.log10(max(max_views + max_likes * 5, 1)) * 12, 42)
    volume_score = min(matched_content_count * 2.5, 18)
    return round(engagement_score + volume_score, 2)


def _recommended_action(overall_score: float, followers_count: int, bad_keyword_hits: int) -> str:
    if bad_keyword_hits > 0:
        return "drop"
    if followers_count >= MIN_FOLLOWERS_FOR_L2 and overall_score >= 56:
        return "keep"
    if overall_score >= 38:
        return "review"
    return "drop"


def evaluate_layer2_gate(followers_count: int, bad_keyword_hits: int) -> Layer2GateDecision:
    if bad_keyword_hits > 0:
        return Layer2GateDecision(
            layer2_eligible="no",
            layer2_skip_reason="bad_keyword_hit",
            recommended_action="drop",
        )
    if followers_count < MIN_FOLLOWERS_FOR_L2:
        return Layer2GateDecision(
            layer2_eligible="no",
            layer2_skip_reason=f"followers_below_{MIN_FOLLOWERS_FOR_L2}",
            recommended_action="drop",
        )
    return Layer2GateDecision(
        layer2_eligible="yes",
        layer2_skip_reason="",
        recommended_action="review",
    )


def _extract_links_from_description(description: str) -> list[str]:
    links: list[str] = []
    for token in description.replace("\n", " ").split():
        text = token.strip(".,;()[]{}<>")
        if text.startswith("http://") or text.startswith("https://"):
            if text not in links:
                links.append(text)
    return links


def map_account_category_platform(scrapecreators_tags: str) -> str:
    return safe_text(scrapecreators_tags)


class YouTubeChannelEnricher:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.scrapecreators_client: ScrapeCreatorsClient | None = self._build_scrapecreators_client()
        self.contact_page_crawler = ContactPageCrawler()

    def enrich_candidates(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        api_key = self._get_api_key()
        metadata = self._fetch_channel_metadata(candidates, api_key=api_key) if api_key else {}
        enable_contact_crawl = bool(get_env_value("ENABLE_CONTACT_CRAWL", "YOUTUBE_ENABLE_CONTACT_CRAWL"))
        skip_contact_crawl = not enable_contact_crawl

        rows: list[dict[str, Any]] = []
        runlog: list[dict[str, Any]] = []
        for candidate in candidates:
            creator_handle = safe_text(candidate.get("creator_handle"))
            channel_id = safe_text(candidate.get("channel_id"))
            channel_meta = metadata.get(channel_id, {}) if channel_id else {}
            description = safe_text(channel_meta.get("description"))
            followers = self._to_int(channel_meta.get("subscriberCount"))
            video_count = self._to_int(channel_meta.get("videoCount"))
            verified = bool(channel_meta.get("verified", False))
            links = _extract_links_from_description(description)
            profile_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
            scrape_status = "not_attempted"
            scrape_payload: dict[str, Any] = {}
            contact_value = ""
            contact_note = "no direct email parsing yet"
            email_source_url = ""
            contact_page_crawl_status = "disabled_by_default"
            contact_page_checked_urls = ""
            if self.scrapecreators_client and profile_url:
                try:
                    scrape_payload = self.scrapecreators_client.get_youtube_channel(profile_url)
                    scrape_status = "ok" if scrape_payload.get("success", True) else "not_successful"
                    if scrape_status == "ok":
                        description = description or safe_text(scrape_payload.get("description"))
                        followers = followers or self._to_int(scrape_payload.get("subscriberCount"))
                        video_count = video_count or self._to_int(scrape_payload.get("videoCount"))
                        verified = verified or bool(scrape_payload.get("isVerified"))
                        contact_value, contact_note = extract_email(scrape_payload)
                        scrape_links = contact_links_from_payload(scrape_payload)
                        merged_links = merge_links(" | ".join(links), scrape_links)
                        links = [item for item in merged_links.split(" | ") if item]
                except requests.RequestException as exc:
                    scrape_status = f"request_error:{safe_text(exc)[:160]}"
                except Exception as exc:  # noqa: BLE001 - fallback should never break primary YouTube API enrichment.
                    scrape_status = f"error:{safe_text(exc)[:160]}"
            if not contact_value and links and not skip_contact_crawl:
                crawl_result = self.contact_page_crawler.find_email(" | ".join(links))
                contact_page_crawl_status = crawl_result.crawl_status
                contact_page_checked_urls = crawl_result.checked_urls_text()
                if crawl_result.email:
                    contact_value = crawl_result.email
                    email_source_url = crawl_result.email_source_url
                    contact_note = f"contact page crawl: {crawl_result.email_source_url}"
            bad_hits = _keyword_hits(" ".join([description, safe_text(candidate.get("sample_contents"))]), BAD_KEYWORDS)
            topic_match_score = _topic_score(
                safe_text(candidate.get("sample_contents")),
                safe_text(candidate.get("matched_queries")),
                description,
            )
            profile_match_score = _profile_score(description, followers, verified)
            activity_score = _activity_score(
                int(candidate.get("max_views") or 0),
                int(candidate.get("max_likes") or 0),
                int(candidate.get("matched_content_count") or 0),
            )
            overall_score = round(topic_match_score + profile_match_score + activity_score, 2)
            gate_decision = evaluate_layer2_gate(followers, bad_hits)
            recommended_action = gate_decision.recommended_action
            if gate_decision.layer2_eligible == "yes":
                recommended_action = _recommended_action(overall_score, followers, bad_hits)
            enriched = dict(candidate)
            account_category_platform = map_account_category_platform(
                safe_text(scrape_payload.get("tags")) if scrape_payload else ""
            )
            enriched.update(
                {
                    "bio": description,
                    "followers_count": followers,
                    "following_count": 0,
                    "statuses_count": video_count,
                    "video_count": video_count,
                    "verified": verified,
                    "profile_url": profile_url,
                    "账号分类_平台抓取": account_category_platform,
                    "external_links": " | ".join(links),
                    "contact_signals": " | ".join(links),
                    "contact_value": contact_value,
                    "contact_note": contact_note,
                    "email_source_url": email_source_url,
                    "contact_page_crawl_status": contact_page_crawl_status,
                    "contact_page_checked_urls": contact_page_checked_urls,
                    "recent_contents": safe_text(candidate.get("sample_contents")),
                    "profile_match_score": profile_match_score,
                    "topic_match_score": topic_match_score,
                    "activity_score": activity_score,
                    "overall_score": overall_score,
                    "layer2_eligible": gate_decision.layer2_eligible,
                    "layer2_skip_reason": gate_decision.layer2_skip_reason,
                    "recommended_action": recommended_action,
                    "bad_keyword_hits": bad_hits,
                    "scrapecreators_status": scrape_status,
                    "scrapecreators_handle": safe_text(scrape_payload.get("handle")) if scrape_payload else "",
                    "scrapecreators_tags": safe_text(scrape_payload.get("tags")) if scrape_payload else "",
                    "scrapecreators_keywords": safe_text(scrape_payload.get("keywords")) if scrape_payload else "",
                    "enrichment_provider": self._provider_label(api_key=api_key, scrape_status=scrape_status),
                }
            )
            rows.append(enriched)
            runlog.append(
                {
                    "creator_handle": creator_handle,
                    "channel_id": channel_id,
                    "metadata_status": "api" if channel_meta else "fallback",
                    "scrapecreators_status": scrape_status,
                    "contact_page_crawl_status": contact_page_crawl_status,
                    "followers_count": followers,
                    "video_count": video_count,
                    "overall_score": overall_score,
                }
            )

        rows.sort(
            key=lambda row: (
                -int(row.get("followers_count") or 0),
                -float(row.get("overall_score") or 0),
                -int(row.get("max_views") or 0),
                safe_text(row.get("creator_handle")),
            )
        )
        return rows, runlog

    def _fetch_channel_metadata(self, candidates: list[dict[str, Any]], *, api_key: str) -> dict[str, dict[str, Any]]:
        channel_ids = [
            safe_text(item.get("channel_id"))
            for item in candidates
            if safe_text(item.get("channel_id")) and not safe_text(item.get("channel_id")).startswith("channel_title:")
        ]
        unique_ids = []
        seen: set[str] = set()
        for channel_id in channel_ids:
            if channel_id not in seen:
                seen.add(channel_id)
                unique_ids.append(channel_id)
        if not unique_ids:
            return {}

        out: dict[str, dict[str, Any]] = {}
        for idx in range(0, len(unique_ids), 50):
            chunk = unique_ids[idx : idx + 50]
            params = {
                "part": "snippet,statistics,status",
                "id": ",".join(chunk),
                "key": api_key,
                "maxResults": len(chunk),
            }
            response = self.session.get("https://www.googleapis.com/youtube/v3/channels", params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("items", []):
                snippet = item.get("snippet") or {}
                statistics = item.get("statistics") or {}
                status = item.get("status") or {}
                out[safe_text(item.get("id"))] = {
                    "description": safe_text(snippet.get("description")),
                    "subscriberCount": statistics.get("subscriberCount"),
                    "videoCount": statistics.get("videoCount"),
                    "verified": bool(status.get("isLinked")),
                }
        return out

    def _get_api_key(self) -> str | None:
        value = get_env_value("YOUTUBE_API_KEY", "YT_API_KEY", "GOOGLE_API_KEY")
        return value or None

    def _build_scrapecreators_client(self) -> ScrapeCreatorsClient | None:
        if get_env_value("SKIP_SCRAPECREATORS", "DISABLE_SCRAPECREATORS"):
            return None
        if not get_env_value("SCRAPECREATORS_API_KEY"):
            return None
        try:
            return ScrapeCreatorsClient()
        except Exception:
            return None

    def _provider_label(self, *, api_key: str | None, scrape_status: str) -> str:
        providers = ["youtube.channels_api" if api_key else "youtube.search_fallback"]
        if scrape_status == "ok":
            providers.append("scrapecreators.youtube_channel")
        return " + ".join(providers)

    def _to_int(self, value: Any) -> int:
        try:
            return int(str(value or "0").replace(",", "").strip())
        except ValueError:
            return 0
