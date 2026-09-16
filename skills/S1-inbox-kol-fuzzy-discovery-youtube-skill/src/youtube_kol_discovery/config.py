from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchQuery:
    name: str
    query: str
    limit: int = 20


@dataclass
class Layer1RunConfig:
    task_name: str = "youtube_kol_discovery"
    platform: str = "youtube"
    topic_query: str = "AI agents"
    l1_mode: str = "dual_channel"
    search_first: bool = True
    enable_discover_supplement: bool = False
    shortlist_target: int = 50
    min_content_views_for_l2: int = 1000
    language: str = "en"
    country: str = "US"
    run_date: str = "2026-04-10"
    search_limit_per_query: int = 20
    discover_limit: int = 20
