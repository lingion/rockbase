from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawTweetRecord:
    provider: str
    query_name: str
    query_text: str
    tweet_id: str
    username: str
    display_name: str
    timestamp: str
    text: str
    comments: int
    likes: int
    retweets: int
    tweet_url: str
    raw: str


@dataclass
class Layer1Candidate:
    username: str
    display_name: str
    matched_queries: str
    tweet_count: int
    max_likes: int
    max_retweets: int
    max_comments: int
    sample_posts: str
    top_tweet_url: str
    source_tweet_ids: str
    provider_source: str


@dataclass
class Layer2EnrichedCandidate:
    username: str
    display_name: str
    bio: str
    location_raw: str
    followers_count: int
    following_count: int
    statuses_count: int
    verified: bool
    blue_verified: bool
    matched_queries: str
    tweet_count: int
    max_likes: int
    max_retweets: int
    sample_posts: str
    top_tweet_url: str
    profile_url: str
    provider_source: str

