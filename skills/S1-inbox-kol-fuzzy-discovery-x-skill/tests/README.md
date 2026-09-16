---
tags:
  - SocialAgency
  - Skills
  - X
  - KOLDiscovery
  - Tests
date: 2026-03-31
status: active
---

# tests 目录说明

本目录用于承接 `Layer1` 可行性测试、MVP 原型与运行依赖资产。

目录约定：

- `scripts/`：放测试脚本、命令包装器、adapter 原型
- `results/`：放原始抓取结果、标准化结果、对比表
- `logs/`：放运行日志、失败记录、复现记录

当前阶段，这里主要用于验证：

- `Scweet`
- `twscrape`
- `snscrape`
- `XActions`
- 其他 Layer1 参考工具
- `Scweet -> user-info -> shortlist` 的 MVP 链路

后续如果开始正式开发 provider adapter，这个目录也可以继续承接原型验证代码。

## 当前实际分层

- `tests/scripts/`
  - 放 probe、MVP 原型、材料整理脚本
- `tests/results/`
  - 放测试证据、provider feasibility notes、原始 `.db/.json`
- `tests/.env.layer1.local`
  - 放本地运行所需的 `X_AUTH_TOKEN`

说明：

- `tests/` 不是正式业务交付目录
- 正式业务产物仍应进入 `workbench/{YYYY-MM-DD}/`
- `tests/vendor/` 是外部参考与 vendor 代码，不作为本 skill 自己的测试覆盖统计

## 中间数据保留规则

如果当天目标是做出可交付的 MVP shortlist，则中间数据必须保留，但要分层保留，避免把临时噪音和正式资产混在一起。

### 必须保留的三层数据

- `raw search results`
  - 作用：保留 provider 原始召回证据，便于复盘 query 质量、排查 provider 问题、解释候选人来源。
- `normalized candidates`
  - 作用：把不同 provider 的输出映射成统一候选结构，供后续去重、补全、打分使用。
- `final shortlist`
  - 作用：作为当天 MVP 的正式交付结果，用于后续 enrichment、review 和 Agency 使用。

### 当前推荐落盘位置

- `tests/results/`
  - 放测试阶段的 `probe` 结果、可行性记录、provider 对比结论、少量原始样例。
- `workbench/{YYYY-MM-DD}/`
  - 放当天 MVP 的正式业务产物，包括 raw candidates、normalized candidates、final shortlist、summary。

### 推荐文件命名

当天如果要产出一轮 MVP，建议至少保留以下文件：

- `x_kol_mvp_raw_candidates_{YYYY-MM-DD}.csv`
- `x_kol_mvp_normalized_candidates_{YYYY-MM-DD}.csv`
- `x_kol_mvp_shortlist_{N}_{YYYY-MM-DD}.csv`
- `x_kol_mvp_summary_{YYYY-MM-DD}.md`

其中：

- `raw_candidates`
  - 保存原始召回结果或近原始结果，不要求完全清洗。
- `normalized_candidates`
  - 保存统一字段后的候选池，是后续 dedupe / scoring 的输入层。
- `shortlist`
  - 保存最终交付用候选名单，数量可带入文件名，例如 `100`。
- `summary`
  - 保存本轮 query、provider、筛选规则、已知问题、产出数量摘要。

### 不建议保留的内容

- 无意义的临时 stdout 拷贝
- 重复的同名试验文件
- 无法说明来源与用途的中间碎片 JSON

### 执行原则

- `tests/results/` 负责“测试证据与方法验证”
- `workbench/{YYYY-MM-DD}/` 负责“当天可交付业务产物”
- 后续如果脚本正式化，默认应自动同时产出：
  - 一份可回溯的 raw / normalized 数据
  - 一份可交付的 shortlist 数据
