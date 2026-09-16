from __future__ import annotations

from extractors.instagram_common import enrich_instagram_row


async def enrich_instagram_basic(page, profile_url: str) -> dict[str, str]:
    data = await enrich_instagram_row(page, profile_url)
    data.setdefault("bio_raw", "")
    data.setdefault("category_tags", "")
    data.setdefault("external_links_raw", "")
    data.setdefault("language", "")
    data.setdefault("contact_note", "")
    return data
