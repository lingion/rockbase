from __future__ import annotations

from typing import Awaitable, Callable, Dict

from extractors.instagram_basic import enrich_instagram_basic
from extractors.instagram_easykol import enrich_instagram_easykol
from extractors.tiktok_basic import enrich_tiktok_basic
from extractors.tiktok_easykol import enrich_tiktok_easykol
from extractors.youtube_basic import enrich_youtube_basic
from extractors.youtube_easykol import enrich_youtube_easykol


Extractor = Callable[..., Awaitable[dict[str, str]]]


BASIC_REGISTRY: Dict[str, Extractor] = {
    "youtube": enrich_youtube_basic,
    "tiktok": enrich_tiktok_basic,
    "instagram": enrich_instagram_basic,
}

DEEP_REGISTRY: Dict[str, Extractor] = {
    "youtube": enrich_youtube_easykol,
    "tiktok": enrich_tiktok_easykol,
    "instagram": enrich_instagram_easykol,
}

REGISTRY: Dict[str, Extractor] = BASIC_REGISTRY
