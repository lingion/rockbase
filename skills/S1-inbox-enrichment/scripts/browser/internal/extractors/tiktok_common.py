from __future__ import annotations

import re

from extractors.common import infer_country_from_text, infer_language_from_text


async def enrich_tiktok_row(page, profile_url: str) -> dict[str, str]:
    result = {
        "handle": "",
        "author_name": "",
        "followers": "",
        "country": "",
        "language": "",
        "visible_email": "",
        "easykol_visible": "no",
        "email_source": "",
        "top_pinned_views": "",
        "avg_views_10": "",
        "is_404": "no",
    }
    if "tiktok.com/" not in (profile_url or "").lower():
        return result
    await safe_goto(page, normalize_tiktok_url(profile_url))
    await page.wait_for_timeout(2500)

    text = await page.evaluate("() => document.body.innerText")
    if is_not_found(text):
        result["is_404"] = "yes"
        return result

    header = await extract_header(page)
    header_text = "\n".join(header.get("header_lines", []))
    result["handle"] = normalize_handle(header["handle"]) or extract_handle(text, profile_url)
    result["author_name"] = clean_author_name(header["author_name"], result["handle"]) or extract_name(f"{header_text}\n{text}", result["handle"])
    result["followers"] = extract_followers_from_header(header["stats"]) or extract_followers(text)
    result["country"] = infer_country_from_text(text[:4000], result["author_name"], result["handle"])
    result["language"] = infer_language_from_text(text[:4000], result["author_name"], result["handle"])
    return result


def normalize_tiktok_url(url: str) -> str:
    url = (url or "").strip()
    if "/video/" in url:
        return url.split("/video/", 1)[0]
    return url


async def safe_goto(page, url: str) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        await page.goto(url, wait_until="commit", timeout=45000)
    await page.wait_for_timeout(1500)


async def extract_header(page) -> dict[str, str]:
    return await page.evaluate(
        """() => {
            const pick = (selectors) => {
              for (const selector of selectors) {
                const node = document.querySelector(selector);
                const text = (node?.innerText || '').trim();
                if (text) return text;
              }
              return '';
            };
            const collect = (selectors) => {
              const out = [];
              for (const selector of selectors) {
                for (const node of document.querySelectorAll(selector)) {
                  const text = (node?.innerText || '').trim();
                  if (!text) continue;
                  for (const line of text.split('\\n')) {
                    const cleaned = line.trim();
                    if (cleaned) out.push(cleaned);
                  }
                }
              }
              return out;
            };
            return {
              handle: pick(['h1', '[data-e2e=\"user-title\"]', '[data-e2e=\"browse-username\"]']),
              author_name: pick(['h2', '[data-e2e=\"user-subtitle\"]', '[data-e2e=\"user-bio\"] + h2']),
              stats: pick(['h3', '[data-e2e=\"followers-count\"]', '[data-e2e=\"user-stats\"]']),
              header_lines: collect(['h1', 'h2', '[data-e2e=\"user-title\"]', '[data-e2e=\"user-subtitle\"]', '[data-e2e=\"user-bio\"]', '[data-e2e=\"user-page\"]']),
            };
        }"""
    )


def is_not_found(text: str) -> bool:
    hay = (text or "").lower()
    return any(token in hay for token in ["couldn't find this account", "account not found", "找不到此帐户", "找不到此账号"])


def extract_handle(text: str, url: str) -> str:
    for line in split_lines(text):
        if line.startswith("@"):
            return normalize_handle(line)
    match = re.search(r"tiktok\.com/@([^/?#]+)", url or "", re.I)
    if match:
        return normalize_handle("@" + match.group(1))
    return ""


def extract_name(text: str, handle: str) -> str:
    header_hint = extract_name_from_inline_header(text, handle)
    if header_hint:
        return header_hint
    lines = split_lines(text)
    if handle:
        bare = handle.lstrip("@").lower()
        for idx, line in enumerate(lines[:20]):
            normalized = line.strip().lower().lstrip("@")
            if normalized == bare:
                for candidate in lines[idx + 1: idx + 5]:
                    cleaned = clean_author_name(candidate, handle)
                    if cleaned:
                        return cleaned
    for idx, line in enumerate(lines[:20]):
        if line.startswith("@"):
            for candidate in lines[idx + 1: idx + 5]:
                cleaned = clean_author_name(candidate, handle)
                if cleaned:
                    return cleaned
    return ""


def extract_name_from_inline_header(text: str, handle: str) -> str:
    lines = split_lines(text)
    if not handle:
        return ""
    bare = handle.lstrip("@").lower()
    for line in lines[:12]:
        lower = line.lower()
        if bare not in lower:
            continue
        match = re.match(rf"@?{re.escape(bare)}\s+(.+)$", line, flags=re.I)
        if match:
            cleaned = clean_author_name(match.group(1), handle)
            if cleaned:
                return cleaned
        tokens = [token.strip() for token in re.split(r"\s{2,}", line) if token.strip()]
        if len(tokens) >= 2:
            for token in tokens[1:]:
                cleaned = clean_author_name(token, handle)
                if cleaned:
                    return cleaned
        stripped = re.sub(rf"^@?{re.escape(bare)}\b", "", line, flags=re.I).strip(" -|:")
        cleaned = clean_author_name(stripped, handle)
        if cleaned:
            return cleaned
    return ""


def clean_author_name(value: str, handle: str = "") -> str:
    value = (value or "").strip()
    if not value:
        return ""
    lower = value.lower()
    bare_handle = handle.lstrip("@").lower() if handle else ""
    blocked = {
        "为你推荐",
        "推薦",
        "following",
        "followers",
        "likes",
        "message",
        "follow",
        "share",
        "tiktok",
        "videos",
        "reposts",
        "liked",
        "playlists",
        "something went wrong",
        "no bio yet.",
        "business inquiries",
        "business inquires",
    }
    if lower in blocked:
        return ""
    if bare_handle and lower.lstrip("@") == bare_handle:
        # Allow stylized display names like `VortexNextGen` for handle `@vortexnextgen`.
        if value == bare_handle or value == handle or value.startswith("@"):
            return ""
    if any(token in lower for token in ["followers", "likes", "following"]):
        return ""
    if value.startswith("@"):
        return ""
    if "@" in value or re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.I):
        return ""
    if "promo" in lower or "contact" in lower:
        return ""
    if "telegram" in lower or "follow my" in lower:
        return ""
    if lower.startswith("business "):
        return ""
    if "lets do some work" in lower or "let's do some work" in lower:
        return ""
    if re.fullmatch(r"[\d\s.,KMBkmb]+", value):
        return ""
    return value


def extract_followers_from_header(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"(\d[\d,.]*\s*[KMB]?)\s+Followers",
        r"(\d[\d,.]*)\s*万粉丝",
        r"(\d[\d,.]*)\s*亿粉丝",
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


def extract_followers(text: str) -> str:
    lines = split_lines(text)
    for idx, line in enumerate(lines[:40]):
        lower = line.lower()
        if "followers" in lower or "粉丝" in lower:
            for candidate in [line] + lines[max(0, idx - 1): idx]:
                value = parse_number_token(candidate)
                if value:
                    return value
    for line in lines[:15]:
        value = parse_number_token(line)
        if value and any(token in text.lower() for token in ["followers", "粉丝"]):
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
