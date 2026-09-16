from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import requests

from x_kol_discovery.io_utils import load_simple_env, safe_text, skill_env_path


GLOBAL_ENV = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env"
)
BASE_URL = "https://api.scrapecreators.com/v1"


def load_scrapecreators_env() -> tuple[dict[str, str], str]:
    skill_env_link = skill_env_path()
    candidates = [skill_env_link, GLOBAL_ENV]
    for path in candidates:
        if path.exists():
            return load_simple_env(path), str(path)
    raise FileNotFoundError("Missing ScrapeCreators env source. Expected skill .env symlink or global API env.")


def normalize_links(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[\n|]+", str(value or ""))
    out: list[str] = []
    for item in items:
        text = safe_text(item)
        if not text or text.lower() == "nan":
            continue
        if text not in out:
            out.append(text)
    return out


def merge_links(existing: str, api_links: list[str]) -> str:
    merged = normalize_links(existing)
    for link in api_links:
        if link not in merged:
            merged.append(link)
    return "\n".join(merged)


def normalize_followers(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return re.sub(r"\s+subscribers?$", "", text, flags=re.I).strip()
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= 1_000_000:
            return f"{numeric / 1_000_000:.1f}M".replace(".0M", "M")
        if numeric >= 1_000:
            return f"{numeric / 1_000:.1f}K".replace(".0K", "K")
        return str(int(numeric))
    return ""


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


class ScrapeCreatorsClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL, timeout_seconds: float = 20.0) -> None:
        if api_key is None:
            env, _ = load_scrapecreators_env()
            api_key = env.get("SCRAPECREATORS_API_KEY", "")
        if not api_key:
            raise RuntimeError("SCRAPECREATORS_API_KEY not found.")
        self.api_key = api_key
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

    def credit_balance(self) -> dict[str, Any]:
        return self.get("/credit-balance")

    def get_tiktok_profile(self, handle: str) -> dict[str, Any]:
        return self.get("/tiktok/profile", {"handle": handle})

    def get_instagram_profile(self, handle: str) -> dict[str, Any]:
        return self.get("/instagram/profile", {"handle": handle})

    def get_twitter_profile(self, handle: str) -> dict[str, Any]:
        return self.get("/twitter/profile", {"handle": handle})

    def get_youtube_channel(self, url: str) -> dict[str, Any]:
        return self.get("/youtube/channel", {"url": url})
