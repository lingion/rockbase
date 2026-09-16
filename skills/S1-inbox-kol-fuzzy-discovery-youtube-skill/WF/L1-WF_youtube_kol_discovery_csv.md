---
description: "[Workflow] YouTube KOL Layer1 discovery workflow."
---

# L1-WF_youtube_kol_discovery_csv

## 核心目标

把 `领域 query -> 大量热视频 -> creator 聚合` 转成可继续补数的 `creator-level` 候选表。

这个 skill 的重点不是“平台 discover 榜”，而是“search 驱动的热内容挖 KOL”。

所以 `L1` 默认只输出一张统一表：

- `youtube_kol_L1_unified_*.csv`

其中：

- `row_type = content` 表示内容行
- `row_type = creator_summary` 表示 creator 聚合摘要行

这样用户只看一张表，但仍保留 content 和 creator 两层信息。

字段原则：

- 表头前部放 `L1 -> L2` 升级所需的必备字段
- 表头后部尽量保留 YouTube provider 的灵活字段
- 不要求一开始把所有 provider 原始字段都强行改成统一名字

## 双通道定义

### content-first

- 从多组 `yt-dlp search` query 拿视频级结果
- 用 `channel_id / channel_title` 聚合回创作者
- 保留热视频证据、标签、观看量和命中 query
- `mostPopular` 只作为补充，不是默认主引擎

### account-first

- 从频道关键词、种子频道、相关频道切入
- 再补最近热视频作为活跃与主题证据

## L1 最低准入字段

- `platform`
- `creator_handle`
- `display_name`
- `matched_queries`
- `matched_content_count`
- `max_views`
- `max_likes`
- `max_comments`
- `sample_contents`
- `top_content_url`
- `source_content_ids`
- `provider_source`
- `discovery_route`
- `content_tags_or_hashtags`

## content-level 必备字段

- `content_id`
- `content_title`
- `theme_text`
- `matched_query_name`
- `matched_query_text`
- `creator_handle`
- `display_name`
- `view_count`
- `content_url`

## 默认流量 gate

- YouTube 当前默认 `view_count >= 1000` 才进入 `L2`
- 低于 `1000` 的内容保留在 `L1 content rows`，但不进入 `L2`

## YouTube alias

- `creator_handle` -> `channel_id`
- `display_name` -> `channel_title`

## 推荐 provider 顺序

1. `youtube.yt_dlp_search`
2. `youtube.channel_lookup_from_search`
3. `youtube.api_most_popular` as supplement only

## 当前 L1 完成判定

- 可以稳定输出 creator-level CSV
- 同一个频道不会重复多行出现
- 能看出每个创作者是因哪几条热视频或查询被发现
