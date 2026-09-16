---
description: "[Workflow] TikTok KOL Layer2 enrichment workflow."
---

# L2-WF_tiktok_kol_enrichment_csv

## 核心目标

在不丢失 `L1` 发现证据的前提下，把 creator 补成可判断、可外联的对象。

## L1 和 L2 的分工

- `L1` 用内容热度筛人
- `L2` 用账号体量和 profile / contact 资料再筛一轮
- `L3` 才做最终 `keep / review / drop`

因此：

- `L1 gate` 默认看 `view_count / max_views`
- `L2 gate` 默认看 `followers_count`
- `L2` 不重新发明 discovery

## Discovery Master 去重

`L2` 调 ScrapeCreators profile / profile videos 前必须先查 `discovery master`。

介入位置：

1. `L1 candidates`
2. `L1 views gate >= 2000`
3. `check discovery master`
4. 仅对 `new_candidate` 调用 `L2 provider`
5. 将本批进入 L2 的新账号写回 `discovery master`

长期主表位置：

- `docs/tiktok_kol_discovery_master.csv`

为什么这样做：

- 避免同一 creator 反复消耗 profile 深挖 credits
- 避免重复进入 `L3 / S2`
- 保证本批口径接近净新增

默认规则：

- 命中 master 的 creator 视为老人
- 老人不进入本批 L2 provider
- 老人不进入本批 `L3 / S2`
- 若未来要刷新老人，应单独做 refresh workflow

当前执行建议：

- 首轮先跑 `profile enrich`
- 先把 `followers_count / bio / bio regex email / external_links` 拉齐
- 若整批速度过慢，`contact page crawl` 作为后置 augment 单独跑在 `L2 shortlist` 上
- 不必把官网邮箱补扫和首轮 profile enrich 强绑在一起

## 当前默认 L2 输入条件

- `L1 content evidence` 已存在
- `max_views >= 2000`
- 未命中 `docs/tiktok_kol_discovery_master.csv`

## L2 新增字段

- `账号类目标签__平台抓取`
- `bio`
- `followers_count`
- `following_count`
- `statuses_count`
- `verified`
- `profile_url`
- `external_links`
- `contact_signals`
- `contact_value`
- `contact_note`
- `enrichment_provider`
- `enrichment_status`
- `enrichment_error`

## TikTok 重点

- `creator_handle` 默认映射 `author_unique_id`
- `followers_count` 是 L2 gate 主字段
- `bio` 是后续 coldmail personalization 的核心输入
- `账号类目标签__平台抓取` 默认继承自 `content_tags_or_hashtags`；抓得到就填，抓不到留空，不做 LLM 猜测
- `external_links / contact_signals` 只记录明确证据
- `contact_value` 只允许 email
- `contact_note` 只允许 email 来源/获取方式

## 当前默认数据来源

| 字段 | 默认来源 | 所在层 |
| --- | --- | --- |
| `view_count` | `ScrapeCreators /v1/tiktok/search/keyword` 返回的视频结果 | `L1 content` |
| `max_views` | 聚合同一 creator 下命中内容的最高 `view_count` | `L1 creator_summary` |
| `followers_count` | `ScrapeCreators profile` | `L2` |
| `bio` | `ScrapeCreators profile` 的 `signature` / bio 字段 | `L2` |
| `external_links` | `ScrapeCreators profile` 的 bio link / external url | `L2` |
| `contact_signals` | bio 中的 link / contact clue / newsletter clue | `L2` |
| `contact_value` | profile 公开 email 或 bio 正则提取 email | `L2` |
| `contact_note` | email 来源，例如 `profile_public_email` / `bio_regex_email` | `L2` |
| `email_source_url` | 若邮箱来自官网/聚合页补扫，记录来源页面 | `L2 augment` |
| `contact_page_crawl_status` | 官网补扫状态 | `L2 augment` |

## 默认 L2 gate

- `followers_count >= 3000` 才允许进入正式 `L3 shortlist`
- `followers_count` 缺失时先标记为 `review`
- 如果 `L1 max_views` 很强但 `followers_count` 缺失，可保留为 `review`

## 为 coldmail 最重要的字段

TikTok 在 `L2 / L3` 里最值得保留给后续 coldmail 的字段：

- `creator_handle`
- `display_name`
- `bio`
- `followers_count`
- `sample_contents`
- `top_content_url`
- `content_tags_or_hashtags`
- `external_links`
- `contact_value`
- `contact_note`

这些字段对应的用途：

- `bio`: 生成个性化 opening / relevance hook
- `sample_contents`: 生成最近内容角度引用
- `content_tags_or_hashtags`: 生成 topic fit 判断
- `external_links`: 判断商业化成熟度
- `contact_value / contact_note`: 进入 coldmail 的直接入口
