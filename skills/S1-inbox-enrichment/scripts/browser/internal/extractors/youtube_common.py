from __future__ import annotations

import re
from extractors.common import infer_country_from_text, infer_language_from_text


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


async def enrich_youtube_row(page, profile_url: str, core_only: bool = False) -> dict[str, str]:
    result = {
        "handle": "",
        "author_name": "",
        "followers": "",
        "country": "",
        "language": "",
        "category_tags": "",
        "bio_raw": "",
        "top_pinned_views": "",
        "avg_views_10": "",
        "visible_email": "",
        "easykol_visible": "no",
        "email_source": "",
        "is_404": "no",
    }
    base_url = normalize_channel_url(profile_url)
    await safe_goto(page, base_url)
    await page.wait_for_timeout(3500)

    if await _is_not_found_page(page):
        result["is_404"] = "yes"
        return result

    result["handle"] = await _extract_handle(page, base_url)
    result["author_name"] = await _extract_author_name(page)
    result["followers"] = await _extract_followers(page)

    page_text = await _get_page_text(page)
    html = await page.content()
    title = await page.title()
    result["country"] = infer_country_from_text(page_text[:4000], html[:4000], title)
    result["language"] = infer_language_from_text(page_text[:4000], html[:4000], title)
    result["bio_raw"] = await _extract_bio(page)

    if not core_only:
        # Only spend time on panel if we need avg_views or email
        # We'll do it quickly
        panel = await _extract_easykol_panel(page)
        result["avg_views_10"] = panel["avg_views_10"]
        result["easykol_visible"] = "yes" if panel["panel_detected"] or _has_easykol_marker(page_text, html) else "no"
        if panel["email"]:
            result["visible_email"] = panel["email"]
            result["email_source"] = "easykol_panel"
        else:
            email = _pick_best_email(page_text)
            if email:
                result["visible_email"] = email
                result["email_source"] = "page_visible"

        # Only get top views if base_url is likely the home page
        if "/@" in base_url and not any(x in base_url for x in ["/videos", "/shorts", "/live"]):
             top_views = await _extract_top_views(page, base_url)
             if top_views:
                 result["top_pinned_views"] = top_views
    return result





def normalize_channel_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if "/videos" in url:
        return url.split("/videos", 1)[0]
    if "/featured" in url:
        return url.split("/featured", 1)[0]
    if "/about" in url:
        return url.split("/about", 1)[0]
    return url


async def _extract_handle(page, fallback_url: str) -> str:
    header_texts = await _extract_header_texts(page)
    for text in header_texts:
        match = re.search(r"@[\w.-]+", text)
        if match:
            return normalize_handle(match.group(0))

    candidates = [
        "#channel-handle",
        "ytd-channel-name + yt-formatted-string",
        "yt-formatted-string#text",
    ]
    for selector in candidates:
        locator = page.locator(selector)
        count = await locator.count()
        for idx in range(min(count, 4)):
            text = (await locator.nth(idx).inner_text()).strip()
            match = re.search(r"@[\w.-]+", text)
            if match:
                return normalize_handle(match.group(0))
    match = re.search(r"/@([^/?#]+)", fallback_url)
    if match:
        return normalize_handle(f"@{match.group(1)}")
    return ""


async def _extract_author_name(page) -> str:
    header_texts = await _extract_header_texts(page)
    for text in header_texts:
        cleaned = clean_channel_name(text)
        if cleaned and not cleaned.startswith("@"):
            return cleaned

    candidates = [
        "yt-formatted-string.ytd-channel-name",
        "ytd-channel-name #text",
        "meta[itemprop='name']",
    ]
    for selector in candidates:
        locator = page.locator(selector)
        if await locator.count():
            text = (await locator.first.inner_text()).strip()
            if text and not text.startswith("@"):
                return text
    title = await page.title()
    return title.replace(" - YouTube", "").strip()
    
    
async def _extract_bio(page) -> str:
    # Try description selector
    selectors = [
        "yt-description-snippet-renderer #description",
        "#description-container #description",
        "meta[name='description']",
    ]
    for selector in selectors:
        if selector.startswith("meta"):
            node = await page.query_selector(selector)
            if node:
                content = await node.get_attribute("content")
                if content: return content.strip()
        else:
            locator = page.locator(selector)
            if await locator.count():
                return (await locator.first.inner_text()).strip()
    return ""


async def _extract_header_texts(page) -> list[str]:
    dom_texts = await page.evaluate(
        """() => {
            const selectors = [
              '#page-header',
              'ytd-page-header-renderer',
              'ytd-c4-tabbed-header-renderer',
              'ytd-channel-name',
              '#channel-header-container',
            ];
            const lines = [];
            for (const selector of selectors) {
              for (const node of document.querySelectorAll(selector)) {
                const text = (node.innerText || '').trim();
                if (!text) continue;
                for (const line of text.split('\\n')) {
                  const cleaned = line.trim();
                  if (cleaned) lines.push(cleaned);
                }
              }
            }
            return lines;
        }"""
    )
    deduped = []
    seen = set()
    for text in dom_texts:
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    if deduped:
        return deduped

    selectors = [
        "#page-header",
        "ytd-page-header-renderer",
        "ytd-c4-tabbed-header-renderer",
        "ytd-channel-name",
    ]
    texts: list[str] = list(dom_texts)
    for selector in selectors:
        locator = page.locator(selector)
        if not await locator.count():
            continue
        for idx in range(min(await locator.count(), 2)):
            try:
                raw = (await locator.nth(idx).inner_text()).strip()
            except Exception:
                continue
            if raw:
                texts.extend([line.strip() for line in raw.splitlines() if line.strip()])
    deduped = []
    seen = set()
    for text in texts:
        if text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def clean_channel_name(value: str) -> str:
    value = (value or "").strip()
    if not value or value.startswith("@"):
        return ""
    if "订阅者" in value or "subscribers" in value.lower():
        return ""
    if value.lower() in {"live", "live now", "premiere"}:
        return ""
    if value in {"直播中", "直播", "首播中", "即将开始"}:
        return ""
    if value in {"订阅", "加入", "社区"}:
        return ""
    if "个视频" in value or "videos" in value.lower():
        return ""
    if value.startswith("http") or ".com" in value.lower():
        return ""
    if len(value) > 80:
        return ""
    return value


async def _extract_followers(page) -> str:
    texts = []
    for selector in ["#subscriber-count", "yt-formatted-string#subscriber-count", "body"]:
        locator = page.locator(selector)
        if await locator.count():
            try:
                texts.append((await locator.first.inner_text()).strip())
            except Exception:
                continue
    for text in texts:
        normalized = normalize_followers(text)
        if normalized:
            return normalized
    return ""


async def _extract_top_views(page, base_url: str) -> str:
    await safe_goto(page, base_url)
    await page.wait_for_timeout(3500)
    text = await _get_page_text(page)
    # 只在首页可见区域里找“置顶/特色视频”附近的播放量；拿不到就留空，不用 recent videos 顶替。
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines[:80]):
        lower = line.lower()
        if any(token in lower for token in ["featured", "for business inquiries", "subscribe", "@"]):
            window = " ".join(lines[idx:idx + 8])
            matches = re.findall(r"(\d[\d,.]*\s*[KMB]?)\s+views", window, re.I)
            if matches:
                normalized = normalize_views(matches[0])
                if normalized:
                    return normalized
    return ""


def normalize_followers(text: str) -> str:
    text = text.replace("\n", " ")
    patterns = [
        r"(\d[\d,.]*\s*[KMB]?)\s+subscribers",
        r"(\d[\d,.]*)\s*万(?:位)?订阅者",
        r"(\d[\d,.]*)\s*亿(?:位)?订阅者",
        r"(\d[\d,.]*)\s*位订阅者",
        r"(\d[\d,.]*)\s*万\s*subscribers",
        r"(\d[\d,.]*)\s*亿\s*subscribers",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        raw = match.group(1)
        if "亿" in pattern:
            return normalize_views(str(float(raw.replace(",", "")) * 100000000))
        if "万" in pattern:
            return normalize_views(str(float(raw.replace(",", "")) * 10000))
        return normalize_views(raw)
    return ""


def normalize_views(text: str) -> str:
    text = re.sub(r"\s+", "", text.upper().replace(",", ""))
    if text.endswith(("K", "M", "B")):
        return text
    if not text or not text.replace(".", "").isdigit():
        return ""
    value = float(text)
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


def _pick_best_email(text: str) -> str:
    blocked_domains = ("youtube.com", "ytimg.com", "google.com")
    for email in EMAIL_PATTERN.findall(text or ""):
        if any(email.lower().endswith(domain) for domain in blocked_domains):
            continue
        return email
    return ""


def _has_easykol_marker(page_text: str, html: str) -> bool:
    haystack = f"{page_text}\n{html}".lower()
    markers = [
        "easykol",
        "easy kol",
        "daily new followers",
        "engagement rate",
        "kol rank",
    ]
    return any(marker in haystack for marker in markers)


async def _is_not_found_page(page) -> bool:
    title = (await page.title()).lower()
    text = (await _get_page_text(page)).lower()
    markers = [
        "this page isn't available",
        "this channel does not exist",
        "video unavailable",
        "404",
        "找不到这个页面",
        "這個頁面無法使用",
        "not available",
    ]
    haystack = f"{title}\n{text}"
    return any(marker in haystack for marker in markers)


async def safe_goto(page, url: str) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        await page.goto(url, wait_until="commit", timeout=45000)
    await page.wait_for_timeout(2000)


async def _get_page_text(page) -> str:
    try:
        body = page.locator("body")
        if await body.count():
            return (await body.first.inner_text(timeout=5000)).strip()
    except Exception:
        pass
    try:
        return await page.evaluate(
            """() => {
                const body = document.body;
                if (!body) return '';
                return (body.innerText || body.textContent || '').trim();
            }"""
        )
    except Exception:
        return ""


async def _extract_easykol_panel(page) -> dict[str, str | bool]:
    await _configure_easykol_panel(page)
    # EasyKOL 面板通常会在页面稳定后再异步注入数据，10s 对当前会话更稳。
    await page.wait_for_timeout(10000)
    snapshot_text = await _get_page_text(page)
    snapshot_html = await page.content()
    snapshot_email = _pick_best_email(f"{snapshot_text}\n{snapshot_html}")
    snapshot_avg_views = _parse_avg_views(f"{snapshot_text}\n{snapshot_html}")
    snapshot_panel_detected = _has_easykol_marker(snapshot_text, snapshot_html)
    if snapshot_email or snapshot_avg_views:
        return {
            "panel_detected": snapshot_panel_detected,
            "email": snapshot_email,
            "avg_views_10": snapshot_avg_views,
        }

    aggregate = []
    for _ in range(8):
        batch = await page.evaluate(
            """() => {
                const collectNodes = (root) => {
                    const items = [];
                    const seen = new Set();
                    const visit = (nodeRoot) => {
                        if (!nodeRoot) return;
                        const nodes = nodeRoot.querySelectorAll ? Array.from(nodeRoot.querySelectorAll('*')) : [];
                        for (const el of nodes) {
                            if (seen.has(el)) continue;
                            seen.add(el);
                            items.push(el);
                            if (el.shadowRoot) {
                                visit(el.shadowRoot);
                            }
                        }
                    };
                    visit(root);
                    return items;
                };
                const nodes = collectNodes(document);
                const emailRe = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/i;
                return nodes.map(el => {
                    const text = (el.innerText || '').trim();
                    const value = ('value' in el && typeof el.value === 'string') ? el.value.trim() : '';
                    const placeholder = typeof el.getAttribute === 'function' ? (el.getAttribute('placeholder') || '').trim() : '';
                    const aria = typeof el.getAttribute === 'function' ? (el.getAttribute('aria-label') || '').trim() : '';
                    const title = typeof el.getAttribute === 'function' ? (el.getAttribute('title') || '').trim() : '';
                    const name = typeof el.getAttribute === 'function' ? (el.getAttribute('name') || '').trim() : '';
                    const type = typeof el.getAttribute === 'function' ? (el.getAttribute('type') || '').trim() : '';
                    const cls = typeof el.className === 'string' ? el.className : '';
                    return { text, value, placeholder, aria, title, name, type, cls, id: el.id || '', tag: el.tagName };
                }).filter(x => {
                    const blob = `${x.id} ${x.cls} ${x.text} ${x.value} ${x.placeholder} ${x.aria} ${x.title} ${x.name} ${x.type}`;
                    return /最近10条|近期10条|近10条|均播|平均播放|CPM|发送邮件|邮箱|无效计数接口显示|daily new followers|estimated|mail|email/i.test(blob) || emailRe.test(blob);
                }).slice(0, 300);
            }"""
        )
        aggregate.extend(batch)
        parsed = _parse_easykol_snapshot(batch)
        if parsed["email"] or parsed["avg_views_10"]:
            return parsed
        await page.wait_for_timeout(1000)
    return _parse_easykol_snapshot(aggregate)


async def _configure_easykol_panel(page) -> None:
    await _pick_dropdown_option(page, ["最近10条", "近期10条", "近10条"], ["最近10条", "近期10条", "最近 10 条"])
    await _pick_dropdown_option(page, ["中位数", "平均数"], ["平均数"])


async def _pick_dropdown_option(page, trigger_candidates: list[str], option_candidates: list[str]) -> None:
    for label in trigger_candidates:
        locator = page.locator(f"text={label}")
        if not await locator.count():
            continue
        try:
            await locator.first.click(timeout=2500)
            await page.wait_for_timeout(800)
            for option_text in option_candidates:
                option = page.locator(f"text={option_text}")
                if await option.count():
                    await option.first.click(timeout=2500)
                    await page.wait_for_timeout(2500)
                    return
        except Exception:
            continue


def _parse_easykol_snapshot(items: list[dict]) -> dict[str, str | bool]:
    def _join_item(item: dict) -> str:
        parts = [
            item.get("text", ""),
            item.get("value", ""),
            item.get("placeholder", ""),
            item.get("aria", ""),
            item.get("title", ""),
        ]
        return " ".join(part for part in parts if part)

    joined = "\n".join(_join_item(item) for item in items if _join_item(item))
    panel_detected = any(
        token in joined.lower()
        for token in ["最近10条", "近期10条", "发送邮件", "无效计数接口显示", "daily new followers", "estimated"]
    )
    return {
        "panel_detected": panel_detected,
        "email": _pick_best_email(joined),
        "avg_views_10": _parse_avg_views(joined),
    }


def _parse_avg_views(text: str) -> str:
    patterns = [
        r"(?:最近10条|近期10条|近10条)[^\n]{0,20}?(\d[\d,.]*\s*[KMB]?)",
        r"(?:平均播放|均播|avg(?:\.| )?views?)[^\n]{0,20}?(\d[\d,.]*\s*[KMB]?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", re.I)
        if match:
            normalized = normalize_views(match.group(1))
            if normalized:
                return normalized
    return ""
