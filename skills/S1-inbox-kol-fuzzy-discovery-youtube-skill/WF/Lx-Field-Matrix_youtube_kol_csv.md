---
description: "[Field Matrix] YouTube KOL CSV 字段继承表 | 采用必备字段 + 灵活字段模型。"
---

# Lx-Field-Matrix_youtube_kol_csv

> 用途：定义 YouTube KOL pipeline 在 `L1 / L2 / L3 / S2` 四层里的字段演进方式。  
> 原则不是强行把所有原始字段都标准化，而是采用：
>
> - `必备字段`：跨平台稳定、必须在层间继承
> - `灵活字段`：工具原生字段，尽量保留，不强制完全统一命名

## 一、共享主干字段

这部分是 YouTube 与其他平台对齐时最核心的跨平台主干。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `platform` | 输出 | 继承 | 继承 | 固定为 `youtube` |
| `creator_handle` | 输出 | 继承 | 继承 | 跨平台主键，YouTube 默认映射到 `channel_id` |
| `display_name` | 输出 | 继承/更新 | 继承 | 创作者显示名，YouTube 默认映射到 `channel_title` |
| `matched_queries` | 输出 | 继承 | 继承 | 命中的 query 证据 |
| `matched_content_count` | 输出 | 继承 | 继承 | 命中的内容数 |
| `sample_contents` | 输出 | 继承 | 继承 | 样例内容摘要 |
| `top_content_url` | 输出 | 继承 | 继承 | 当前最强信号内容链接 |
| `source_content_ids` | 输出 | 继承 | 继承 | 支撑证据链 |
| `provider_source` | 输出 | 继承 | 继承 | 当前 provider 来源 |
| `discovery_route` | 输出 | 继承 | 继承 | `content_first / account_first` |

## 二、L1 必备字段

这部分是 `L1` 最低契约。  
无论底层走 `yt-dlp`、API 还是后续别的 provider，都要尽量先把这些字段落下来。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `content_title` | 新增 | 继承 | 可保留 | 内容标题，关键词匹配主入口 |
| `theme_text` | 新增 | 继承 | 可保留 | 用于主题/关键词匹配的文本 |
| `content_url` | 新增 | 继承 | 可保留 | 原内容链接 |
| `content_tags_or_hashtags` | 新增 | 继承 | 继承 | 标签或主题词 |
| `view_count` | 新增 | 继承 | 可保留 | 单条内容流量门槛字段 |
| `like_count` | 新增 | 继承 | 可保留 | 单条内容互动字段 |
| `comment_count` | 新增 | 继承 | 可保留 | 单条内容互动字段 |
| `max_views` | 新增 | 继承 | 继承 | 创作者命中内容里的最高浏览量 |
| `max_likes` | 新增 | 继承 | 继承 | 创作者命中内容里的最高点赞数 |
| `max_comments` | 新增 | 继承 | 继承 | 创作者命中内容里的最高评论数 |
| `l2_eligible` | 新增 | 继承 | 可保留 | 是否允许进入 L2 |
| `l2_skip_reason` | 新增 | 继承 | 可保留 | 跳过原因 |

## 三、L2 必备字段

这部分是 `L2` 的标准化补全字段。  
目标是：在保留 `L1` 发现证据的前提下，把频道资料补成可判断对象。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `bio` |  | 新增 | 继承 | 标准化频道简介 |
| `followers_count` |  | 新增 | 继承 | YouTube 对应 `subscriber_count` |
| `following_count` |  | 可新增 | 继承 | YouTube 通常缺失，预留 |
| `statuses_count` |  | 新增 | 继承 | 对应频道视频总数 |
| `verified` |  | 新增 | 继承 | 频道认证状态 |
| `profile_url` |  | 新增 | 继承 | 频道主页链接 |
| `external_links` |  | 可新增 | 继承 | 简介或主页外链 |
| `contact_signals` |  | 可新增 | 继承 | 邮箱、官网、Linktree 等线索 |
| `contact_value` |  | 可新增 | 继承 | 最终命中的邮箱或主要联系方式 |
| `contact_note` |  | 可新增 | 继承 | 联系方式来源说明 |
| `email_source_url` |  | 可新增 | 继承 | contact page / website crawl 命中邮箱的网页来源 |
| `contact_page_crawl_status` |  | 可新增 | 继承 | contact page / website crawl 执行状态 |
| `contact_page_checked_urls` |  | 可新增 | 可保留 | contact page / website crawl 实际检查的 URL |
| `enrichment_provider` |  | 新增 | 继承 | 当前补全来源 |
| `enrichment_status` |  | 可新增 | 继承 | 补全状态 |
| `enrichment_error` |  | 可新增 | 继承 | 错误信息 |

## 四、L3 必备字段

这部分是 `L3` 的决策层字段。  
它不负责找人，也不负责基础资料抓取，只负责判断和分桶。

| 字段 | L1 | L2 | L3 | 说明 |
| :--- | :---: | :---: | :---: | :--- |
| `country_inferred` |  |  | 新增 | 推断国家 |
| `country_confidence` |  |  | 新增 | 国家判断置信度 |
| `primary_language` |  |  | 新增 | 主语言 |
| `language_mix` |  |  | 新增 | 语言混合情况 |
| `topic_match_score` |  | 可新增 | 正式输出 | 主题匹配分 |
| `profile_match_score` |  | 可新增 | 正式输出 | profile 质量分 |
| `activity_score` |  | 可新增 | 正式输出 | 活跃度分 |
| `overall_score` |  | 可新增 | 正式输出 | 总分 |
| `matched_signals` |  |  | 新增 | 高分证据摘要 |
| `recommended_action` |  | 可新增 | 正式输出 | `keep / drop` |
| `decision_reason` |  |  | 新增 | 简短决策说明 |

## 五、S2 / Mail1 必备字段

这部分从 `L3 -> S2 base mapping` 开始生效。  
规则参考 X 的成熟 skill：`Mail1` 列必须在 `S2 base` 首次建好，但默认先留空，等 merge 后再填。

| 字段 | L1 | L2 | L3 | S2 | 说明 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `联系方式` |  | 可新增 | 继承 | 正式输出 | 仅允许 email，来自 `contact_value` |
| `联系方式备注` |  | 可新增 | 继承 | 正式输出 | 仅允许 email 的来源/获取方法，来自 `contact_note` |
| `外链__平台抓取` |  | 可新增 | 继承 | 正式输出 | 官网 / link page / newsletter / socials，不等于 email |
| `Mail1发出状态` |  |  |  | 新增 | 默认留空，表示尚未进入发信状态机 |
| `Mail1_Hook` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Greeting_Name` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Subject` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Content V1` |  |  |  | 新增 | S2 base 建列，DM fill 阶段填写 |
| `Mail1_Content V2` |  |  |  | 新增 | S2 base 建列，默认可空 |

结论：

- `L1 / L2 / L3` 不加入 `Mail1` 列
- 从 `L3 -> S2 base mapping` 开始，必须把 `Mail1` 列加入 CSV
- `S2 merge` 只负责保留这些列，不负责首次建列
- `Mail1` 文案的真实填充时点是 merge 后的 `DM fill / 3.2`
- `联系方式` 不允许回退填入 `contact_signals / external_links`

## 六、YouTube 灵活字段

这部分是建议尽量保留的 `YouTube / yt-dlp` 原生字段。  
它们不要求跨平台强统一，但只要拿到了，就应尽量原样保留在 `L1 raw` 或 `L1 unified` 靠后列。

- `content_id`
- `channel_id`
- `channel_title`
- `channel_url`
- `channel_is_verified`
- `uploader`
- `uploader_id`
- `uploader_url`
- `description`
- `duration`
- `timestamp`
- `release_timestamp`
- `availability`
- `live_status`
- `thumbnails`
- `_type`
- `ie_key`

## 七、按层理解

- `L1`：先保留所有能支撑“通过热内容找到背后 KOL”的字段
- `L2`：补齐创作者资料和联系方式线索
- `L3`：只做评分、排序和决策
- `S2`：把 shortlist 变成可继续 Mail1 / drafts 的外联底稿

## 八、推荐原则

- 不要求不同平台在 `L1` 把所有原始字段都标准化成同一个名字
- 只要求先满足 `L1-L2-L3` 的必备字段契约
- `Mail1` 字段属于 `S2` 契约，不应提前渗透进 `L2/L3`
- 工具原生字段尽量全量保留，放在表格靠后位置
- 用户主操作面优先看必备字段，调试和追溯再看灵活字段

## 九、YouTube alias

- `creator_handle` -> `channel_id`
- `display_name` -> `channel_title`
- `followers_count` -> `subscriber_count`
