---
description: "[Workflow] TikTok KOL Layer1 discovery workflow."
---

# L1-WF_tiktok_kol_discovery_csv

## 双通道定义

### content-first

- 从 keyword search、topic videos、高信号热视频拿内容
- 通过 `author_unique_id` 聚合回 creator
- 当前默认入口：`ScrapeCreators /v1/tiktok/search/keyword`
- hashtag 明显时，补 `ScrapeCreators /v1/tiktok/search/hashtag`

### account-first

- 从 user/profile lookup、seed creator expansion 切入
- 再补热视频作为活跃证据
- 当前可选：
  - `ScrapeCreators /v1/tiktok/search/users`
  - `ScrapeCreators /v3/tiktok/profile/videos`
  - `TikTok-Api` user search 作为交叉验证

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

## TikTok alias

- `creator_handle` -> `author_unique_id`
- `display_name` -> `nickname`

## 当前策略

- 优先做窄版、可解释的 search/trending path
- 先把 collector 实际能拿到的字段尽量全量保留
- 再根据真实返回结果回填和收紧 field matrix
- 需要 cookies / session / proxy 时必须显式写 blocker
- 默认测试时启用 skill-local static proxy，不默认裸跑
- 当前默认 `L1 content-first` 不再押注 `TikTok-Api item search`
- 当前默认 `L1 content-first` 入口为 `ScrapeCreators`
- `TikTok-Api` 保留给 `account-first / user lookup`
