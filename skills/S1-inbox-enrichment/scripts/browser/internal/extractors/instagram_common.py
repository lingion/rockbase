from __future__ import annotations

import re

from extractors.common import infer_country_from_text


async def enrich_instagram_row(page, profile_url: str) -> dict[str, str]:
    result = {
        "handle": "",
        "author_name": "",
        "followers": "",
        "country": "",
        "visible_email": "",
        "easykol_visible": "no",
        "email_source": "",
        "top_pinned_views": "",
        "avg_views_10": "",
        "is_404": "no",
    }
    await safe_goto(page, normalize_instagram_url(profile_url))
    await page.wait_for_timeout(2500)

    text = await page.evaluate("() => document.body.innerText")
    if is_not_found(text):
        result["is_404"] = "yes"
        return result

    title = await page.title()
    og_title = await get_meta(page, 'meta[property="og:title"]')
    description = await get_meta(page, 'meta[name="description"]')
    result["handle"] = extract_handle(text, profile_url, og_title or title)
    result["author_name"] = extract_name(text, result["handle"], og_title or title)
    result["followers"] = extract_followers(text, description)
    result["country"] = infer_country_from_text(text[:4000], description, og_title or title, result["author_name"])
    return result


def normalize_instagram_url(url: str) -> str:
    url = (url or "").strip()
    url = url.split("?", 1)[0].split("#", 1)[0]
    for token in ["/reels/", "/reel/", "/p/"]:
        if token in url:
            prefix = url.split(token, 1)[0]
            if prefix.count("/") >= 3:
                return prefix
    return url.rstrip("/")


async def safe_goto(page, url: str) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        await page.goto(url, wait_until="commit", timeout=45000)
    await page.wait_for_timeout(1500)


async def get_meta(page, selector: str) -> str:
    locator = page.locator(selector)
    if await locator.count():
        return (await locator.first.get_attribute("content")) or ""
    return ""


def is_not_found(text: str) -> bool:
    hay = (text or "").lower()
    return any(token in hay for token in ["sorry, this page isn't available", "page isn't available", "找不到页面"])


def extract_handle(text: str, url: str, title_like: str = "") -> str:
    if title_like:
        match = re.search(r"\(@([^()]+)\)", title_like)
        if match:
            return normalize_handle("@" + match.group(1))
    for line in split_lines(text):
        if line.startswith("@"):
            return normalize_handle(line)
    match = re.search(r"instagram\.com/([^/?#]+)/?", url or "", re.I)
    if match:
        return normalize_handle("@" + match.group(1))
    return ""


def extract_name(text: str, handle: str, title_like: str = "") -> str:
    if title_like and "(@" in title_like:
        name = title_like.split("(@", 1)[0].strip()
        name = re.sub(r"\s*[•·]\s*Instagram.*$", "", name, flags=re.I)
        if clean_author_name(name, handle):
            return name

    lines = split_lines(text)
    if handle:
        bare = handle.lstrip("@").lower()
        for idx, line in enumerate(lines[:25]):
            if line.strip().lower() in {bare, handle.lower()}:
                if idx > 0:
                    prev = clean_author_name(lines[idx - 1], handle)
                    if prev:
                        return prev
                if idx + 1 < len(lines):
                    nxt = clean_author_name(lines[idx + 1], handle)
                    if nxt:
                        return nxt
    return ""


def clean_author_name(value: str, handle: str = "") -> str:
    value = (value or "").strip()
    if not value:
        return ""
    lower = value.lower()
    bare_handle = handle.lstrip("@").lower() if handle else ""
    blocked = {
        "also from meta",
        "follow",
        "message",
        "see more from",
        "sign up for instagram",
        "log in",
    }
    if lower in blocked:
        return ""
    if bare_handle and lower.lstrip("@") == bare_handle:
        return ""
    if value.startswith("@"):
        return ""
    if "followers" in lower or "following" in lower or "posts" in lower:
        return ""
    return value


def extract_followers(text: str, description: str = "") -> str:
    if description:
        match = re.search(r"(\d[\d,.]*\s*[KMB]?)\s+Followers", description, re.I)
        if match:
            return normalize_views(match.group(1).replace(",", ""))
        value = parse_number_token(description)
        if value:
            return value
    lines = split_lines(text)
    for idx, line in enumerate(lines[:30]):
        lower = line.lower()
        if "followers" in lower or "粉丝" in lower:
            for candidate in [line] + lines[max(0, idx - 1): idx]:
                value = parse_number_token(candidate)
                if value:
                    return value
    return ""


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def parse_number_token(text: str) -> str:
    text = (text or "").strip()
    patterns = [
        r"(\d[\d,.]*\s*[KMB])",
        r"(\d[\d,.]*)\s*万",
        r"(\d[\d,.]*)\s*亿",
        r"(\d[\d,.]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        if "亿" in pattern:
            return normalize_views(str(float(raw) * 100000000))
        if "万" in pattern:
            return normalize_views(str(float(raw) * 10000))
        return normalize_views(raw)
    return ""


def normalize_views(text: str) -> str:
    token = re.sub(r"\s+", "", (text or "").upper())
    if token.endswith(("K", "M", "B")):
        return token
    try:
        value = float(token)
    except Exception:
        return ""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{value / 1_000:.1f}K".replace(".0K", "K")
    return str(int(round(value)))


def normalize_handle(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("@"):
        value = "@" + value.lstrip("@")
    value = re.sub(r"[^@A-Za-z0-9._-]", "", value)
    return value
