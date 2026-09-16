from __future__ import annotations

import re
from typing import Any

import requests

from youtube_kol_discovery.io_utils import get_env_value, safe_text


BASE_URL = "https://api.scrapecreators.com/v1"


def normalize_links(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[\n|,]+", str(value or ""))
    out: list[str] = []
    for item in items:
        text = safe_text(item)
        if not text or text.lower() in {"nan", "none"}:
            continue
        if text not in out:
            out.append(text)
    return out


def merge_links(*values: Any) -> str:
    merged: list[str] = []
    for value in values:
        for link in normalize_links(value):
            if link not in merged:
                merged.append(link)
    return " | ".join(merged)


def extract_email(text_or_payload: Any) -> tuple[str, str]:
    if isinstance(text_or_payload, dict):
        email = safe_text(text_or_payload.get("email"))
        if email:
            return email, "ScrapeCreators API email"
        source_text = safe_text(text_or_payload.get("description"))
    else:
        source_text = safe_text(text_or_payload)
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", source_text, re.I)
    if match:
        return match.group(0), "ScrapeCreators description regex"
    return "", ""


def contact_links_from_payload(payload: dict[str, Any]) -> str:
    links = [
        payload.get("links"),
        payload.get("courses"),
        payload.get("newsletter"),
        payload.get("twitter"),
        payload.get("instagram"),
        payload.get("tiktok"),
        payload.get("spotify"),
    ]
    return merge_links(*links)


class ScrapeCreatorsClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key or get_env_value("SCRAPECREATORS_API_KEY")
        if not self.api_key:
            raise RuntimeError("SCRAPECREATORS_API_KEY not found.")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.headers = {"x-api-key": self.api_key}

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.get(url, headers=self.headers, params=params or {}, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected ScrapeCreators payload type from {url}")
        return payload

    def get_youtube_channel(self, url: str) -> dict[str, Any]:
        return self.get("/youtube/channel", {"url": url})
