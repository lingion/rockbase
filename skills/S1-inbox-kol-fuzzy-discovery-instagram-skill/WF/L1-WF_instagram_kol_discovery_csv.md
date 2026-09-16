---
description: "[Workflow] Instagram KOL Layer1 discovery workflow."
---

# L1-WF_instagram_kol_discovery_csv

## 双通道定义

### content-first

- 默认从 `ScrapeCreators /v2/instagram/reels/search` 切入
- 关键词示例：`accio` / `accio review` / `accio ai`
- 用 `username` 聚合回 creator
- `hot` 在这里定义为 high-signal topic content，不是平台全站 trending

### account-first

- 默认从 `ScrapeCreators /v1/instagram/profile` 切入
- `Instaloader session-backed profile/hashtag` 作为补充线
- 再补高信号内容作为主题证据

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

## 当前实战门槛

- `L1 views gate = 2000`
- 对 `view_count < 2000` 的内容，不进入正式 `L2`

## 当前过程文件位置

- `L1 raw / unified / candidates / runlog`
- 统一放在：
  - `.../Social Agency/workbench/{YYYY-MM-DD}/Instagram/`

## Instagram alias

- `creator_handle` -> `username`
- `display_name` -> `full_name`
