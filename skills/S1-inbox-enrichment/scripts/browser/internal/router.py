from __future__ import annotations

from urllib.parse import urlparse


PLATFORM_ALIASES = {
    "youtube": "youtube",
    "you tube": "youtube",
    "yt": "youtube",
    "tiktok": "tiktok",
    "tik tok": "tiktok",
    "instagram": "instagram",
    "ig": "instagram",
    "x": "x",
    "twitter": "x",
}


def normalize_platform(value: str) -> str:
    token = " ".join((value or "").strip().lower().split())
    return PLATFORM_ALIASES.get(token, token)


def infer_platform(platform_value: str, profile_url: str) -> str:
    normalized = normalize_platform(platform_value)
    if normalized in {"youtube", "tiktok", "instagram", "x"}:
        return normalized

    parsed = urlparse((profile_url or "").strip())
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    haystack = f"{host}{path}"
    if "youtube.com" in haystack or "youtu.be" in haystack:
        return "youtube"
    if "tiktok.com" in haystack:
        return "tiktok"
    if "instagram.com" in haystack:
        return "instagram"
    if "x.com" in haystack or "twitter.com" in haystack:
        return "x"
    return "unknown"
