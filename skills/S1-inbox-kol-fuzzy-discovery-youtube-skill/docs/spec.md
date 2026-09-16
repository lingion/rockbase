---
tags: [spec, youtube, kol, skill, discovery]
date: 2026-04-10
status: active
---

# S1 Inbox YouTube KOL Fuzzy Discovery Spec

## 0. Recommended Architecture Tree

```text
S1-inbox-kol-fuzzy-discovery-youtube-skill/
├── SKILL.md
├── WF_Int.md
├── WF/
├── docs/
├── specs/
├── src/
└── tests/
```

## 1. Background & Problem

现有 X skill 已经证明：真正稳定的资产不是平台名，而是 `L1 -> L2 -> L3 -> S2` 这条业务骨架。YouTube 需要的是一套新的 `L1` 搜索实现，而不是重造后半段 workflow。

这里的主问题不是“能不能拿到平台总榜”，而是：

- 用户给一个领域角度
- skill 要通过大量热内容搜索
- 再把这些热内容背后的 creator 聚合出来

所以这是一个 `search-first, hot-content-led KOL mining` 系统。

## 2. Target Positioning

它是一个 YouTube KOL 模糊发现 skill。

它不是：

- 自动联系 bot
- 全站爬虫
- 通用媒体监控平台

## 3. User Inputs & Outputs

### Inputs

- `platform`
- `topic_query`
- `country_include`
- `language_include`
- `l1_mode`
- `search_queries`
- `seed_channels`
- `provider_plan`
- `shortlist_target`

### Outputs

- `L1 unified table`
- `L1 candidates`
- `L2 enriched`
- `L3 shortlist`
- `S2 outreach export`
- runlog / audit summary

## 4. Core Workflow

1. Intake
2. Build task spec
3. Update query library before finalizing query names
4. Run multi-query `content-first` hot-content search
5. Aggregate hot videos back to creators
6. Run `account-first` expansion only when needed
7. Merge and dedupe by `channel_id`
8. Enrich to L2
9. Score to L3
10. Export S2

## 5. Key Modules

- `task spec`
- `provider plan`
- `query pack`
- `L1 adapters`
- `creator normalization`
- `L2 enrichment`
- `L3 scoring`
- `S2 export`

## 6. What Is Shared

- layer semantics
- field taxonomy
- spec structure
- shortlist semantics
- output contract

## 7. What Stays Platform-Specific In V1

- `yt-dlp` integration
- YouTube Data API key handling
- future shared-secrets env symlink for `scrapecreator` fallback
- `channel_id` and `channel_title` aliasing
- content-to-channel aggregation
- YouTube-specific contact and link extraction

## 8. Decision Rules

- 默认 `l1_mode = dual_channel`
- 默认 `search_first = true`
- 默认 `enable_discover_supplement = false`
- `content-first` 优先多 query 的 `yt-dlp` 热内容搜索
- API key 缺失不影响主流程，因为 discover 不是默认主路径
- `youtube/api-samples` 仅作 API 参考

## 9. Evaluation / Validation

- query-based hot-content search works
- multiple hit videos aggregate into one creator row
- account-first can produce channel shortlist
- discover supplement can be disabled without harming the main workflow

## 10. Output Contract

最小 L1 字段：

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

默认主输出是一张 `unified table`，其中 `row_type` 有两种：

- `content`
- `creator_summary`

这张表至少需要让 `content` 行包含：

- `content_title`
- `theme_text`
- `matched_query_text`
- `creator_handle`
- `view_count`
- `content_url`

默认 `view_count >= 1000` 才进入 `L2`

## 11. Migration / Upgrade Path

- 当前不抽 shared runtime
- YouTube 先独立落地
- YouTube 跑稳后，再评估抽离 shared query planning / normalization / S2 mapping

## 12. Acceptance Criteria

- 目录结构完整
- task spec 模板完整
- 双通道 L1 设计明确
- fallback 路径明确
- downstream L2/L3/S2 contract 明确

## 13. Next Steps

1. 先扩大 search query pack
2. 接 YouTube `L2` channel enrichment
3. 验证 search-first hot-content path
4. 再决定是否补 discover supplement
5. 再决定抽 shared core
6. 接入 `scrapecreator` fallback env symlink

## 14. Current Runtime Entrypoint

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_layer1_mvp.py \
  --spec specs/_template.youtube_kol_task.json \
  --run-date 2026-04-10
```

当前行为：

- 默认直接跑 search-first
- discover supplement 默认关闭
- 输出 `L1 candidates`、raw JSON、runlog

Layer2:

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_layer2_from_candidates.py \
  --input-csv deliverables/2026-04-10/youtube_kol_L1_candidates_2026-04-10.csv
```

当前行为：

- 有 `YOUTUBE_API_KEY` 时优先补 channels API 元数据
- 无 API key 时仍会产出一版 fallback L2，用于 review 和后续人工挑选

## Appendix. Reference Projects & What To Borrow

- `yt-dlp`: search runtime
- YouTube Data API: optional supplement only
- existing X skill: downstream workflow shape
