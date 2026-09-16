---
tags:
  - SocialAgency
  - Skills
  - X
  - KOLDiscovery
  - Plan
date: 2026-03-31
status: active
---

# Plan-X模糊搜索KOL-Skill实施计划

## 一、项目定位

本项目目标是产出一个可落地的 `X KOL 模糊搜索 skill`，用于把自然语言需求转换为：

- `Layer1` 模糊发现
- `Layer2` 资料补全与清洗
- `Layer3` 评分与 shortlist 决策

当前阶段先不追求一次完成全部功能，而是按阶段推进，优先做出可用的最小闭环。

## 二、阶段划分

### Phase 1：Layer1 可行性测试

目标：

- 验证 `Layer1` 候选工具是否真的能完成模糊搜索 KOL 的 discovery 目标
- 判断哪些工具值得保留为主 provider、辅助 provider、参考工具
- 判断哪些项目原理相同，哪些不应轻易合并

交付物：

- `docs/layer1-feasibility.md`
- provider feasibility matrix
- 初轮真实测试记录
- 默认 provider 建议

### Phase 2：架构定稿

目标：

- 固化 `Layer1 / Layer2 / Layer3` 架构
- 固化 `Layer1` 的 provider 选型逻辑
- 固化 `query spec / execution plan / provider adapter` 的基本约束

交付物：

- `docs/Spec-X模糊搜索KOL-Skill架构设计.md`
- `SKILL.md` 初版结构草案
- schema 草案

### Phase 3：最小可运行版本

目标：

- 先打通一个最小闭环
- 默认用 `Scweet` 作为 `Layer1`
- 默认用 `Scweet user-info` 作为 `Layer2`
- 用本地脚本输出基础 shortlist

交付物：

- provider adapter v1
- query planner v1
- enrichment pipeline v1
- shortlist CSV / Markdown 输出
- `L3 -> S1 Inbox` mapping v1

### Phase 4：模块化扩展

目标：

- 把 `Layer1` 做成真正可插拔
- 接入 `twscrape / snscrape / XActions`
- 完成 provider registry 与 routing policy

交付物：

- provider registry
- 多 provider routing
- merge / dedupe 规则

### Phase 5：质量与交付强化

目标：

- 强化 `Layer3`
- 提升国家、语言、话题判断质量
- 形成可供 Agency 使用的标准交付格式

交付物：

- ranking / scoring logic v2
- review table
- outreach-ready shortlist

## 三、推荐执行顺序

建议按以下顺序推进：

1. 先完成 `Layer1` 可行性测试
2. 再冻结架构与 schema
3. 再做 `Scweet -> Scweet user-info -> shortlist -> S1 Inbox mapping` 的最小闭环
4. 然后扩 provider
5. 最后做评分和交付质量强化

## 四、当前建议的首发范围

首发版本建议只做：

- `Layer1`：`Scweet`
- `Layer2`：`Scweet user-info`
- `Layer2 gate`：`max_views >= 5000`
- `Layer2 enhanced`：后续再接 `ScrapeCreators`
- `Layer2 fallback`：后续再接 `OmniChrome`
- `Layer3`：规则评分的最小版

首发版本先不做：

- 大规模代理治理
- 多 provider 并行调度
- follower graph 深扩展
- contact extraction 全自动化

## 五、关键设计文档

当前项目目录内建议作为核心输入材料使用：

- `docs/Spec-X模糊搜索KOL-Skill架构设计.md`
- `docs/TODO-skill开发清单.md`
- `tests/README.md`

## 六、下一步

下一步建议先做：

1. 补 `SKILL.md` 与 `README.md`
2. 将 `query spec schema`、`execution plan schema`、`provider adapter contract` 写成固定文档
3. 跑一轮新的批次闭环验证
4. 再决定是否接 `ScrapeCreators enhanced enrichment`
