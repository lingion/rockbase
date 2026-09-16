---
tags:
  - SocialAgency
  - Skills
  - X
  - KOLDiscovery
  - Spec
  - Layer1
  - FeasibilityTest
date: 2026-03-31
status: planning
---

# Spec-Layer1可行性测试方案

## 一、测试目的

本测试不是直接开发完整 skill，而是先回答一个更关键的问题：

**`Layer1` 里的候选工具，能不能真正支持“模糊搜索 X 上的目标 KOL”这件事。**

如果这一步不先验证，后面无论写多少 schema、adapter、router，都可能建立在错误假设上。

所以本阶段目标是：

- 验证 `Scweet / twscrape / snscrape / XActions / 官方 API / 其他参考工具` 的实际可用性
- 判断它们是否真的能完成本项目的 discovery 目标
- 识别哪些项目只是“看起来能搜”，哪些项目真能稳定产出候选 KOL
- 识别哪些项目底层原理相同，可以合并同类项
- 判断最终应采用：
  - 单一主 provider
  - 多 provider 并行
  - 多 provider 分层补充

## 二、测试主题

本轮统一测试主题固定为：

**找到英语区、粉丝量在 1000 以上、最近热门的 AI 科技类博主，最近谈到 OpenClaw 相关话题，而且有热帖发布。目标是最终找到 1000 个这样的博主。**

这条测试主题非常适合做 feasibility study，因为它同时覆盖了：

- `topic`：AI / OpenClaw / AI tech
- `language`：English
- `popularity`：有热帖
- `account size`：粉丝量 > 1000
- `recency`：最近在聊

如果某个工具在这个主题下完全跑不动，那它就很难成为 Layer1 的主力 provider。

## 三、核心测试问题

本阶段要回答的不是“工具能不能运行”，而是以下问题：

1. 它能否执行真正的 `topic fuzzy discovery`
2. 它能否限制 `language = English`
3. 它能否帮助找到“最近在谈 OpenClaw”的账号
4. 它能否支持“粉丝量 > 1000”的后续筛选
5. 它能否帮助发现“有热帖”的博主，而不只是返回零散推文
6. 它的结果是否适合进入 `Layer2`
7. 它与其他工具的原理是否重复
8. 它是否值得保留为独立 provider

## 四、测试对象

本轮建议优先测试这些对象：

### A 级：主测试对象

- `Scweet`
- `twscrape`
- `snscrape`

理由：

- 它们最接近真正的 `X fuzzy discovery engine`
- 都具备一定抓取和搜索能力
- 都有可能成为 `Layer1` 的主 provider 或低成本备选

### B 级：辅助测试对象

- `XActions`
- `官方 API`

理由：

- `XActions` 适合验证 agent 自动化抓取形态
- 官方 API 适合做“高可信搜索能力基准”

### C 级：参考测试对象

- `last30days-skill`
- `Sherlock`
- `Social Analyzer`
- `Maigret`
- `SpiderFoot`

理由：

- 它们更适合作为参考方法或辅助信号工具
- 不一定适合直接争夺主 provider 位
- 但有助于判断“是否应做交叉验证池”

## 五、测试流程

建议分五步走：

### Step 1：读项目与判原理

每个项目先做读码前的结构判断：

- 它是 API 驱动、网页抓取、浏览器自动化，还是多源 research flow
- 它的搜索入口是什么
- 它的输出粒度是 tweet、profile、还是 mixed results
- 它是否支持 topic / lang / recent / followers 这类约束

这一阶段主要做：

- 看首页 README
- 看安装方式
- 看核心 CLI / Python API
- 看关键搜索函数

目标不是马上运行，而是判断：

- 它属于哪一类 provider
- 它和其他项目是否原理重复

### Step 2：建立最小测试脚本

对每个 A 级、B 级测试对象建立最小测试脚本或命令样例，尽量统一输入：

- topic: `OpenClaw`
- broader topic: `AI`, `AI agents`, `automation`, `developer tools`
- language: `en`
- follower threshold: `1000+`
- recency: recent

这一步输出应该是：

- 可执行命令
- 必要参数
- 是否需要 cookies / token / browser state
- 预期输出结构

### Step 3：真实跑一次

对每个主测试对象跑真实测试，记录：

- 能否成功启动
- 能否返回结果
- 返回多少条候选
- 返回的是 tweet 还是 user 还是混合
- 是否含 language 线索
- 是否能支持后续筛粉
- 是否容易进入 `Layer2`

### Step 4：结果标准化

即使每个工具输出不同，也要先映射到统一评估表里：

```yaml
provider:
run_success:
result_type:
candidate_count:
query_support:
lang_support:
follower_support:
hot_post_signal:
integration_risk:
notes:
```

### Step 5：归纳与决策

最后不是比较“谁酷”，而是做架构决策：

- 哪个工具适合当默认 provider
- 哪个工具适合当 fallback
- 哪个工具适合做验证池
- 哪些工具底层原理高度相似，可以合并同类项
- 哪些工具虽然功能类似，但实现成熟度不同，不应轻易合并

## 六、如何判断“原理相同”

这是本阶段非常重要的一部分。

判断两个项目是否原理相同，建议看这几个点：

- 都是直接抓 X 前端网页 / GraphQL
- 都依赖 cookies / session
- 都从搜索页或 timeline 取结果
- 都主要输出 tweet / user records
- 都没有本质不同的数据源

如果五项高度重合，就说明它们可能只是：

- 封装层不同
- CLI 不同
- 维护质量不同

此时重点就不是“全留”，而是比较：

- 稳定性
- 文档质量
- 输出质量
- 易集成程度
- 社区活跃度

## 七、如何判断“不能轻易合并”

即使两个项目看起来都在抓 X，也不能太主观判断它们等价。

出现以下情况时，要保留它们的独立观察：

- 查询能力细节不同
- 返回粒度不同
- 有的更擅长 topic search，有的更擅长 profile expansion
- 有的更擅长 followers / replies / retweeters
- 有的在长期验证中更稳定
- 有的依赖浏览器态，有的依赖静态请求

所以测试阶段必须先“观察事实”，不能一上来就凭感觉合并。

## 八、评估维度

每个工具建议至少按以下维度打分：

|维度|说明|
|---|---|
|可启动性|是否容易安装与运行|
|可复现性|是否容易重复跑出稳定结果|
|topic 模糊发现能力|能否围绕 OpenClaw / AI 科技话题找到人|
|语言筛选能力|是否能支持英语区筛选|
|热门内容信号|能否帮助识别“有热帖”|
|粉丝筛选可行性|是否能获取或推断粉丝量|
|结果进入 Layer2 的适配度|能否无缝交给 ScrapeCreators / OmniChrome|
|扩展性|是否适合封装成 provider adapter|
|维护风险|是否容易失效、是否重依赖 cookies / session|

## 九、你需要提供什么

为了真正开始测试，你最好提供以下内容：

### 必需项

- 你希望优先测试的工具范围  
  建议默认：`Scweet / twscrape / snscrape / XActions`
- 你愿意先测试到什么深度  
  建议默认：先做“能不能找到候选人”的浅层测试

### 很可能需要

- 可用于测试的 X 账号 cookies / 登录态  
  尤其是 `Scweet / twscrape / XActions` 这类工具
- 如果你已经有代理方案，也建议说明
- 如果你有官方 API 权限，也可以作为基准测试一起加进来

### 可选项

- 你对 “热帖” 的定义  
  例如点赞、转推、回复、浏览量的哪一种阈值
- 你对 “最近” 的定义  
  例如 7 天、14 天、30 天
- 你对 “AI 科技类博主” 的更细定义  
  例如偏开发者、偏创业者、偏 AI 产品测评、偏研究者

## 十、是否需要把测试代码落到本地

答案是：**需要，而且应该落到 skill 自己的 `tests` 文件夹。**

原因：

- 这不是一次性的聊天分析
- 我们需要重复测试多个 provider
- 我们需要记录真实命令、输出、失败日志
- 我们需要比较多个项目的结果
- 后面还要复跑验证

所以本项目建议使用：

- `tests/scripts/`：放测试脚本
- `tests/results/`：放原始结果和标准化结果
- `tests/logs/`：放运行日志

## 十一、当前建议的测试顺序

建议顺序如下：

1. `Scweet`
2. `twscrape`
3. `snscrape`
4. `XActions`
5. `官方 API`
6. `last30days-skill` 与其他参考型工具

原因：

- 先验证最可能成为主 provider 的对象
- 再验证辅助层
- 最后再看参考工具是否值得纳入验证池

## 十一点五、测试阶段的多 Agent 策略

测试阶段也可以启用多 Agent，但建议遵守以下原则：

### 适合用子 Agent 并行做的事

- 并行阅读不同项目的 README、CLI、安装说明
- 并行梳理不同 provider 的运行前提
- 并行准备不同 provider 的最小测试命令
- 并行分析不同 provider 的输出结构和字段映射

### 不适合完全分散给子 Agent 的事

- 最终测试主题定义
- 统一成功标准
- 多 provider 的横向对比结论
- “是否合并同类项”的最终判断
- 回写主 Spec 的最终结论

这些应该由主线程统一收敛。

### 建议并行上限

- 每轮最多 `3` 个子 Agent

原因：

- 避免重复阅读同一类项目
- 避免比较标准漂移
- 便于主线程收敛

### 推荐分工方式

- Agent A：主候选组  
  `Scweet / twscrape / snscrape`
- Agent B：辅助与基准组  
  `XActions / X Search Posts / X Search Users`
- Agent C：参考与验证组  
  `last30days-skill / Sherlock / Social Analyzer / Maigret / SpiderFoot`

### 测试阶段的正确节奏

1. 先由主线程定义测试主题和判定标准
2. 子 Agent 并行学习和准备命令
3. 主线程统一决定先测谁
4. 真实运行时可按 provider 分批并行
5. 所有结果统一回写 `tests/results/` 和 Spec

## 十二、测试完成后的预期输出

本阶段完成后，至少应得到：

1. 一份 `Layer1 provider feasibility matrix`
2. 一份真实测试结果记录
3. 一个默认 provider 建议
4. 一个 fallback provider 建议
5. 一个“哪些工具保留、哪些工具仅作参考”的决策

如果这些输出完成，`Layer1` 的设计就会从“概念正确”升级到“可实施”。

## 十三、首轮实测归档

2026-03-31 的第一轮 P1 实测结果已归档在：

- `tests/results/2026-03-31-P1-provider-feasibility-summary.md`

后续每轮测试都建议延续同样的归档方式，便于纵向比较 provider 的真实表现。
