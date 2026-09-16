from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


CANONICAL_ALIASES = {
    "report_time": ["提报时间", "Report Time"],
    "reporter": ["提报人", "Reporter"],
    "platform": ["平台", "Platform"],
    "handle": ["账号ID", "Handle", "Username"],
    "author_name": ["频道/作者名称", "频道作者名称", "频道名称", "平台作者", "Author", "Channel Name"],
    "profile_url": ["账号链接", "主页链接", "Profile URL"],
    "country": ["博主国家", "国家", "Country"],
    "followers": ["粉丝数", "Subscribers", "Follower Count"],
    "top_pinned_views": ["置顶最高单条播放量", "Pinned Top Views", "Top Pinned Views"],
    "avg_views_10": ["近期10条均播", "最近10条均播", "10条均播", "Avg Views 10"],
    "category_tags": ["账号类目标签__平台抓取", "账号类目标签", "Category"],
    "bio_raw": ["账号简介__平台抓取", "账号简介", "Bio", "Description"],
    "contact": ["联系方式", "Email", "Contact"],
    "contact_note": ["联系方式备注", "Contact Note"],
    "external_links_raw": ["外链__平台抓取", "External Links", "External Links Raw"],
    "language": ["语言", "Language"],
    "notes": ["提报备注", "备注", "Notes"],
}


@dataclass
class FieldMap:
    canonical_to_header: dict[str, str]
    header_to_index: dict[str, int]

    def header_for(self, canonical_key: str) -> str | None:
        return self.canonical_to_header.get(canonical_key)

    def index_for(self, canonical_key: str) -> int | None:
        header = self.header_for(canonical_key)
        if header is None:
            return None
        return self.header_to_index.get(header)


def build_field_map(headers: Iterable[str]) -> FieldMap:
    header_list = list(headers)
    normalized = {normalize_header(h): h for h in header_list}
    canonical_to_header: dict[str, str] = {}
    for key, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            hit = normalized.get(normalize_header(alias))
            if hit:
                canonical_to_header[key] = hit
                break
    return FieldMap(
        canonical_to_header=canonical_to_header,
        header_to_index={header: idx for idx, header in enumerate(header_list)},
    )


def normalize_header(value: str) -> str:
    return "".join((value or "").strip().lower().split())
