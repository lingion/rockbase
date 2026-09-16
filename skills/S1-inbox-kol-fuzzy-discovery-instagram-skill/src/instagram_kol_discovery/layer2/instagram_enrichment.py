from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from instagram_kol_discovery.io_utils import get_env_value, safe_text
from instagram_kol_discovery.layer2.contact_page_crawler import ContactPageCrawler, extract_emails_from_text


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
CONTACT_HINT_RE = re.compile(r"\b(email|contact|collab|partnership|business|inquiries|dm|link in bio)\b", re.I)
COUNTRY_HINTS = {
    "usa": "美国",
    "us": "美国",
    "united states": "美国",
    "uk": "英国",
    "london": "英国",
    "canada": "加拿大",
    "india": "印度",
    "singapore": "新加坡",
    "china": "中国",
    "hong kong": "中国香港",
}
LANGUAGE_HINTS = {
    "english": "英语",
    "en ": "英语",
    "español": "西班牙语",
    "spanish": "西班牙语",
    "中文": "中文",
    "mandarin": "中文",
}


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _normalize_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = safe_text(value).lower()
    if text in {"1", "true", "yes"}:
        return "yes"
    if text in {"0", "false", "no"}:
        return "no"
    return safe_text(value)


def _host_from_url(url: str) -> str:
    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    return parsed.netloc.lower()


def _collect_external_links(user_payload: dict[str, Any]) -> str:
    links: list[str] = []
    external_url = safe_text(user_payload.get("external_url"))
    if external_url:
        links.append(external_url)
    bio_links = user_payload.get("bio_links") or []
    if isinstance(bio_links, list):
        for item in bio_links:
            if not isinstance(item, dict):
                continue
            url = safe_text(item.get("url"))
            if url:
                links.append(url)
    deduped: list[str] = []
    for link in links:
        if link not in deduped:
            deduped.append(link)
    return " | ".join(deduped)


def _contact_signals(bio: str, external_links: str, business_email: str) -> str:
    parts: list[str] = []
    if business_email:
        parts.append("api_business_email")
    if EMAIL_RE.search(bio):
        parts.append("bio_email")
    if CONTACT_HINT_RE.search(bio):
        parts.append("bio_contact_hint")
    for link in [safe_text(part) for part in external_links.split(" | ") if safe_text(part)]:
        host = _host_from_url(link)
        if host:
            parts.append(f"link:{host}")
    deduped: list[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    return " | ".join(deduped)


def _infer_country_and_language(bio: str, external_links: str) -> tuple[str, str, str, str]:
    text = f"{bio} {external_links}".lower()
    country = ""
    confidence = ""
    for hint, label in COUNTRY_HINTS.items():
        if hint in text:
            country = label
            confidence = "medium"
            break
    language = ""
    for hint, label in LANGUAGE_HINTS.items():
        if hint in text:
            language = label
            break
    if not language:
        language = "英语"
    return country, confidence, language, language


def _extract_email(bio: str, business_email: str) -> tuple[str, str]:
    if business_email:
        return business_email, "来源: Instagram profile business_email"
    emails = extract_emails_from_text(bio)
    if emails:
        return emails[0], "来源: Instagram bio regex"
    return "", ""


def _topic_tokens(candidate: dict[str, Any]) -> list[str]:
    raw = " ".join(
        [
            safe_text(candidate.get("matched_queries")),
            safe_text(candidate.get("matched_query_text")),
            safe_text(candidate.get("matched_query_name")).replace("_", " "),
        ]
    ).lower()
    tokens: list[str] = []
    for chunk in re.split(r"[^a-z0-9]+", raw):
        token = chunk.strip()
        if len(token) < 3:
            continue
        if token in {"and", "the", "for", "with", "from", "that", "this", "tips", "hack", "hacks"}:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _score_topic(candidate: dict[str, Any], bio: str) -> int:
    text = f"{safe_text(candidate.get('matched_queries'))} {safe_text(candidate.get('sample_contents'))} {bio}".lower()
    score = 25
    matched_tokens = 0
    for token in _topic_tokens(candidate):
        if token in text:
            matched_tokens += 1
            score += 10
    if safe_text(candidate.get("content_tags_or_hashtags")):
        score += 5
    if safe_text(candidate.get("matched_content_count")) and _to_int(candidate.get("matched_content_count")) >= 2:
        score += 10
    if matched_tokens == 0:
        score -= 10
    return max(0, min(score, 100))


def _score_profile(followers_count: int, bio: str, external_links: str, verified: str) -> int:
    score = 20
    if followers_count >= 2000:
        score += 25
    if followers_count >= 10000:
        score += 10
    if bio:
        score += 15
    if external_links:
        score += 10
    if verified == "yes":
        score += 10
    return min(score, 100)


def _score_activity(candidate: dict[str, Any], statuses_count: int) -> int:
    score = 20
    max_views = _to_int(candidate.get("max_views"))
    matched_content_count = _to_int(candidate.get("matched_content_count"))
    if max_views >= 2000:
        score += 20
    if max_views >= 100000:
        score += 15
    if matched_content_count >= 2:
        score += 10
    if statuses_count >= 20:
        score += 10
    return min(score, 100)


def _score_contactability(contact_value: str, external_links: str, contact_signals: str) -> int:
    score = 10
    if contact_value:
        score += 55
    if external_links:
        score += 15
    if contact_signals:
        score += 10
    return min(score, 100)


def _recommended_action(*, followers_count: int, overall_score: float, contact_value: str, min_followers_for_l3: int) -> tuple[str, str]:
    if followers_count >= min_followers_for_l3 and overall_score >= 60:
        return "keep", "粉丝达标且主题/活跃度满足要求"
    if followers_count >= min_followers_for_l3:
        return "review", "粉丝达标，但主题或联系质量仍需人工判断"
    if followers_count <= 0:
        return "review", "粉丝数缺失，需要人工确认"
    if contact_value and overall_score >= 55:
        return "review", "粉丝未达标，但已有邮箱线索，可保留观察"
    return "drop", "粉丝数低于 L2 门槛"


class InstagramProfileEnricher:
    def __init__(self, *, min_followers_for_l3: int = 2000, skip_contact_crawl: bool = False) -> None:
        api_key = get_env_value("SCRAPECREATORS_API_KEY")
        if not api_key:
            raise RuntimeError("Missing SCRAPECREATORS_API_KEY")
        self.base_url = "https://api.scrapecreators.com/v1/instagram/profile"
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key})
        self.min_followers_for_l3 = min_followers_for_l3
        self.skip_contact_crawl = skip_contact_crawl
        self.contact_crawler = ContactPageCrawler()

    def _fetch_profile(self, handle: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}?{urlencode({'handle': handle})}", timeout=30)
        response.raise_for_status()
        return response.json()

    def enrich_candidates(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        enriched_rows: list[dict[str, Any]] = []
        runlog: list[dict[str, Any]] = []
        for candidate in candidates:
            handle = safe_text(candidate.get("creator_handle"))
            if not handle:
                continue
            try:
                payload = self._fetch_profile(handle)
                user = ((payload.get("data") or {}).get("user")) if isinstance((payload.get("data") or {}), dict) else {}
                user = user if isinstance(user, dict) else {}
                bio = safe_text(user.get("biography"))
                followers_count = _to_int(((user.get("edge_followed_by") or {}).get("count")))
                following_count = _to_int(((user.get("edge_follow") or {}).get("count")))
                statuses_count = _to_int(((user.get("edge_owner_to_timeline_media") or {}).get("count")))
                verified = _normalize_bool(user.get("is_verified"))
                external_links = _collect_external_links(user)
                business_email = safe_text(user.get("business_email"))
                business_phone_number = safe_text(user.get("business_phone_number"))
                category_name = safe_text(user.get("category_name") or user.get("overall_category_name"))
                contact_value, contact_note = _extract_email(bio, business_email)
                email_source_url = ""
                contact_page_status = "not_attempted"
                checked_urls = ""
                if not contact_value and external_links and not self.skip_contact_crawl:
                    crawl = self.contact_crawler.find_email(external_links)
                    if crawl.email:
                        contact_value = crawl.email
                        contact_note = "来源: contact page crawl"
                        email_source_url = crawl.email_source_url
                    contact_page_status = crawl.crawl_status
                    checked_urls = crawl.checked_urls_text()
                contact_signals = _contact_signals(bio, external_links, business_email)
                country, country_confidence, primary_language, language_mix = _infer_country_and_language(bio, external_links)
                topic_match_score = _score_topic(candidate, bio)
                profile_match_score = _score_profile(followers_count, bio, external_links, verified)
                activity_score = _score_activity(candidate, statuses_count)
                contactability_score = _score_contactability(contact_value, external_links, contact_signals)
                overall_score = round((topic_match_score * 0.35) + (profile_match_score * 0.25) + (activity_score * 0.2) + (contactability_score * 0.2), 1)
                recommended_action, decision_reason = _recommended_action(
                    followers_count=followers_count,
                    overall_score=overall_score,
                    contact_value=contact_value,
                    min_followers_for_l3=self.min_followers_for_l3,
                )
                profile_l2_eligible = "yes" if followers_count >= self.min_followers_for_l3 else "no"
                profile_l2_skip_reason = "" if profile_l2_eligible == "yes" else f"below_followers_gate_{self.min_followers_for_l3}"
                enriched_rows.append(
                    {
                        **candidate,
                        "bio": bio,
                        "followers_count": followers_count,
                        "following_count": following_count,
                        "statuses_count": statuses_count,
                        "verified": verified,
                        "profile_url": f"https://www.instagram.com/{handle}/",
                        "external_links": external_links,
                        "contact_signals": contact_signals,
                        "contact_value": contact_value,
                        "contact_note": contact_note,
                        "email_source_url": email_source_url,
                        "contact_page_crawl_status": contact_page_status,
                        "contact_page_checked_urls": checked_urls,
                        "enrichment_provider": "scrapecreators.instagram.profile",
                        "enrichment_status": "success",
                        "enrichment_error": "",
                        "topic_match_score": topic_match_score,
                        "profile_match_score": profile_match_score,
                        "activity_score": activity_score,
                        "contactability_score": contactability_score,
                        "overall_score": overall_score,
                        "recommended_action": recommended_action,
                        "decision_reason": decision_reason,
                        "country_inferred": country,
                        "country_confidence": country_confidence,
                        "primary_language": primary_language,
                        "language_mix": language_mix,
                        "business_email": business_email,
                        "business_phone_number": business_phone_number,
                        "category_name": category_name,
                        "bio_links": safe_text(user.get("bio_links")),
                        "external_url_linkshimmed": safe_text(user.get("external_url_linkshimmed")),
                        "profile_l2_eligible": profile_l2_eligible,
                        "profile_l2_skip_reason": profile_l2_skip_reason,
                    }
                )
                runlog.append(
                    {
                        "creator_handle": handle,
                        "status": "success",
                        "followers_count": followers_count,
                        "contact_value": contact_value,
                        "recommended_action": recommended_action,
                    }
                )
            except Exception as exc:
                enriched_rows.append(
                    {
                        **candidate,
                        "bio": "",
                        "followers_count": "",
                        "following_count": "",
                        "statuses_count": "",
                        "verified": "",
                        "profile_url": f"https://www.instagram.com/{handle}/",
                        "external_links": "",
                        "contact_signals": "",
                        "contact_value": "",
                        "contact_note": "",
                        "email_source_url": "",
                        "contact_page_crawl_status": "not_attempted",
                        "contact_page_checked_urls": "",
                        "enrichment_provider": "scrapecreators.instagram.profile",
                        "enrichment_status": "error",
                        "enrichment_error": safe_text(exc),
                        "topic_match_score": 0,
                        "profile_match_score": 0,
                        "activity_score": 0,
                        "contactability_score": 0,
                        "overall_score": 0,
                        "recommended_action": "review",
                        "decision_reason": "L2 拉取失败，需要人工复核",
                        "country_inferred": "",
                        "country_confidence": "",
                        "primary_language": "",
                        "language_mix": "",
                        "business_email": "",
                        "business_phone_number": "",
                        "category_name": "",
                        "bio_links": "",
                        "external_url_linkshimmed": "",
                        "profile_l2_eligible": "review",
                        "profile_l2_skip_reason": "profile_fetch_error",
                    }
                )
                runlog.append(
                    {
                        "creator_handle": handle,
                        "status": "error",
                        "error": safe_text(exc),
                    }
                )
        return enriched_rows, runlog
