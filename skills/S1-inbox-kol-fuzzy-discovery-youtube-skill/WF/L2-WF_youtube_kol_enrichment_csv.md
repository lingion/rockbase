---
description: "[Workflow] YouTube KOL Layer2 enrichment workflow."
---

# L2-WF_youtube_kol_enrichment_csv

## 核心目标

在不丢失 `L1` 发现证据的前提下，把 creator 补成可判断、可外联的对象。

## 默认批次规范

- `L2` 默认运行粒度：**20 creators / batch**
- 当 `L1 candidates` 超过 `20` 时，必须先拆分，再分批执行 `L2`
- 不把大于 `20` 的候选表默认视作单批直接全量跑
- `--limit 20` 不只是 smoke/debug 用法，而是默认吞吐单位
- 正式批次应输出可审计的 `part` 命名，例如：`batch_part1`、`batch_part2`

## L1 和 L2 的分工

YouTube 与 X 的核心分层保持一致：

- `L1` 用内容热度筛人
- `L2` 用账号体量和 profile 资料再筛一轮
- `L3` + LLM 才做最终 `keep / drop`

因此：

- `L1 gate` 默认看 `view_count / max_views`
- `L2 gate` 默认看 `followers_count`
- `L2` 不应该重新发明 discovery，也不应该丢掉 `L1` 的热内容证据

## Discovery Master 去重

`L2` 调用 YouTube API 前必须先查 `discovery master`。

介入位置：

1. `L1 candidates`
2. `L1 views gate`
3. `check discovery master`
4. 仅对 `new_candidate` 调用 YouTube API / fallback provider
5. 将本批进入 L2 的新账号写回 `discovery master`

长期主表位置：

- `docs/youtube_kol_discovery_master.csv`

审计产物：

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_master_audit_{batch}_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_master_audit_{batch}_{YYYY-MM-DD}.json`

为什么这样做：

- 避免同一 creator 在多批、多天反复进入 L2 API
- 保护 YouTube API quota 和后续 `scrapecreator` 成本
- 保证本批 `L2 / L3 / S2` 默认接近净新增口径

默认规则：

- 命中 master 的 creator 视为老人
- 老人不进入本批 L2 provider
- 老人不进入本批 L3 / S2
- 若未来需要刷新老人，应单独做 refresh workflow

## L2 新增字段

- `bio`
- `followers_count`
- `statuses_count`
- `channel_url`
- `external_links`
- `contact_signals`
- `recent_contents`
- `email_source_url`
- `contact_page_crawl_status`
- `contact_page_checked_urls`
- `enrichment_provider`

## YouTube 重点

- 优先补 `channel about`、`channel links`、频道简介
- 允许 `subscriber_count` 作为 `followers_count` 的平台映射值
- 允许 `video_count` 作为 `statuses_count` 的平台映射值
- `contact_signals` 只记录拿得到的官网、邮箱线索、社媒链接，不编造邮箱
- 缺少 API key 时，允许先走 `search fallback enrichment`，用 L1 证据先产出可 review 的 L2

## 当前数据来源

| 字段 | 默认来源 | 所在层 |
| --- | --- | --- |
| `view_count` | `yt-dlp search` 返回的视频搜索结果 | `L1 content` |
| `max_views` | 聚合同一频道下命中视频的最高 `view_count` | `L1 creator_summary` |
| `followers_count` | YouTube Data API `channels.list(part=statistics)` 的 `subscriberCount` | `L2` |
| `statuses_count` | YouTube Data API `channels.list(part=statistics)` 的 `videoCount` | `L2` |
| `bio` | YouTube Data API `channels.list(part=snippet)` 的 `description` | `L2` |
| `external_links` | 先从 YouTube API description 抽 URL，再用 ScrapeCreators YouTube channel fallback 补充 | `L2` |
| `contact_signals` | 先等于可见外链，再用 ScrapeCreators 的 `links / courses / newsletter / social links` 补充 | `L2` |
| `contact_value` | ScrapeCreators `email`、description email regex，或 contact page / website crawl 命中的邮箱 | `L2` |
| `email_source_url` | contact page / website crawl 命中邮箱时的网页来源 | `L2` |
| `contact_page_crawl_status` | contact page / website crawl 的执行状态 | `L2` |
| `contact_page_checked_urls` | contact page / website crawl 实际检查过的 URL | `L2` |

## ScrapeCreators fallback

接入方式：

- skill 根目录 `.env` 软连接到全局 `SECRTE_API_Key.env`
- 代码读取 `SCRAPECREATORS_API_KEY`
- endpoint 使用 `GET /youtube/channel?url={channel_url}`

默认补充字段：

- `contact_value`
- `contact_note`
- `external_links`
- `contact_signals`
- `scrapecreators_status`
- `scrapecreators_handle`
- `scrapecreators_tags`
- `scrapecreators_keywords`

规则：

- ScrapeCreators 是 L2 fallback / enhancement，不替代 YouTube API 主元数据
- fallback 出错不应中断 L2，只写入 `scrapecreators_status`
- 如果命中 discovery master，本批不进入 ScrapeCreators，避免重复花费

## Contact page / website crawl

目的：

- 提高 `contact_value` 的 email 命中率
- 只使用 creator 自己公开放出的 `external_links / contact_signals`
- 不把 YouTube 本身继续扫很多遍，因为 YouTube description 和 ScrapeCreators 已经覆盖了主站内线索

触发位置：

1. YouTube Data API 补 `bio / followers_count / statuses_count`
2. ScrapeCreators fallback 补 `email / links / newsletter / tags`
3. 如果 `contact_value` 仍为空，且 `external_links` 非空，才触发 contact page crawl

默认扫描策略：

- 优先扫描官网、newsletter、Linktree/Beacons/Carrd 等 link page
- 对普通官网补扫 `/contact`、`/contact-us`、`/about`、`/about-us`
- 跳过 YouTube、X/Twitter、Instagram、TikTok、Facebook、LinkedIn、Spotify、Discord、GitHub、Medium 等社媒/平台页
- 每个 creator 默认只取少量 base links 和页面，避免速度过慢、误触发防护或制造不必要请求
- 默认单页超时较短，完整批次建议使用保守参数：`--timeout-seconds 3 --max-urls-per-creator 4`

新增字段：

- `email_source_url`: 命中邮箱的网页地址
- `contact_page_crawl_status`: `email_found`、`email_not_found`、`no_crawlable_links` 或错误摘要
- `contact_page_checked_urls`: 本次实际检查过的网页列表

规则：

- contact page crawl 只补空邮箱，不覆盖 ScrapeCreators 已经拿到的 `contact_value`
- 失败不影响 L2 行产出，只写状态字段
- 命中的邮箱必须来自公开网页文本或 `mailto:` 链接，不做猜测式邮箱生成

如果已经有一份完成 YouTube API + ScrapeCreators 的 `L2 enriched CSV`，优先使用增量脚本补邮箱，不要重复消耗 ScrapeCreators：

```bash
PYTHONPATH="src" python3 src/youtube_kol_discovery/pipelines/augment_layer2_contact_crawl.py \
  --input-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_{YYYY-MM-DD}.csv \
  --output-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_contact_crawl_{YYYY-MM-DD}.csv \
  --timeout-seconds 3 \
  --max-urls-per-creator 4
```

整理规则：

- contact crawl 的过程输出仍先进入 `workbench/`
- 人工确认字段、命中率和批次口径后，再复制/重命名到 `deliverables/`
- `deliverables/` 只保留最终批次 CSV 和 merged final，不保留 runlog、audit、smoke/test 文件

## 默认 L2 准入建议

- `followers_count >= 1000` 才允许进入正式 `L3 shortlist`
- `followers_count` 缺失时不要直接删除，先标记为 `review`
- 如果 `L1 max_views` 很强但 `followers_count` 缺失，优先走 `scrapecreator` fallback 补一次
