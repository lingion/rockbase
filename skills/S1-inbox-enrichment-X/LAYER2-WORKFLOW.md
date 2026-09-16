---
title: Layer 2 Workflow
status: active
date: 2026-03-25
tags:
  - social-agency
  - x
  - enrichment
  - workflow
---

# Layer 2 Workflow

本文件定义 `S1-inbox-enrichment-X` 的标准 Layer 2 工作流。

适用范围：

- 已有 X 名单
- 已有主表 CSV
- 目标是补齐事实字段、计算字段、原始 JSON 与后续 Recommendation 输入

不适用范围：

- Layer 1 模糊搜索找人
- 大规模推荐写作
- 报价、画像、商务判断

## Workflow Goal

把一个已有的 X 名单，稳定推进到以下状态：

1. 原始 JSON 已落到当天 `workbench/{YYYY-MM-DD}/`
2. 可直接抓到的字段已经回填
3. 抓不到的行被明确标记为失败项
4. 失败项进入 handle 修复循环
5. `404`、`unresolved` 和 `media/institution` 被单独标注并沉到底部

## Canonical Order

### Phase 0: Backup

先备份，再动主表。

- 备份路径：`Agency/list-bak/{YYYY-MM-DD}/`
- 命名：`{文件名}_bak_{HHMMSS}.csv`

### Phase 1: Deduplicate

先去重，再 enrichment。

推荐主键优先级：

1. `账号ID`
2. `账号链接`

说明：

- 如果同一账号重复出现，只保留信息更完整的一行
- 去重报告应单独落盘，不要默默删数据

### Phase 2: First Fetch

使用当前 `账号ID` 直接抓第一轮原始 JSON。

默认执行规则：

- `10 个一组`
- 每组写一次 manifest 进度
- 不要一次性全量怼 API
- 如果发现旧抓取进程残留，先清理旧进程，再继续新批次
- manifest 必须记录标准状态：
  - `ok`
  - `empty`
  - `account_not_exist`
  - `network_error`
  - `bad_payload`

产物：

- `x_api_sample_{handle}.json`
- `x_api_manifest_{batch}.json`

要求：

- 必须落到当天 `workbench/{YYYY-MM-DD}/`
- 不允许只在终端里看结果

### Phase 3: First Enrichment

使用第一轮 JSON 回填 Layer 2 字段。

本阶段只补：

- `频道/作者名称`
- `账号链接`
- `语言`
- `粉丝数`
- `账号简介__平台抓取`
- `Latest Activity Proof`
- `外链__平台抓取`
- `近期10条均播`
- `近10条平均ER（按曝光）`
- `近10条平均ER（按粉丝）`
- `联系方式备注`

### Phase 4: Failure Detection

从第一轮 enrichment 后识别失败项。

失败项判定标准：

- `Latest Activity Proof` 为空
- 或 `API 无 tweets`
- 或关键字段仍为空且 manifest 显示 `tweet_count = 0`

### Phase 5: Handle Repair Loop

只对失败项做 handle 修复，不全表乱修。

顺序：

1. 先做离线候选推断
2. 再用 Omni-Chrome 小批量验证
3. 再用 API 复验候选 handle
4. 只有候选与 API 都成立时，才写回主表

推荐节奏：

- `4 个一组`
- 慢速跑 Omni-Chrome
- 每组结束后立即 API 复验

### Phase 6: Second Enrichment

修复 handle 后，重新跑 fetch + enrich。

要求：

- 不跳过 JSON 落盘
- 不跳过 manifest
- 不允许“只修 handle 不重抓”

### Phase 7: Final Labeling

对最终表补标签：

- `404`
- `unresolved`
- `media/institution`

同时输出：

- `x_retry_queue_{table}.json`

标签写入：

- 第一列 `备注`

使用英文标记：

- `404`
- `unresolved`
- `media/institution`

### Phase 8: Bottom Placement

把以下行沉到底部：

1. `media/institution`
2. `404`
3. `unresolved`
4. `media/institution | unresolved`

强规则：

- `unresolved` 必须在最下面
- `media/institution` 在 unresolved 之上
- `404` 如果同时 unresolved，则跟随 unresolved 一起沉底

## Field Rules

### `语言`

依据最近一批原创主帖的 `lang` 分布推断：

- `zh >= 60%` -> `中文`
- `en >= 60%` -> `English`
- `zh + en` 都高 -> `中英双语`

### `近期10条均播`

口径：

- 最近 `10` 条原创主帖
- 排除 replies
- 排除 retweets
- 排除 quote tweets
- 取 `views.count`
- 求平均

显示格式：

- 整数
- 千分位

### `近10条平均ER（按曝光）`

单条口径：

`(likes + replies + retweets + quotes) / views`

汇总口径：

- 最近 `10` 条原创主帖
- 排除 quote tweets
- 先算每条 ER
- 再取平均

显示格式：

- 百分比
- 保留 1 位小数

### `近10条平均ER（按粉丝）`

单条口径：

`(likes + replies + retweets + quotes) / followers_count`

汇总口径：

- 最近 `10` 条原创主帖
- 排除 quote tweets
- 先算每条 ER
- 再取平均

补充清空规则：

- 若源 JSON 的 `Latest Activity Proof < 2026-01-01`
- 则清空：
  - `近期10条均播`
  - `近10条平均ER（按曝光）`
  - `近10条平均ER（按粉丝）`
- 并在 `联系方式备注` 追加：
  - `Recent-10 metrics cleared: latest activity before 2026-01-01`

显示格式：

- 百分比
- 保留 1 位小数

## Output Files

每次 workflow 至少要留下这些文件：

- `x_api_manifest_{batch}.json`
- `x_handle_repairs_*.json`
- `x_ai_*_remaining_unresolved*.json`
- `x_ai_*_flagged_bottom*.json`
- `x_ai_*_finalize*.json`
- `x_retry_queue_{table}.json`

## Recommended Entry

如果任务是标准 Layer 2，请优先使用：

`python3 scripts/run_layer2_workflow.py --csv <csv> --batch-name <name>`

标准抓取节奏：

- `chunk-size = 10`
- 只有在明确需要时才覆盖默认值

只在以下情况拆分脚本单独跑：

- 需要人工插入 handle 修复
- 只做 recommendation input
- 只想重跑 enrich，不想重抓
- 只想重跑最终 `404 / unresolved / media/institution` 标记与排序
