from __future__ import annotations

from extractors.tiktok_common import enrich_tiktok_row


async def enrich_tiktok_basic(page, profile_url: str) -> dict[str, str]:
    data = await enrich_tiktok_row(page, profile_url)
    data.setdefault("bio_raw", "")
    data.setdefault("category_tags", "")
    data.setdefault("external_links_raw", "")
    data.setdefault("contact_note", "")
    return data
