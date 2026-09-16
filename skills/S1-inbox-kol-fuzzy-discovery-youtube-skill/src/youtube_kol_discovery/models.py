from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawVideoRecord:
    provider: str
    discovery_route: str
    query_name: str
    query_text: str
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    url: str
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
