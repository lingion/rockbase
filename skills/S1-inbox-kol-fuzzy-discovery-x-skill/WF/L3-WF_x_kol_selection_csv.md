---
description: "[Workflow] X KOL Layer3 决策层 CSV 工作流 | 目标：把 Layer2 enriched CSV 升级成 shortlist CSV。"
---

# L3-WF_x_kol_selection_csv

> 用途：把 `Layer2 enriched CSV` 转成一张最终可以交给 Agency 使用的 `Layer3 shortlist CSV`。

## 一、核心目标

`Layer3` 只负责一件事：做决定。

这层负责：

- 打分
- 排序
- 分桶
- 输出 shortlist / review / outreach 候选

它不再负责找人，也不负责基础资料补全。

## 二、输入与输出

### 输入 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L2_enriched_batch1_{YYYY-MM-DD}.csv`

### 主输出 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L3_shortlist_batch1_{YYYY-MM-DD}.csv`

### 辅助输出

- `workbench/{YYYY-MM-DD}/x_kol_L3_review_table_batch1_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_L3_audit_summary_batch1_{YYYY-MM-DD}.md`
- `workbench/{YYYY-MM-DD}/x_kol_L3_runlog_batch1_{YYYY-MM-DD}.json`

## 三、CSV 字段契约

`Layer3 shortlist CSV` 应保留 `Layer2` 的核心资料字段，并新增这些决策字段：

| 字段 | 说明 |
| :--- | :--- |
| `country_inferred` | 推断国家 |
| `country_confidence` | 国家判断置信度 |
| `primary_language` | 主语言 |
| `language_mix` | 语言混合情况 |
| `topic_match_score` | 话题匹配分 |
| `profile_match_score` | profile 质量分 |
| `activity_score` | 活跃度分 |
| `overall_score` | 总分 |
| `matched_signals` | 触发高分的证据摘要 |
| `recommended_action` | `keep / review / drop` |
| `decision_reason` | 简短决策说明 |

## 四、生成规则

1. `Layer3` 必须基于 `Layer2 enriched CSV` 打分，不能重新回头改 `Layer1`。
2. `Layer3` 有硬 gate：`followers_count < 1000` 的账号不能进入 `Layer3`。
3. `recommended_action` 必须是明确字段，不允许只靠人工阅读分数理解。
4. `keep / review / drop` 三种状态要可排序、可筛选。
5. 最终 shortlist 要保证人一眼能看出：
   - 为什么留
   - 为什么待复核
   - 为什么丢弃

## 五、排序规则

`Layer3 shortlist CSV` 默认排序：

1. `followers_count` 降序
2. `overall_score` 降序
3. `activity_score` 降序
4. `username` 升序

说明：

- `Layer3` 仍保留 `recommended_action` 字段用于筛选和解释。
- 但最终 CSV 的主排序统一看 `followers_count`，方便人工优先查看更大体量账号。

## 六、保留与去掉

必须保留：

- `Layer2` 的核心 profile 字段
- `Layer1` 的基本发现痕迹，至少保留 `matched_queries / sample_posts / top_tweet_url`
- 所有评分字段
- 最终推荐动作

允许去掉：

- 纯技术型中间辅助字段
- 不影响业务判断的 debug 字段

## 七、CSV 升级关系

最终升级路径应该是：

- `x_kol_L1_candidates_batchN_{YYYY-MM-DD}.csv`
  ->
- `x_kol_L2_enriched_batchN_{YYYY-MM-DD}.csv`
  ->
- `x_kol_L3_shortlist_batchN_{YYYY-MM-DD}.csv`

所以你看进度的时候，不需要读脚本，只要看三张 CSV 的演进就知道现在做到哪一层了。

补充规则：

- 同一天可存在多批
- 文件名必须显式带 `batch1 / batch2 / batch3`
- 不允许后一批覆盖前一批
- `followers_count < 1000` 的账号只允许停留在 `Layer2`，不进入 `Layer3 shortlist / review`

## 八、脚本入口

当前对应脚本：

- `src/x_kol_discovery/pipelines/run_layer3_from_enriched.py`
- `src/x_kol_discovery/pipelines/run_batch_pipeline.py`

推荐调用方式：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer3_from_enriched.py \
  --input-csv workbench/2026-04-01/x_kol_L2_enriched_batch1_2026-04-01.csv \
  --run-date 2026-04-01 \
  --batch batch1 \
  --shortlist-target 100
```

## 九、这层完成的判定标准

- 有一张稳定的 shortlist CSV
- `keep / review / drop` 已经明确
- 排序规则已固定
- 人能直接拿这张表进入 outreach 或 handoff
