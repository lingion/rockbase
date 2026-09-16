from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from tiktok_kol_discovery.io_utils import safe_text


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
MAILTO_RE = re.compile(r"mailto:([^\"'?#<>\s]+)", re.I)
BLOCKED_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "domain.com", "email.com"}
SKIP_HOST_PARTS = {
    "tiktok.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "facebook.com",
    "linkedin.com",
    "github.com",
}
LINK_PAGE_HOST_PARTS = {"linktr.ee", "beacons.ai", "bio.link", "lnk.bio", "taplink.cc", "solo.to", "msha.ke"}
CONTACT_PATHS = ("/contact", "/contact-us", "/about", "/about-us")


@dataclass
class ContactCrawlResult:
    email: str = ""
    email_source_url: str = ""
    crawl_status: str = "not_attempted"
    checked_urls: list[str] | None = None

    def checked_urls_text(self) -> str:
        return " | ".join(self.checked_urls or [])


def normalize_links(links_value: Any) -> list[str]:
    if isinstance(links_value, list):
        values = links_value
    else:
        values = str(links_value or "").split("|")
    out: list[str] = []
    for raw_value in values:
        value = safe_text(raw_value).strip("<>()[]{}\"'")
        if not value:
            continue
        if value not in out:
            out.append(value)
    return out


def extract_emails_from_text(text: str) -> list[str]:
    decoded = html.unescape(safe_text(text))
    candidates = [match.group(1) for match in MAILTO_RE.finditer(decoded)]
    candidates.extend(match.group(0) for match in EMAIL_RE.finditer(decoded))
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        email_value = candidate.strip().strip(".,;:()[]{}<>")
        lowered = email_value.lower()
        if lowered in seen or not _is_plausible_email(email_value):
            continue
        seen.add(lowered)
        out.append(email_value)
    return out


def candidate_urls_from_links(links_value: Any, *, max_base_links: int = 3) -> list[str]:
    bases: list[str] = []
    for raw_link in normalize_links(links_value):
        url = _normalize_url(raw_link)
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        if _is_skippable_host(host) and not _is_link_page_host(host):
            continue
        if url not in bases:
            bases.append(url)
        if len(bases) >= max_base_links:
            break
    out: list[str] = []
    for url in bases:
        _append_unique(out, url)
        host = urlparse(url).netloc.lower()
        if _is_link_page_host(host):
            continue
        for path in CONTACT_PATHS:
            _append_unique(out, urljoin(url, path))
    return out


class ContactPageCrawler:
    def __init__(self, timeout_seconds: float = 2.5, max_urls_per_creator: int = 3) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                )
            }
        )
        self.timeout_seconds = timeout_seconds
        self.max_urls_per_creator = max_urls_per_creator

    def find_email(self, links_value: Any) -> ContactCrawlResult:
        urls = candidate_urls_from_links(links_value)
        if not urls:
            return ContactCrawlResult(crawl_status="no_crawlable_links", checked_urls=[])
        checked: list[str] = []
        last_error = ""
        for url in urls[: self.max_urls_per_creator]:
            try:
                response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
                checked.append(response.url)
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400:
                    last_error = f"http_{response.status_code}"
                    continue
                if "text/html" not in content_type and "text/plain" not in content_type and not content_type.startswith("text/"):
                    last_error = "non_text_content"
                    continue
                emails = extract_emails_from_text(response.text[:1_000_000])
                if emails:
                    return ContactCrawlResult(
                        email=emails[0],
                        email_source_url=response.url,
                        crawl_status="email_found",
                        checked_urls=checked,
                    )
            except requests.RequestException as exc:
                last_error = f"request_error:{safe_text(exc)[:120]}"
        status = "email_not_found"
        if last_error:
            status = f"{status}:{last_error}"
        return ContactCrawlResult(crawl_status=status, checked_urls=checked)


def _normalize_url(value: str) -> str:
    text = safe_text(value).strip("<>()[]{}\"'")
    if not text or text.startswith("mailto:"):
        return ""
    if text.startswith("//"):
        text = f"https:{text}"
    if not text.startswith(("http://", "https://")):
        if "." not in text or " " in text:
            return ""
        text = f"https://{text}"
    parsed = urlparse(text)
    if not parsed.netloc:
        return ""
    return text


def _is_plausible_email(email_value: str) -> bool:
    if not EMAIL_RE.fullmatch(email_value):
        return False
    lowered = email_value.lower()
    domain = lowered.rsplit("@", 1)[-1]
    if domain in BLOCKED_EMAIL_DOMAINS:
        return False
    if lowered.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    return True


def _is_skippable_host(host: str) -> bool:
    return any(part == host or host.endswith(f".{part}") for part in SKIP_HOST_PARTS)


def _is_link_page_host(host: str) -> bool:
    return any(part == host or host.endswith(f".{part}") for part in LINK_PAGE_HOST_PARTS)


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
