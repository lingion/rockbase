---
tags:
  - SocialAgency
  - X
  - KOLDiscovery
  - SkillDesign
  - Spec
date: 2026-03-31
status: done
---

# Spec-X模糊搜索KOL-Skill架构设计

来源说明：本报告基于已有文档 `docs/research/x-api-and-scraping-tools-summary.md`，并结合 2026-03-31 当日联网检索后的公开资料整理，目标是把本项目的 X KOL 模糊搜索能力重构成一个可执行的三层架构。

## 一、总判断

这件事的本质不是“找一个万能搜索 API”，而是把 `模糊找人` 拆成三层：

- `Layer1`：模糊发现层
- `Layer2`：补全与清洗层
- `Layer3`：评分与决策层

你现在已有的 `ScrapeCreators API` 很有价值，但它不适合作为发现层主引擎。  
它更适合放在 `Layer2`，做 profile、tweets、metadata 的补全与标准化。

所以这套 skill 最合理的主设计是：

- `Layer1` 负责低成本模糊抓取，不强依赖官方 API
- `Layer2` 当前执行版优先用 `Scweet user-info` 补全，但先做免费版 `views gate`；增强版再接 `ScrapeCreators`，抓不到再走 `OmniChrome`
- `Layer3` 负责国家、语言、话题、活跃度和推荐分的最终判断

一句话总结：

**Layer1 找人，Layer2 补数，Layer3 做决定。**

当前免费版补充原则：

- `Layer2` 不再默认对全部 `Layer1 candidates` 做 profile lookup
- 只有 `max_views >= 5000` 的账号，才进入当前默认 `Scweet user-info` 补全链路
- `max_views < 5000` 的账号保留在 `L1` / `L2 enriched` 中，但标记为 `views gate` 跳过
- 这样可以把免费抓取成本集中在更可能值得补数的账号上

## 二、三层架构

## 2.1 Layer1：模糊发现层

### 定位

`Layer1` 是数据入口层，负责从 X 上把“可能相关的人”先召回出来。

它解决的问题不是“准不准”，而是：

- 有没有足够多候选人
- 能不能按 topic / language / country / role 先做粗筛
- 成本能不能接受

### Layer1 的前置核心：自然语言需求转抓取计划

`Layer1` 不是一上来就调用 provider。  
它最前面必须先有一个“自然语言需求 -> 搜索规格 -> provider 抓取计划”的转换模块。

这是 `Layer1` 的前置核心，不是附属能力。

建议把它拆成三个子步骤：

#### A. Intent Parsing

把用户给出的一段自然语言需求拆成结构化约束，例如：

- topic
- country
- language
- role / bio hints
- exclude 条件
- 粉丝量区间
- 活跃度要求
- seed accounts

#### B. Query Spec Generation

把结构化约束整理成统一的 discovery spec，供后续所有 provider 共用。

统一 spec 示例：

```yaml
topic_query: "AI agents automation workflow"
country_include: ["US"]
language_include: ["en"]
bio_keywords: ["founder", "builder"]
must_keywords: ["AI agents"]
any_keywords: ["automation", "workflow"]
exclude_keywords: ["crypto", "trader"]
role_hints: ["founder", "builder"]
min_followers: 3000
max_followers: 300000
seed_accounts: []
result_limit: 100
```

#### C. Provider-specific Plan Compilation

在统一 spec 的基础上，再编译成不同 provider 可执行的抓取计划。

计划示例：

```yaml
plan:
  - provider: scweet
    mode: tweet_search
    search_terms: ["AI agents", "automation", "workflow"]
    language: "en"
    limit: 100

  - provider: scweet
    mode: profile_expansion
    bio_keywords: ["founder", "builder"]
    limit: 50

  - provider: twscrape
    mode: seed_expansion
    enabled_if: "candidate_count < 40"
```

这一段的准确定位可以写成：

**Natural Language Brief -> Discovery Query Spec -> Provider-specific Search Plan**

中文可以写成：

**自然语言需求解析为搜索规格，并进一步编排为 provider 级抓取计划。**

### Layer1 的内部结构

从执行顺序上，`Layer1` 更准确的内部结构应该是：

- `Layer1A: Intent Parsing`
- `Layer1B: Query Spec Generation`
- `Layer1C: Provider Execution`
- `Layer1D: Merge / Dedupe`

### 输入

- `topic_query`
- `country_include`
- `language_include`
- `bio_keywords`
- `exclude_keywords`
- `seed_accounts`
- `result_limit`

### 输出

- `candidate usernames`
- `candidate user ids`
- `matched tweets`
- `source query`
- `raw discovery signals`

### 推荐工具定位

#### A. Scweet

当前判断：**强候选发现层工具**。

原因：

- 支持 tweets 搜索
- 支持日期范围
- 支持 user / hashtag / engagement 条件
- 支持 `lang`
- 支持 `place / geocode`
- 支持 profile metadata
- 支持 followers / following
- 有 CLI，适合快速做 skill 原型

适合放在 `Layer1` 的场景：

- topic 模糊抓取
- recent 话题发现
- hashtag 扩展
- 基于 profile/followers 的二次扩展

限制：

- 本质仍然是 scraping
- 依赖 cookies / 登录态 / 限流控制
- `location` 不应直接当作国家真值

结论：

**如果你想尽快做出一个能跑的模糊发现层，Scweet 是目前最值得优先试的候选。**

#### B. twscrape

当前判断：**工程型发现层 / 关系扩展层候选**。

优点：

- 支持 search、user lookup、timeline、followers/following
- 支持更细粒度关系数据，如 retweeters、replies
- 自由度高，适合长期内部能力建设

限制：

- 更像低层采集引擎，不是现成业务工具
- 需要 cookie、代理、账号池治理
- 运维成本高于 `Scweet`

结论：

**它适合后续做深做强，不一定适合最先拿来做 V1 主链路。**

#### C. XActions

当前判断：**agent-friendly 辅助发现层**。

优点：

- 有 CLI、browser scripts、MCP server
- 支持 `searchTweets`、`scrapeHashtag`、`scrapeProfile`
- 支持 `scrapeFollowers`、`scrapeFollowing`
- 很适合 AI agent 调用和半自动化流程

限制：

- 更像自动化工具箱
- 标准化输出和稳定性还需要二次封装
- 不建议单独作为唯一发现层主引擎

结论：

**适合做 Layer1 的辅助入口，不建议单核依赖。**

#### D. last30days-skill

当前判断：**Layer1 的架构参考型工具**。

GitHub：

- `https://github.com/mvanhorn/last30days-skill`

为什么值得参考：

- 它不是单一 X 抓取器，而是一个多源 research skill
- 当前已经把 `X` 接入到自己的多源检索链路里
- README 明确写到 X 支持浏览器 cookies 方案，也支持句柄解析与近 30 天研究
- 它的整体思路不是“绑死一个 provider”，而是“多源搜索 + 打分 + 去重 + 汇总”

这对我们设计 `Layer1` 很有启发，因为它说明：

- discovery layer 可以不是单一工具
- provider 可以按配置动态启用
- cookies 可以作为 X 侧低成本入口
- 搜索结果应该进入统一的 score / dedupe / synthesize 流程

它不适合作为本项目的直接主引擎的原因：

- 目标偏“趋势研究 / 多平台研究”
- 不是专门为 X KOL discovery 设计
- 输出更偏 research summary，而不是 KOL shortlist

结论：

**它最适合放在 Layer1 的“架构参考工具”列表里，帮助我们设计 provider registry、routing、dedupe、multi-source merge。**

#### E. 官方 API

虽然 X 官方现在已经支持 `User Search` 和 `Post Search`，但在本项目里，我不建议把它定义成 `Layer1` 的默认主引擎。

原因：

- 成本偏高
- 发现层的灵活度不一定最优
- 更适合做高确定性补充，而不是最低成本大范围召回

结论：

**官方 API 可以保留为补充入口，但不作为当前默认发现层。**

### Layer1 潜在 Provider 选型表

下表把当前值得纳入 `Layer1` 视野的工具分成三类：

- `主候选`：可以直接考虑做 provider
- `辅助候选`：可作为补充抓取或 fallback
- `参考型工具`：更适合作为方法论参考，而不是直接主抓取器

|工具|链接|类别|是否需要 cookies / 登录态|是否依赖本地 bird CLI|是否支持 topic 搜索|是否支持 lang / country 条件|接入难度|适合角色|是否适合默认 provider|当前研究结论|测试优先级|
|---|---|---|---|---|---|---|---|---|---|---|---|
|Scweet|https://github.com/Altimis/Scweet|主候选|通常需要，核心是 `auth_token` + `ct0`|否|强|中，`lang` 强，`country/location` 需谨慎解释|中|主发现 provider|是，当前首选|最接近真正的 X 模糊搜索主引擎|P1|
|twscrape|https://github.com/vladkens/twscrape|主候选|需要，可用 cookies 或已授权账号|否|强|中，更多依赖自定义查询与后处理|中高|工程型 provider、关系扩展 provider|可作为第二主选|更强的工程化采集引擎，适合第二主选|P1|
|bird CLI|https://github.com/steipete/bird|辅助候选|需要 `AUTH_TOKEN` + `CT0` 或浏览器 profile|是，本体|强|中，topic 搜索强；lang 可经 query 表达；country 仍偏后处理|中|原生 X GraphQL CLI / 高价值参考 provider|可作为参考，不建议先于 Scweet 做默认主引擎|本地已实测通过 `whoami` 与 `search`，值得继续探索|P2|
|XActions|https://github.com/nirholas/XActions|辅助候选|通常需要浏览器态 / 本地 session|否|中|弱到中，偏动作脚本化|中|辅助 provider / 半自动 provider / 浏览器态 fallback|否|更适合 agent 自动化和浏览器态 fallback|P2|
|X Search Posts|https://docs.x.com/x-api/posts/search/introduction|辅助候选|不需要 cookies，但需要 API 权限|否|强|强，原生支持 `lang:` 与 `place_country:`|中|高可信 topic provider|否，成本偏高|高可信 topic/lang/country 补充 provider|P2|
|X Search Users|https://docs.x.com/x-api/users/search-users|辅助候选|不需要 cookies，但需要 API 权限|否|弱到中，偏 bio/name 搜索|弱到中，需依赖 `location` 等字段推断|中|bio/name 召回补充 provider|否|适合 bio/name 召回，不适合单独承担 KOL 发现|P3|
|last30days-skill|https://github.com/mvanhorn/last30days-skill|参考型工具|支持 cookies 路线|部分，主要是内置/捆绑 Bird 能力|中|弱到中，更偏 research flow 后处理|中|架构参考工具 / handle resolution 参考|否|方法论参考价值高，不建议直接当主 provider|P3|
|Sherlock|https://github.com/sherlock-project/sherlock|参考型工具|不需要|否|弱，不适合 topic 搜索|弱|低|username pivot provider / 交叉验证工具|否|适合已知用户名交叉验证，不适合 topic discovery|P4|
|Social Analyzer|https://github.com/qeeqbox/social-analyzer|参考型工具|通常不强依赖官方 API|否|弱到中，更偏 profile 查找|弱|中|cross-platform profile finder|否|适合 cross-platform profile 扩展，不适合主 provider|P4|
|Maigret|https://github.com/soxoj/maigret|参考型工具|不需要|否|弱，不适合 topic 搜索|弱|低|username dossier provider|否|适合 identity mapping / dossier，不适合 topic discovery|P4|
|SpiderFoot|https://github.com/smicallef/spiderfoot|参考型工具|视模块而定|否|弱|弱|中高|OSINT enrichment / auxiliary signal collector|否|适合辅助 enrichment，不适合主 provider|P4|
|snscrape|https://github.com/JustAnotherArchivist/snscrape|辅助候选|通常不需要|否|中到强|弱到中，语言可做后处理，国家需二次推断|低中|轻量补充 provider|可作为低成本备选|低成本补位方案，适合并行对比|P1|

### 选型解读

- `默认 provider` 最适合优先考虑：`Scweet`
- `第二主选 / 工程加强版`：`twscrape`
- `低成本补位`：`snscrape`
- `高可信补充`：`X Search Posts / X Search Users`
- `辅助自动化入口`：`XActions`
- `方法论参考与交叉验证池`：`last30days-skill`、`Sherlock`、`Social Analyzer`、`Maigret`、`SpiderFoot`

### 对这些通用 OSINT 工具的判断

这批工具里，真正更接近 `X Layer1 provider` 的，仍然是：

- `Scweet`
- `twscrape`
- `snscrape`
- `X Search Posts / X Search Users`

而以下几类更适合放在 `Layer1` 的参考池或辅助池：

- `Sherlock`
- `Social Analyzer`
- `Maigret`
- `SpiderFoot`
- `last30days-skill`

原因不是它们没价值，而是它们更偏：

- username pivot
- cross-platform identity mapping
- account existence verification
- multi-source OSINT aggregation

这些能力对我们很有帮助，但更像：

- 候选账号交叉验证器
- 身份归并器
- 辅助发现器

而不是最直接的 `X topic/lang/country fuzzy discovery engine`。

### Layer1 设计结论

当前最合理的设计是：

- 主入口：`Scweet`
- 备用入口：`twscrape`
- 辅助入口：`XActions`
- 架构参考：`last30days-skill`
- 补充入口：`官方 API` 或第三方 actor

也就是说：

**Layer1 = 非官方优先的模糊发现层。**

### Layer1 的模块化与热插拔设计

`Layer1` 不应该被写死成某几个工具名，而应该是一个半开放、可插拔的 discovery framework。

更准确地说，它应该由四部分组成：

#### A. Provider Interface

所有发现层工具都必须适配统一输入输出协议。

统一输入示意：

```yaml
topic_query:
country_include:
language_include:
bio_keywords:
exclude_keywords:
seed_accounts:
result_limit:
```

统一输出示意：

```yaml
provider:
username:
user_id:
matched_text:
matched_reason:
source_query:
raw_signals:
```

#### B. Provider Registry

当前 registry 可先包含：

- `provider_scweet`
- `provider_twscrape`
- `provider_xactions`
- `provider_last30days_reference`
- `provider_official_api`
- `provider_future_xxx`

后续如果你再给新工具，我们不改总架构，只新增一个 provider adapter。

#### C. Routing Strategy

需要定义：

- 默认先跑哪个 provider
- 哪些 provider 可并行
- 哪些 provider 仅在 fallback 时启用
- 哪些 provider 成本高，需要显式开启

#### D. Merge / Dedupe Strategy

多 provider 输出后，统一做：

- username / user id 去重
- query 来源记录
- matched signals 合并
- provider source 保留

这一步会直接影响 `Layer3` 的评分质量。

## 2.2 Layer2：补全与清洗层

### 定位

`Layer2` 不负责“找人”，它负责把 `Layer1` 找回来的候选账号补全成可判断的数据对象。

它的职责包括：

- profile enrichment
- tweets enrichment
- metadata normalization
- contact signal extraction
- fallback 抓取

### 默认主链路

`Layer2` 在理想版设计里，默认主工具应该是：

- `ScrapeCreators /v1/twitter/profile`
- `ScrapeCreators /v1/twitter/user-tweets`

原因：

- 你已经有现成 API
- 调用成本和接入心智都更低
- 对已知 handle 的资料补全非常适合
- 适合做统一字段输出

但从当前执行节奏和成本控制看，建议区分“理想版主链路”和“当前执行版主链路”：

- 理想版默认：`ScrapeCreators`
- 当前执行版默认：`Scweet user-info`
- 增强补全：`ScrapeCreators`
- 失败 fallback：`OmniChrome`

这样做的原因是：

- `Scweet user-info` 不消耗 `ScrapeCreators` credits
- 它和 `Layer1` 的 `Scweet search` 天然衔接
- 已经足够补全 `bio / location_raw / followers_count / following_count / statuses_count / verified`
- 可以先支撑 v0/v1 的 shortlist 判断，再把更昂贵的 enrichment 留给增强阶段

### fallback 机制

当 `ScrapeCreators` 抓不到、字段缺失、结构异常时，fallback 应该走：

- `OmniChrome`

在这里，`OmniChrome` 的定位不是常规主链路，而是：

- DOM 级补抓器
- 失败兜底器
- 人工可审计浏览器抓取器

适合补的内容：

- bio / location / pinned tweet
- 外链
- 联系方式线索
- 页面上已展示但 API 没回来的字段

### Layer2 输入

- `username`
- `user id`
- `sample tweets`
- `discovery metadata`

### Layer2 输出

- `bio`
- `location_raw`
- `followers_count`
- `following_count`
- `tweet_count`
- `verified`
- `recent_tweets`
- `external_links`
- `contact_signals`
- `normalized profile object`

### Layer2 设计结论

这一层不需要太花哨，核心是稳定和统一：

- 当前执行版默认：`Scweet user-info`
- 增强补全：`ScrapeCreators`
- fallback：`OmniChrome`
- 输出：标准化 profile + tweets data object

也就是说：

**Layer2 = enrichment + normalization layer。**

## 2.3 Layer3：评分与决策层

### 定位

`Layer3` 是最终把“候选人”变成“可执行 shortlist”的地方。

它不是抓取层，而是判断层。

### 要解决的问题

- 这个人是不是我们要找的话题型 KOL
- 国家是不是匹配
- 语言是不是匹配
- 粉丝量是否在合适区间
- 内容是否真实在聊这个主题
- 活跃度是否足够
- 是否值得进入 handoff / outreach

### 核心评分维度

#### A. 话题匹配

建议拆成：

- `must_keywords`
- `any_keywords`
- `exclude_keywords`

信号来源：

- bio
- recent tweets
- pinned tweet
- external links

输出字段：

- `topic_match_score`
- `matched_signals`

#### B. 国家判断

国家不能只靠一个字段，建议多信号合并：

- `location_raw`
- bio 中的国家/城市词
- 最近帖子里的自述地点
- 主页链接国家后缀
- 时间分布推断时区

输出字段：

- `country_inferred`
- `country_confidence`
- `country_signals`

#### C. 语言判断

语言建议基于最近 N 条 tweets 做统计，而不是只看单条搜索结果：

- `primary_language`
- `language_mix`
- `language_confidence`

#### D. 账号质量

建议至少包含：

- `followers_count`
- `following_count`
- `tweet_count`
- `recent_post_count`
- `activity_score`

#### E. 最终推荐分

最终输出建议统一成：

- `profile_match_score`
- `topic_match_score`
- `activity_score`
- `overall_score`
- `recommended_action`

其中 `recommended_action` 可取：

- `keep`
- `review`
- `drop`

### Layer3 输出

- shortlist
- review table
- outreach candidate table
- audit summary

### Layer3 设计结论

这一层决定这套 skill 是否真正能服务 agency 执行。

也就是说：

**Layer3 = scoring + ranking + selection layer。**

## 三、推荐的数据流

整条链路建议定义成：

1. `Layer1` 用模糊条件抓候选账号
2. 候选账号进入 `Layer2`
3. `Layer2` 先用 `Scweet user-info` 补基础 profile
4. 需要增强字段时再用 `ScrapeCreators` 补 profile / tweets
5. 缺失字段用 `OmniChrome` fallback
6. 补全后的标准化对象进入 `Layer3`
7. `Layer3` 输出 shortlist 和评分表

如果要更简洁地表达：

- `Layer1`：召回
- `Layer2`：补全
- `Layer3`：决策

### 运行产物保留协议

这条链路不应只保留最终表，而应把每一层过程产物都保留下来。

正式规则：

- 所有运行产物统一写入 `workbench/{YYYY-MM-DD}/`
- 同一天允许存在多个批次
- 每个批次都要保留完整链路：
  - `L1 CSV`
  - `L2 CSV`
  - `L3 CSV`
  - `L3 -> S1 Inbox CSV`
- 文件名必须带 `batch` 编号

建议命名模式：

- `x_kol_L1_candidates_batch1_{YYYY-MM-DD}.csv`
- `x_kol_L2_enriched_batch1_{YYYY-MM-DD}.csv`
- `x_kol_L3_shortlist_batch1_{YYYY-MM-DD}.csv`
- `x_kol_S1_inbox_batch1_{YYYY-MM-DD}.csv`

这样做的原因是：

- 一天可能会跑多批不同 topic / 不同策略
- 每批都需要完整回溯
- 后续复盘、比较、重跑时不应覆盖上一批产物

## 四、当前最推荐的落地方案

### 方案 A：当前主推荐

- `Layer1 = Scweet`
- `Layer2 = Scweet user-info -> ScrapeCreators enhanced enrichment -> OmniChrome fallback`
- `Layer3 = 本地评分脚本`

这是当前最符合你思路、也最容易快速成型的方案。

### 方案 B：后续增强

- `Layer1 = Scweet + twscrape + XActions`
- `Layer2 = ScrapeCreators + OmniChrome`
- `Layer3 = 规则评分 + seed 扩展 + 关系扩展`

这是后续把系统做强的方向，但不需要第一天就上。

## 五、这份 skill 的建议输入输出

### 输入参数

```yaml
platform: x
topic_query: "AI agents"
country_include: ["US", "GB"]
language_include: ["en"]
bio_keywords: ["founder", "builder", "researcher"]
exclude_keywords: ["crypto", "trader", "airdrop"]
min_followers: 3000
max_followers: 300000
min_recent_posts: 5
min_topic_match_posts: 2
seed_accounts: []
result_limit: 100
```

### 输出字段

```yaml
username:
display_name:
bio:
location_raw:
country_inferred:
country_confidence:
primary_language:
language_mix:
followers_count:
following_count:
tweet_count:
verified:
topic_match_score:
profile_match_score:
activity_score:
overall_score:
matched_signals:
sample_posts:
profile_url:
source_method:
recommended_action:
```

## 六、为什么这个结构比“找一个官方 API”更对

因为本项目的真实目标不是“调通一个接口”，而是：

- 能稳定找到人
- 能补全成可判断对象
- 能输出 agency 可执行的 shortlist

而这三件事，本来就不是一个工具能完成的。

所以最合理的设计不是单点工具设计，而是：

- 把模糊搜索交给 `Layer1`
- 把资料补全交给 `Layer2`
- 把业务判断交给 `Layer3`

## 七、下一步建议

如果继续往执行走，我建议直接产出两样东西：

1. `X-KOL-Fuzzy-Discovery` skill 的 `SKILL.md`
2. 一个最小可运行脚本：
   - 接收 `topic / country / language`
   - 走 `Layer1`
   - 用 `Layer2` 补全
   - 输出 `Layer3` 的 CSV shortlist

## 八、建议目录结构

为了把当前的测试脚本逐步升级成正式 skill，建议目录结构收口为：

```text
S1-inbox-kol-fuzzy-discovery-x-skill/
├── SKILL.md
├── README.md
├── docs/TODO-skill开发清单.md
├── docs/Spec-X模糊搜索KOL-Skill架构设计.md
├── docs/
│   ├── plan.md
│   ├── layer1-feasibility.md
│   ├── research/
│   │   ├── osint-summary.md
│   │   └── x-api-and-scraping-tools-summary.md
│   ├── schemas/
│   │   ├── query_spec.schema.json
│   │   ├── execution_plan.schema.json
│   │   ├── layer1_candidate.schema.json
│   │   ├── layer2_enriched_profile.schema.json
│   │   └── layer3_shortlist_record.schema.json
│   └── decisions/
│       ├── provider-selection.md
│       └── known-limitations.md
├── src/
│   └── x_kol_discovery/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── io_utils.py
│       ├── layer1/
│       │   ├── __init__.py
│       │   ├── queries.py
│       │   ├── scweet_adapter.py
│       │   ├── normalize.py
│       │   └── dedupe.py
│       ├── layer2/
│       │   ├── __init__.py
│       │   ├── enrichment.py
│       │   ├── scrapecreators_client.py
│       │   └── README.md
│       ├── layer3/
│       │   ├── __init__.py
│       │   ├── ranking.py
│       │   └── README.md
│       ├── pipelines/
│       │   ├── check_scrapecreators_setup.py
│       │   ├── run_layer1_mvp.py
│       │   ├── run_layer2_from_candidates.py
│       │   └── run_full_pipeline.py
│       └── outputs/
│           └── __init__.py
├── tests/
│   ├── README.md
│   ├── .env.layer1.local
│   ├── scripts/
│   ├── results/
│   ├── logs/
│   └── vendor/
└── examples/
    ├── brief_openclaw_en.yaml
    └── brief_openclaw_minimal.json
```

当前建议的职责分工：

- `docs/`：承接计划、架构、research、schema、决策记录。
- `src/`：承接正式可运行代码。
- `tests/`：继续作为 provider probe、验证脚本、vendor 参考池。
- `examples/`：承接真实 brief 样例。

其中：

- `Layer1` 先做成真的可运行。
- `Layer2` 与 `Layer3` 先留接口与占位，不做假实现。
- `workbench/{YYYY-MM-DD}/` 继续只存运行产物，不存正式逻辑代码。
- 所有运行产物默认按 `batch1 / batch2 / batch3 ...` 编号，不覆盖前一批结果。

## 九、信源与校验日期

校验日期：**2026-03-31**

主要信源：

- ScrapeCreators 文档首页  
  https://docs.scrapecreators.com/
- ScrapeCreators Twitter Profile  
  https://docs.scrapecreators.com/v1/twitter/profile/
- Scweet GitHub  
  https://github.com/Altimis/Scweet
- twscrape GitHub  
  https://github.com/vladkens/twscrape
- XActions GitHub  
  https://github.com/nirholas/XActions
- last30days-skill GitHub  
  https://github.com/mvanhorn/last30days-skill
- X User Search  
  https://docs.x.com/x-api/users/search-users
- X Post Search  
  https://docs.x.com/x-api/posts/search/introduction
