from __future__ import annotations

from extractors.instagram_basic import enrich_instagram_basic


async def enrich_instagram_easykol(page, profile_url: str) -> dict[str, str]:
    data = await enrich_instagram_basic(page, profile_url)
    if data.get("is_404") == "yes":
        data["contact_note"] = "404"
    elif data.get("visible_email"):
        data["contact_note"] = "easykol 抓取"
    else:
        data["contact_note"] = "easykol 无法抓取"
    data.setdefault("avg_views_10", "")
    data.setdefault("top_pinned_views", "")
    return data
