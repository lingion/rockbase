---
description: "[Field Matrix] TikTok KOL CSV 字段继承表 | 采用必备字段 + 灵活字段模型。"
---

# Lx-Field-Matrix_tiktok_kol_csv

> 用途：定义 TikTok KOL pipeline 的字段演进。包含 `L1 / L2 / L3 / S2`。  
> 原则采用：
>
> - `必备字段`：跨平台稳定契约
> - `灵活字段`：TikTok provider 原生字段，尽量保留

## 一、共享主干字段

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `platform` | 输出 | 继承 | 继承 | 固定为 `tiktok` |
| `creator_handle` | 输出 | 继承 | 继承 | 跨平台主键，TikTok 默认映射到 `author_unique_id` |
| `display_name` | 输出 | 继承/更新 | 继承 | TikTok 默认映射到 `nickname` |
| `matched_queries` | 输出 | 继承 | 继承 | 发现证据 |
| `matched_content_count` | 输出 | 继承 | 继承 | 命中的内容数 |
| `sample_contents` | 输出 | 继承 | 继承 | 样例内容摘要 |
| `top_content_url` | 输出 | 继承 | 继承 | 最强信号内容链接 |
| `source_content_ids` | 输出 | 继承 | 继承 | 证据链 |
| `provider_source` | 输出 | 继承 | 继承 | 当前 provider |
| `discovery_route` | 输出 | 继承 | 继承 | `content_first / account_first` |

## 二、L1 必备字段

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `content_title` | 新增 | 继承 | 可保留 | TikTok 标题或 caption |
| `theme_text` | 新增 | 继承 | 可保留 | 用于关键词匹配的正文/标题文本 |
| `content_url` | 新增 | 继承 | 可保留 | 视频链接 |
| `content_tags_or_hashtags` | 新增 | 继承 | 继承 | hashtags / topic words |
| `账号类目标签__平台抓取` |  | 新增 | 继承 | 默认等于 `content_tags_or_hashtags`；ScrapeCreators 能提取则填，拿不到则留空 |
| `view_count` | 新增 | 继承 | 可保留 | 单条内容流量门槛 |
| `like_count` | 新增 | 继承 | 可保留 | 单条内容互动 |
| `comment_count` | 新增 | 继承 | 可保留 | 单条内容互动 |
| `max_views` | 新增 | 继承 | 继承 | 创作者命中内容最高播放 |
| `max_likes` | 新增 | 继承 | 继承 | 创作者命中内容最高点赞 |
| `max_comments` | 新增 | 继承 | 继承 | 创作者命中内容最高评论 |
| `l2_eligible` | 新增 | 继承 | 可保留 | 是否进入 L2 |
| `l2_skip_reason` | 新增 | 继承 | 可保留 | 跳过原因 |

## 三、L2 必备字段

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `bio` |  | 新增 | 继承 | 标准化 profile 简介 |
| `followers_count` |  | 新增 | 继承 | 粉丝数 |
| `following_count` |  | 新增 | 继承 | 关注数 |
| `statuses_count` |  | 新增 | 继承 | 视频总数或作品数 |
| `verified` |  | 新增 | 继承 | 认证状态 |
| `profile_url` |  | 新增 | 继承 | 主页链接 |
| `external_links` |  | 可新增 | 继承 | Bio 外链 |
| `contact_signals` |  | 可新增 | 继承 | 邮箱、Linktree、品牌联系入口 |
| `contact_value` |  | 新增 | 继承 | 仅允许 email |
| `contact_note` |  | 新增 | 继承 | email 来源说明 |
| `email_source_url` |  | 可新增 | 继承 | 若来自外链补扫，记录来源页 |
| `contact_page_crawl_status` |  | 可新增 | 继承 | 外链邮箱补扫状态 |
| `contact_page_checked_urls` |  | 可新增 | 继承 | 实际检查过的 URL 列表 |
| `enrichment_provider` |  | 新增 | 继承 | 补全来源 |
| `enrichment_status` |  | 可新增 | 继承 | 补全状态 |
| `enrichment_error` |  | 可新增 | 继承 | 错误信息 |

## 四、L3 必备字段

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `country_inferred` |  |  | 新增 | 推断国家 |
| `country_confidence` |  |  | 新增 | 国家置信度 |
| `primary_language` |  |  | 新增 | 主语言 |
| `language_mix` |  |  | 新增 | 语言混合 |
| `topic_match_score` |  | 可新增 | 正式输出 | 主题匹配分 |
| `profile_match_score` |  | 可新增 | 正式输出 | profile 质量分 |
| `activity_score` |  | 可新增 | 正式输出 | 活跃度分 |
| `overall_score` |  | 可新增 | 正式输出 | 总分 |
| `matched_signals` |  |  | 新增 | 高分依据 |
| `recommended_action` |  | 可新增 | 正式输出 | `keep / review / drop` |
| `decision_reason` |  |  | 新增 | 决策说明 |

## 五、S2 / Mail1 必备字段

这部分从 `L3 -> S2 base mapping` 开始生效。

| 字段 | L1 | L2 | L3 | S2 | 说明 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `联系方式` |  | 可新增 | 继承 | 正式输出 | 仅允许 email，不允许直接塞 link-in-bio 或社媒链接 |
| `联系方式备注` |  | 可新增 | 继承 | 正式输出 | 仅允许 email 的来源/获取方法 |
| `外链__平台抓取` |  | 可新增 | 继承 | 正式输出 | Bio / link-in-bio / newsletter / socials，不等于 email |
| `Mail1发出状态` |  |  |  | 新增 | 默认留空 |
| `Mail1_Hook` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Greeting_Name` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Subject` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Content V1` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Content V2` |  |  |  | 新增 | S2 base 建列，默认可空 |

结论：

- `Mail1` 列从 `S2 base` 开始进入 CSV
- 不提前进入 `L2 / L3`
- `S2 merge` 只负责保留，不负责首次建列
- `联系方式` 不允许回退填入 `contact_signals / external_links`

## 六、TikTok 灵活字段

当前策略：

- 先尽量保留 collector 能稳定拿回的全部字段
- 等第一次真实 L1 run 完成后，再决定哪些字段降级为非默认导出
- 对 coldmail 最有价值的字段，不要因为“看起来冗余”而过早删除

- `content_id`
- `author_unique_id`
- `author_id`
- `nickname`
- `sec_uid`
- `create_time`
- `share_count`
- `collect_count`
- `music_title`
- `region`
- `is_ad`
- `aweme_type`
- `cover_url`
- `duration`
- `session_required`
- `proxy_required`

## 七、TikTok alias

- `creator_handle` -> `author_unique_id`
- `display_name` -> `nickname`

## 八、当前推荐保留给 coldmail 的最佳字段

以下字段应优先保留到 `L2 / L3 / S2`：

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
- `recommended_action`
- `decision_reason`
