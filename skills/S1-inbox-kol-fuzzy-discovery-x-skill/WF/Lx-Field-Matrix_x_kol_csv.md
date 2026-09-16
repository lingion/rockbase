---
description: "[Field Matrix] X KOL Discovery CSV 字段继承表 | 用于查看 L1 / L2 / L3 三层 CSV 的字段演进关系。"
---

# Lx-Field-Matrix_x_kol_csv

> 用途：这份表不是 workflow，也不是脚本说明。  
> 它只回答一件事：`L1 / L2 / L3` 每一层 CSV 到底长什么样，哪些字段是继承下来的，哪些字段是这一层新加的。

## 一、主干继承字段

这部分是三层之间最核心的“主干字段”。  
原则是：越靠上越稳定，越不应该在后续层被丢掉。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `username` | 输出 | 继承 | 继承 | 全链路主键，必须保留 |
| `display_name` | 输出 | 继承/更新 | 继承 | 显示名，可在 L2 用 profile info 校正 |
| `matched_queries` | 输出 | 继承 | 继承 | 发现层命中依据 |
| `tweet_count` | 输出 | 继承 | 继承 | 本轮 discovery 命中的帖子数，不是账号总发帖数 |
| `sample_posts` | 输出 | 继承 | 继承 | 给人工快速感知话题相关性 |
| `top_tweet_url` | 输出 | 继承 | 继承 | 当前最强发现证据链接 |
| `source_tweet_ids` | 输出 | 继承 | 继承 | 发现证据链 |
| `provider_source` | 输出 | 继承 | 继承 | L1 来源 provider |

## 二、L1 热度与发现字段

这部分是 `L1` 的重点。  
主要目标不是“补 profile”，而是回答：

- 这个账号为什么被找到
- 它命中的帖子热不热
- 它值不值得进入 L2

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `max_views` | 新增 | 继承 | 继承 | 命中帖子中的最高浏览量，当前最关键热度字段 |
| `max_likes` | 新增 | 继承 | 继承 | 命中帖子中的最高点赞数 |
| `max_retweets` | 新增 | 继承 | 继承 | 命中帖子中的最高转推数 |
| `max_comments` | 新增 | 继承 | 继承 | 命中帖子中的最高评论数 |

## 三、L2 Profile 补全字段

这部分是 `L2` 新增的“资料层字段”。  
它们应该建立在 `L1` 主干不丢失的基础上。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `bio` |  | 新增 | 继承 | 标准化简介 |
| `location_raw` |  | 新增 | 继承 | 原始 location |
| `followers_count` |  | 新增 | 继承 | 粉丝数 |
| `following_count` |  | 新增 | 继承 | 关注数 |
| `statuses_count` |  | 新增 | 继承 | 账号总发帖数 |
| `verified` |  | 新增 | 继承 | 官方认证 |
| `blue_verified` |  | 新增 | 继承 | 蓝标认证 |
| `profile_url` |  | 新增 | 继承 | 主页链接 |
| `enrichment_provider` |  | 新增 | 继承 | 当前补全来源 |

## 四、L2 可增强字段

这部分是 `L2` 后续增强补全最适合继续长出来的字段。  
当前可以先作为预留字段，不要求第一天都实现。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `recent_tweets` |  | 可新增 | 继承 | 最近帖子集合 |
| `external_links` |  | 可新增 | 继承 | Bio/主页外链 |
| `contact_signals` |  | 可新增 | 继承 | 邮箱、官网、Linktree 等线索 |
| `profile_data_status` |  | 可新增 | 继承 | 补全状态标记 |
| `needs_enhanced_enrichment` |  | 可新增 | 继承 | 是否需要继续走 ScrapeCreators/OmniChrome |

## 五、L3 决策字段

这部分是 `L3` 新增的“判断层字段”。  
这层才是 shortlist 真正成立的地方。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `country_inferred` |  |  | 新增 | 推断国家 |
| `country_confidence` |  |  | 新增 | 国家判断置信度 |
| `primary_language` |  |  | 新增 | 主语言 |
| `language_mix` |  |  | 新增 | 语言混合情况 |
| `topic_match_score` |  |  | 新增 | 话题匹配分 |
| `profile_match_score` |  | 可新增 | 正式输出 | profile 质量分 |
| `activity_score` |  | 可新增 | 正式输出 | 活跃度分 |
| `overall_score` |  | 可新增 | 正式输出 | 总分 |
| `matched_signals` |  |  | 新增 | 高分依据摘要 |
| `recommended_action` |  | 可新增 | 正式输出 | `keep / review / drop` |
| `decision_reason` |  |  | 新增 | 简要决策说明 |

## 六、按层理解

如果按最简单的方式理解三层 CSV：

- `L1`：先把“谁值得看”找出来
- `L2`：把“这个人到底是谁”补出来
- `L3`：把“要不要留”判断出来

所以你以后看 CSV 进度时，可以只抓这几个核心变化：

- `L1` 重点看：`max_views / max_likes / matched_queries`
- `L2` 重点看：`bio / followers_count / verified / location_raw`
- `L3` 重点看：`overall_score / recommended_action`

## 七、建议的字段稳定性

最稳定、最不该乱改名的字段：

- `username`
- `display_name`
- `matched_queries`
- `sample_posts`
- `top_tweet_url`
- `followers_count`
- `bio`
- `overall_score`
- `recommended_action`

当前最值得后续考虑改名的字段：

- `tweet_count`

原因：

- 它实际表示的是“本轮 discovery 命中的帖子数”
- 容易和账号总发帖数混淆

后续更清晰的名字可以考虑：

- `matched_tweet_count`
- `discovery_tweet_count`

但在正式改名前，三层里最好保持同一个名字，避免 workflow 和脚本脱节。
