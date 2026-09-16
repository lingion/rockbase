---
tags:
  - SocialAgency
  - Skills
  - X
  - KOLDiscovery
  - TODO
date: 2026-03-31
status: active
---

# TODO-skill开发清单

> 更新说明：本清单已按 2026-03-31 当天目录内实际产物重新对账。凡是已有文档、脚本、测试结果支撑的事项，统一标记为已完成；仍缺正式封装或定稿的事项保留未完成。

## 一、Layer1 可行性测试

- [x] 确认首轮测试主题与成功标准
- [x] 读 `Scweet` 首页与核心搜索能力
- [x] 读 `twscrape` 首页与核心搜索能力
- [x] 读 `snscrape` 首页与核心搜索能力
- [ ] 读 `XActions` 首页与核心搜索能力
- [x] 明确哪些工具需要 cookies / token / browser state
- [x] 为主测试对象建立最小测试脚本
- [x] 跑第一轮真实测试
- [ ] 输出 provider feasibility matrix
- [x] 做默认 provider / fallback provider 初判
- [x] 补充 `Scweet` 第二轮 deep probe
- [x] 补充 `bird` 可行性观察记录
- [x] 补充 `last30days-skill` 架构参考记录
- [ ] 将当前测试结论回写为正式 matrix 与固定结论版本

## 二、架构与规范

- [x] 冻结 `Layer1 / Layer2 / Layer3` 职责边界草案
- [x] 确认 `Layer1` 的 provider 分类：主候选 / 辅助候选 / 参考型工具
- [ ] 定义 `query spec schema`
- [ ] 定义 `execution plan schema`
- [ ] 定义 `provider adapter contract`
- [ ] 定义 `merge / dedupe` 输出结构
- [ ] 将架构草案收口为 v1 可执行规范，而不是继续扩调研

## 三、Layer1

- [x] 设计 `Intent Parsing` 字段规范草案
- [x] 设计 `Query Spec Generation` 规则草案
- [x] 设计 `Provider-specific Plan Compilation` 规则草案
- [ ] 把 `Scweet probe` 升级为真正的默认 provider adapter v1
- [ ] 预留 `twscrape` adapter 接口
- [ ] 预留 `snscrape` adapter 接口
- [ ] 预留 `XActions` adapter 接口
- [ ] 设计 provider registry
- [ ] 设计 routing policy
- [ ] 设计 user-level candidate normalization 结构
- [ ] 设计 tweet-level discovery signal normalization 结构
- [ ] 输出首版 `merge / dedupe` 规则

## 四、Layer2

- [x] 接入 `Scweet user-info` 作为当前默认 Layer2 基础补全
- [x] 设计 `Scweet user-info -> 标准化 profile object` 的过渡链路
- [x] 定义当前免费版 `Layer2` 准入门槛：`max_views >= 5000`
- [ ] 明确 `ScrapeCreators` 输入输出字段
- [ ] 明确 `Scweet user-info` 与 `ScrapeCreators enhanced enrichment` 的切换规则
- [ ] 明确 `OmniChrome fallback` 触发条件
- [ ] 设计 profile normalization 结构
- [ ] 设计 tweets normalization 结构
- [ ] 设计 links / contact signals 的抽取策略

## 五、Layer3

- [ ] 定义 topic score 规则
- [ ] 定义 country inference 规则
- [ ] 定义 language inference 规则
- [ ] 定义 activity score 规则
- [ ] 定义 overall score 规则
- [ ] 定义 `keep / review / drop` 推荐动作

## 六、技能文件与脚本

- [x] 编写 `SKILL.md` 初版
- [x] 补 `README.md` 作为目录入口
- [x] 编写 provider feasibility probe 脚本
- [ ] 编写 provider adapter 脚本骨架
- [ ] 编写 query planner 脚本骨架
- [ ] 编写 shortlist 输出脚本骨架
- [x] 设计测试输入样例
- [ ] 整理脚本目录，区分 `probe`、`adapter`、`planner`、`output`

## 七、验证与交付

- [ ] 用 1 个真实 brief 跑通最小闭环
- [ ] 验证 shortlist 结构是否满足 Agency 使用
- [x] 记录已知限制与风险
- [x] 形成 v1 handoff 说明

## 八、当前实际优先级

- [ ] P0：把 `Scweet` 变成可复用的 `Layer1` adapter，而不是继续停留在 probe
- [ ] P0：补 `query spec schema`、`execution plan schema`、`provider adapter contract`
- [x] P0：写 `SKILL.md` 初版，先打通单 provider 路线
- [ ] P0：把 `query spec / execution plan / provider contract` 收成单独 schema 文档
- [ ] P1：把 `Scweet user-info` 固化为当前默认 `Layer2` 主链路
- [x] P1：为 `Layer2` 增加免费版 `views gate`，避免默认补全全部候选人
- [ ] P1：接入 `ScrapeCreators` 作为 `Layer2 enhanced enrichment`
- [ ] P1：输出第一版 shortlist CSV / Markdown
- [ ] P2：再回头补 `twscrape / bird / XActions` 的扩展路线

## 九、当前判断

- 已完成的核心工作：调研、三层架构草案、`Scweet / twscrape / snscrape` 初轮测试、`Scweet` deep probe、`bird` 与 `last30days-skill` 的补充观察。
- 当前卡点不在“要不要继续研究”，而在“如何把已有最小闭环包装成稳定 skill，并把 schema 与扩展点写清楚”。
- 接下来的主线应从“继续比较 provider”切到“先固化 `Scweet search -> Scweet user-info -> shortlist -> S1 mapping`”，再逐步补 `ScrapeCreators enhanced enrichment`。
