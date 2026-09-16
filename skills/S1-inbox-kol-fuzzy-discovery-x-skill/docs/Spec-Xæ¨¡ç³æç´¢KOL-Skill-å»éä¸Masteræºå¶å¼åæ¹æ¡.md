---
tags:
  - SocialAgency
  - Skills
  - X
  - KOLDiscovery
  - Dedupe
  - Master
date: 2026-04-01
status: in_progress
---

# Spec-X模糊搜索KOL-Skill-去重与Master机制开发方案

## 一、目标

本方案只解决一件事：

把 `X KOL` skill 当前分散的重复问题，收口成内嵌在 `L1 -> L2 -> L3` 中的自动机制，而不是额外手工流程。

要解决的重复分三类：

1. `Layer1` 同一批 query pack 内部重复命中
2. 多个 batch / 多天重复搜索同类 query
3. 同一账号反复进入 `L2 API`、`L3 shortlist`、`S2`

## 二、设计原则

### 1. 去重必须内嵌，不新增手工步骤

用户以后仍然只需要：

- 启动 `WF_Spec`
- 给自然语言任务
- 跑主流程

不需要额外手动运行“去重工具”。

### 2. 优先保护 API 成本

当前最昂贵的环节不是 `Layer1 search`，而是 `Layer2 enrichment API`。

所以第一优先级是：

- 在 `L1 -> L2` 之间挡住重复账号

### 3. 允许跨天重新发现，但批次只看纯新增

同样的关键词隔天重复跑，不应被视为错误，因为：

- `X` 上可能出现新的热帖
- 同一主题可能持续有新作者进入

所以 query 侧不能做绝对去重，但账号处理侧默认采用严格新增口径：

- 同日去重
- 跨日可刷新
- 命中 `discovery master` 的账号一律视为老人，不进入本批 `L2`

## 三、总体方案

本次开发主做四件事：

1. `Layer1 Query Registry`
2. `Layer2 Discovery Master`
3. `Layer2 Master Audit`
4. `S2 Netnew Deliverable`

`S2 master` 暂不作为本期主开发项，只保留接口和后续扩展位。

## 四、Layer1 Query Registry

### 目标

避免同一天、同一任务或同一时间窗内，反复执行语义等价的 query pack。

### 集成位置

- `src/x_kol_discovery/layer1/`

当前已落地：

- `layer1/query_registry.py`

### 核心对象

`query_fingerprint`

由以下字段标准化后生成：

- `platform`
- `topic_query`
- `language_include`
- `exclude_keywords`
- `role_keywords`
- `content_keywords`
- `product_keywords`
- `workflow_keywords`
- `agentic_keywords`
- `topic_keywords`
- `since`
- `until`

### 行为规则

1. 同一天同一 `query_fingerprint`
   - 默认不重跑
   - 当前实现是直接拦截 query 执行
   - 不再重复搜索

2. 跨天相同 `query_fingerprint`
   - 允许重跑
   - 因为可能出现新热帖

3. 用户明确要求强制刷新
   - 允许跳过 registry 直接重跑

### 产物形式

长期主表建议：

- `/.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/Agency/list-master/x_kol_query_registry.csv`

字段建议：

- `query_fingerprint`
- `task_name`
- `platform`
- `topic_query`
- `since`
- `until`
- `run_date`
- `last_run_at`
- `batch_name`
- `result_count`
- `status`
- `source_l1_raw_json`
- `source_l1_candidates_csv`

## 五、Layer2 Discovery Master

### 目标

在 `max_views` gate 之后，对准备进入 `Layer2 API` 的账号做长期去重，避免重复补数和重复花费 API。

### 集成位置

- `src/x_kol_discovery/layer2/`

当前已落地：

- `layer2/discovery_master.py`

### 介入位置

流程改成：

1. `L1 raw`
2. `L1 candidates`
3. `apply_layer2_views_gate`
4. `check_discovery_master`
5. 仅对新增账号调用 `Layer2 provider`
6. `Layer2` 结果回写 `discovery master`
7. 再进入 `Layer3`

### 为什么放在这里

原因不是纯粹技术，而是业务成本：

- `max_views < threshold` 的账号本来就不会进 `L2`
- 没必要对它们做长期主表去重
- 真正值得做 master 的，是已经过了热度门槛、准备花 API 成本的账号

### 主键

- `platform + username`

### 字段建议

- `platform`
- `username`
- `display_name`
- `profile_url`
- `first_seen_date`
- `last_seen_date`
- `first_seen_batch`
- `last_seen_batch`
- `best_max_views_seen`
- `best_top_tweet_url`
- `latest_matched_queries`
- `times_seen_after_views_gate`
- `last_layer2_provider`
- `last_followers_count`
- `last_bio`
- `last_location_raw`
- `last_external_links`
- `last_contact_value`
- `last_contact_note`
- `last_enriched_at`
- `master_status`

长期主表建议：

- `/.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/Agency/list-master/x_kol_discovery_master.csv`

### 行为规则

当某账号已经过了 `Layer2 views gate`：

1. master 不存在
   - 进入 `L2 API`

2. master 存在
   - 一律视为老人
   - 不再打 API
   - 不进入本批 `L2`
   - 不进入本批 `L3 / S2`

说明：

- 当前默认批次只看“纯新增”
- 如果未来要做老人刷新，应单独设计 `refresh workflow`
- `discovery master` 继续保留全历史，但日常批次不复用老人进结果表

## 六、Layer2 Master Audit

为了让运营视角能直接看懂这批账号是怎么被分流的，当前已经补了独立审计产物：

- `x_kol_L2_master_audit_{batch}_{date}.csv`
- `x_kol_L2_master_audit_{batch}_{date}.json`

它们至少区分：

- `new_candidate`
- `blocked_by_master`
- `blocked_by_views_gate` 由 runlog 统计给出

## 七、S2 Netnew Deliverable

当前规则已经收口为：

- `workbench/` 保留全量底稿
- `deliverables/` 默认只镜像净新增 `S2`

也就是：

- 同一批正式全量 `S2` 继续写到 `workbench`
- 镜像到 skill 内交付目录时，自动剔除已经在更早 `S2 deliverables` 中出现过的账号

## 六、Layer3 与 S2 的影响

如果 `Layer2 Discovery Master` 正常工作：

- 大部分重复账号不会再次进入 `L2 API`
- 后续 `L3` 会天然接近纯新增
- `S2` 会天然接近纯新增

但这不代表后面完全不用去重。

后续仍建议保留轻量规则：

1. `Layer3`
   - 基于同一批输入自然排序与主键去重

2. `L3 -> S2`
   - 写入最终执行表时按 `platform + username` 再做一次轻量去重

本期不单独开发 `S2 master`，但 `run_l3_to_s2_mapping.py` 后续应预留升级位。

## 七、与现有规则的关系

本方案不改变当前业务 gate，只改变它们前后的去重时机。

当前业务规则仍保持：

- `L1 -> L2`: `max_views >= 5000`
- `L2 -> L3`: `followers_count >= 1000`

本方案新增的是：

- `query registry`
- `discovery master`

## 八、开发落点

本期开发建议新增或改造这些位置：

- `src/x_kol_discovery/layer1/query_registry.py`
- `src/x_kol_discovery/layer2/discovery_master.py`
- `src/x_kol_discovery/pipelines/run_layer1_mvp.py`
- `src/x_kol_discovery/pipelines/run_batch_pipeline.py`
- `src/x_kol_discovery/pipelines/run_full_pipeline.py`
- 视情况补 `io_utils.py` 的 master 读写工具

## 九、开发顺序

### Phase A

先开发：

1. `Layer2 Discovery Master`
2. 接入 `run_layer2_from_candidates.py`
3. 接入 `run_batch_pipeline.py`

理由：

- 最先节省 `ScrapeCreators` 成本
- 立刻解决“同一人反复补数”的问题

### Phase B

再开发：

1. `Layer1 Query Registry`
2. 接入 `run_layer1_mvp.py`
3. 接入 `run_batch_pipeline.py`

理由：

- 优化的是重复搜索
- 价值次于节省 API

## 十、验证方式

本期先做内部验证，不立刻抓新数据。

验证顺序：

1. 静态验证 registry/master 读写逻辑
2. 用已有 `batch1 / batch2` 文件做回放验证
3. 确认不会误挡住应进入 `L2` 的账号
4. 再用今天的 `batch1` 做真实测试

## 十一、开发前备份要求

在正式开发之前，必须把整个 skill 目录物理备份到：

- `workbench/{YYYY-MM-DD}/`

建议命名：

- `x_kol_skill_backup_before_dedupe_master_{YYYY-MM-DD}_{HHMMSS}/`

备份范围：

- 整个 `.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/`

本备份动作必须发生在代码开发开始之前，而不是开发结束之后。

## 十二、本期完成定义

满足以下条件，视为本期开发完成：

1. `Layer1` 支持 query registry
2. `Layer2` 支持 discovery master
3. 主流程自动使用两者
4. 用户不需要额外手动执行去重步骤
5. 旧 batch 回放验证通过
6. 再用新 batch 做一次真实验证
