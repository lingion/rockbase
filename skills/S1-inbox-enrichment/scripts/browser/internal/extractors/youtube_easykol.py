from __future__ import annotations

from extractors.youtube_common import enrich_youtube_row


async def enrich_youtube_easykol(page, profile_url: str) -> dict[str, str]:
    data = await enrich_youtube_row(page, profile_url, core_only=False)
    if data.get("is_404") == "yes":
        data["contact_note"] = "404"
    elif data.get("visible_email"):
        data["contact_note"] = "easykol 抓取"
    else:
        data["contact_note"] = "easykol 无法抓取"
    return data
