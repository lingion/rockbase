from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchQuery:
    name: str
    query: str
    limit: int = 90


@dataclass(frozen=True)
class ScweetCookieProfile:
    name: str
    auth_token: str
    ct0: str = ""
    env_path: str = ""


@dataclass
class Layer1RunConfig:
    task_name: str = "openclaw_recent_hot_kol_en"
    topic_query: str = "OpenClaw AI agents automation developer tools"
    layer1_provider: str = "scweet"
    since: str = "2026-03-01"
    until: str = "2026-03-31"
    shortlist_target: int = 100
    min_followers_for_keep: int = 1000
    layer3_min_followers: int = 1000
    layer2_min_max_views: int = 5000
    layer2_provider: str = "scrapecreators_twitter_profile"
    layer2_enrichment_chunk_size: int = 30
    discovery_master_enabled: bool = True
    discovery_master_refresh_days: int = 7
    query_registry_enabled: bool = True
    user_info_batch_size: int = 20
    user_info_retry_single_on_empty_batch: bool = True
    user_info_batch_pause_seconds: float = 0.0
    language: str = "en"
    run_date: str = "2026-03-31"
