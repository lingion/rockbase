from __future__ import annotations

from extractors.youtube_common import enrich_youtube_row


async def enrich_youtube_basic(page, profile_url: str) -> dict[str, str]:
    data = await enrich_youtube_row(page, profile_url, core_only=True)
    data.setdefault("category_tags", "")
    data.setdefault("bio_raw", "")
    data.setdefault("external_links_raw", "")
    data.setdefault("contact_note", "")
    return data
