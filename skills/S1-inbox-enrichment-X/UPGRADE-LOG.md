---
title: S1 Inbox Enrichment X Upgrade Log
status: active
date: 2026-03-25
tags:
  - social-agency
  - x
  - enrichment
  - changelog
---

# Upgrade Log

## 2026-04-13

### Rename: `S1-inbox-X-enrichment` -> `S1-inbox-enrichment-X`

本次变更只调整 skill 命名与目录顺序，不改动 enrichment 业务逻辑。

影响说明：

- 相对路径脚本可继续工作，因为主要通过 `__file__` / 当前脚本目录定位
- 外部引用如果写死旧目录名，需要改为新目录名
- `SKILL.md` 的 `name` 字段已同步切换为 `s1-inbox-enrichment-x`

## 2026-03-25

### vNext: Layer 2 Stabilization Upgrade

本次升级基于真实跑表经验，重点不是新增字段，而是提升 Layer 2 的稳定性、可恢复性与可审计性。

#### 1. 抓取默认强制 `10 个一组`

- `run_layer2_workflow.py` 默认 `--chunk-size 10`
- `fetch_x_user_tweets.py` 默认 `--chunk-size 10`
- `LAYER2-WORKFLOW.md` 与 `SKILL.md` 已同步明确写入

#### 2. 抓取前自动清理残留 fetch 进程

新增行为：

- workflow 在进入 fetch 前，会清理旧的 `fetch_x_user_tweets.py` 进程
- 目的是避免多轮未退出抓取相互抢占，导致 manifest 与 sample JSON 不稳定

对应脚本：

- `scripts/run_layer2_workflow.py`

#### 3. Manifest 状态标准化

`fetch_x_user_tweets.py` 现在会为每条抓取记录补齐这些字段：

- `result_type`
- `message`
- `batch_name`
- `batch_index`
- `skipped_existing`

当前标准 `result_type`：

- `ok`
- `empty`
- `account_not_exist`
- `network_error`
- `bad_payload`
- `http_error`

这解决了之前必须反复打开原始 JSON 才能判断 `404 / 无 tweets / 网络异常` 的问题。

#### 4. Enrich 对异常 JSON 增加容错

新增行为：

- 如果 sample JSON 缺少 `response_json`
- enrichment 不再整轮报错退出
- 会把异常写入 `联系方式备注`

对应脚本：

- `scripts/enrich_x_csv_layer2.py`

#### 5. Finalize 自动输出 Retry Queue

新增产物：

- `x_retry_queue_{table}.json`

作用：

- 把 `account_not_exist`
- `empty`
- `network_error`
- `bad_payload`
- `unresolved_other`

按类别整理成下一轮 handle repair / retry 的直接输入。

对应脚本：

- `scripts/finalize_x_csv_layer2.py`

#### 6. Finalize 清洗历史脏标签

新增行为：

- 自动去掉 `CREAO raw import`
- 自动去掉字符串化的 `nan`

这样主表备注只保留当前 workflow 真正有效的标签：

- `media/institution`
- `404`
- `unresolved`

#### 7. 失败备注标准化

`enrich_x_csv_layer2.py` 现在优先写固定英文备注，而不是混杂自由文本。

当前标准备注包括：

- `API no tweets`
- `Account doesn't exist`
- `Network error`
- `Bad payload`
- `Original sample < 10 (N)`

这样后续筛选、透视表和 retry queue 会更稳定。

#### 8. `media/institution` 规则收窄

`finalize_x_csv_layer2.py` 的组织号判定已经收紧：

- 优先看 `账号类目标签__平台抓取`
- 再看 `频道/作者名称 + 账号ID`
- 不再只因为 bio 里的弱词就打 `media/institution`

目标是减少把个人号误沉到底部的情况。

## Current Recommendation

当前推荐的标准执行顺序：

1. `run_layer2_workflow.py`
2. 查看主表
3. 查看 `x_retry_queue_{table}.json`
4. 对 retry queue 进入 handle repair loop

## Known Caveat

如果手工执行脚本时，把 `enrich` 和 `finalize` 并行启动，仍可能造成标签时序错误。

规范做法：

- 必须走 workflow 串行执行
- 或者手工执行时严格按：
  - `fetch`
  - `enrich`
  - `finalize`

顺序运行

## 2026-03-26

### Layer 1 Discovery Tuning v2

本次升级基于 `OpenClaw / US / English / AI creators` 的真实测试结果，目标是让 Layer 1 更像“找个人 AI 博主”，而不是泛泛抓一堆 AI 讨论噪音。

#### 1. Query 生成从长句改为短 query 优先

当前策略：

- 少生成整句 query
- 优先保留：
  - `brand`
  - `brand_exact`
  - `brand_adjacent`
  - `brand_signal`
  - `adjacent`
  - `role`
  - `scenario`
  - `signal`

这解决了第一轮里大量长句 query 直接 `0 results` 的问题。

#### 2. Layer 1 支持英文过滤与营销词排除

`build_layer1_queries.py` 与 `run_layer1_workflow.py` 新增：

- `--lang`
- `--exclude-terms`

当前推荐口径：

- `lang:en`
- `-newsletter -news -agency -seo -growth -marketer -marketing`

#### 3. Candidate Pool 新增个人博主筛选信号

`build_x_candidate_pool.py` 现在不只输出命中次数，还会输出：

- `display_name`
- `brand_query_hits`
- `marketing_risk`
- `creator_signal`
- `creator_fit_score`
- `sample_text`

作用：

- 不再只靠 `total_hits` 排序
- 可以更快看出哪些更像个人 creator / builder
- 可以更快排掉营销味或纯噪音账号

#### 4. 实测效果

基于 `openclaw-us-en` 测试：

- v1：`30 queries / 11 zero-result`
- v2：`33 queries / 0 zero-result`

说明 Layer 1 v2 的方向是正确的，至少在 X 搜索可用性上已经明显改善。

#### 5. 当前仍存在的下一轮优化点

还需要继续收敛：

- 过泛角色词，例如 `creators`
- 产品本体账号 `openclaw` 本身在候选池中的排序
- “美国为主”的信号仍未在 Layer 1 里强约束

当前判断：

- Layer 1 v2 已适合做第一轮召回
- 但还不适合直接当最终 shortlist
