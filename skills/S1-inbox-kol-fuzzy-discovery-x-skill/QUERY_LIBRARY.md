# Query Keyword Matrix Library

用于沉淀 `S1-inbox-kol-fuzzy-discovery-x-skill` 的 query 方法论与历史关键词资产。

---

## Part 1. 基本原则与方法

### 1.1 目标

这个 library 不是单次 runlog 归档，而是一个可持续更新的 `query 关键词矩阵`：

- 上半部分沉淀方法论
- 下半部分按主题词持续累计历史 query 记录
- 新 campaign 可以直接复用结构，只替换核心关键词

### 1.2 Query 设计原则

每条 query 建议由 3 层组成：

```text
"核心关键词" + 意图包 + 排除词
```

标准模板：

```text
"{TOPIC}" ({KEYWORDS}) -{NEG_1} -{NEG_2} -{NEG_3}
```

### 1.3 什么叫“合理的关键词数量”

如果目标是：

- `5` 组
- 每组 `6` 个 query

那本质上不是要准备 `30` 个完全不同的词，而是要准备：

1. `1` 个核心 topic
2. `5` 组搜索角度
3. 每组约 `4-6` 个关键词

因此更合理的准备量通常是：

- `1` 个核心品牌词
- `20-30` 个功能性关键词
- `3-8` 个排除词

也就是总共大约：

- `24-39` 个可复用关键词单元`

但真正执行时，建议优先控制在：

- `5` 个角度包
- 每包 `4-5` 个词

这样通常已经足够覆盖一轮 discovery。

### 1.4 综合方案：全球英语区 AI 热门博主 Query Matrix

目标：

- 找全球范围内英语区 AI 博主
- 尽量偏热门、偏有传播力、偏有商务转化价值
- 尽量减少搜出泛创业、泛独立开发、非 AI 圈账号

核心原则：

- 不要把泛词当核心词
- `shipping / building / maker / stack` 这类词不能单独作为核心搜索组
- 真正的核心词必须先锁定 `AI`
- 之后再叠加“人群词”与“内容词”

推荐用三层结构设计 query：

| Layer | 作用 | 典型词 |
| --- | --- | --- |
| `AI Lock` | 锁定 AI 赛道，避免跑偏 | `AI`, `LLM`, `AI tools`, `AI agents`, `generative AI`, `AI automation`, `AI coding` |
| `Creator Intent` | 锁定你想找的博主类型 | `builder`, `founder`, `engineer`, `creator`, `tutorial`, `review`, `demo`, `walkthrough`, `comparison` |
| `Expansion Signal` | 补充“正在使用 / 正在讨论 / 正在比较” | `workflow`, `use case`, `tested`, `trying`, `thoughts`, `vs`, `alternative`, `stack` |

推荐的 5 组主搜索角度：

| Query Group | 组合逻辑 | 用途 |
| --- | --- | --- |
| `AI Core` | `核心词 + AI Lock` | 起盘，找泛 AI 讨论人群 |
| `AI Workflow` | `核心词 + AI Lock + workflow/use case` | 找真实应用场景用户 |
| `AI Builder` | `核心词 + AI Lock + builder/founder/engineer` | 找偏实操、偏 build in public 的账号 |
| `AI Content` | `核心词 + AI Lock + tutorial/review/demo` | 找有内容产能的创作者 |
| `AI Compare` | `核心词 + AI Lock + compare/vs/alternative/tested` | 找有购买决策影响力的人 |

建议的关键词矩阵，适用于“全球英语区 AI 热门博主”：

| Query Group | 建议关键词 |
| --- | --- |
| `AI Core` | `AI`, `LLM`, `AI tools`, `generative AI`, `AI agents` |
| `AI Workflow` | `AI workflow`, `AI automation`, `use case`, `AI coding`, `AI research` |
| `AI Builder` | `builder`, `founder`, `engineer`, `researcher`, `creator` |
| `AI Content` | `tutorial`, `review`, `demo`, `walkthrough`, `comparison` |
| `AI Compare` | `compare`, `vs`, `alternative`, `tested`, `thoughts` |

补充说明：

- `shipping`, `building`, `shipped`, `maker`, `stack` 不建议作为核心组单独使用
- 这些词只能作为 `Expansion Signal`，并且必须和 `AI Lock` 词同时出现
- 否则很容易搜出大量非 AI 账号

如果今天把核心词换成 `Claude`，建议优先准备：

- 核心品牌词：`1` 个，即 `Claude`
- `AI Lock` 词：`5-7` 个
- `Creator Intent` 词：`8-10` 个
- `Expansion Signal` 词：`6-8` 个
- 排除词：`3-5` 个

这个规模基本就足够支撑：

- `5` 组主搜索角度
- 每组 `4-6` 个可组合关键词

### 1.5 当前推荐排除词管理

默认排除词要单独管理，不要混入主关键词池。

| Topic Type | Suggested Negative Keywords |
| --- | --- |
| AI tools / devtools | `crypto`, `trader`, `airdrop` |
| Claude / LLM | 可先沿用 `crypto`, `trader`, `airdrop`，后续视噪音再补 |

### 1.6 维护规则

- 每次正式跑过的 query，都应追加到 Part 2
- 每次准备执行新的 `Query Name` 时，必须先把该 `Query Name` 写进 Part 2，再生成 spec / allocation / todo
- 新 `Query Name` 不允许先写进 spec 再补 library；正确顺序是 `QUERY_LIBRARY -> spec -> batch run`
- 同一主题词可以多次追加新记录
- 若有新的有效经验，优先回写到 Part 1
- Part 1 只保留原则，不堆 runlog 细节
- Part 2 只保留真实跑过的 query 历史

---

## Part 2. Query Keyword History Library

说明：

- Part 2 只记录真实执行过的历史 query
- 不再重复承载方法论
- 后续从 `OpenClaw`、`Claude` 到更多主题词，持续往下追加

本区只记录真实执行过的 query 拆解。

### 2.2.1 `OpenClaw`

| Date | Query Name | Query Text | Provider | Batch | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-01` | `topic_core` | `"OpenClaw" (AI OR AI agents OR automation OR developer tools) -crypto -trader -airdrop` | `scweet` | `batch1probe` | `100` | default pack |
| `2026-04-01` | `topic_workflow` | `"OpenClaw" (workflow OR productivity OR coding OR devtools OR build) -crypto -trader -airdrop` | `scweet` | `batch1probe` | `98` | default pack |
| `2026-04-01` | `topic_roles` | `"OpenClaw" (builder OR founder OR engineer OR researcher OR creator) -crypto -trader -airdrop` | `scweet` | `batch1probe` | `95` | default pack |
| `2026-04-01` | `topic_content` | `"OpenClaw" (tutorial OR demo OR review OR usecase OR walkthrough) -crypto -trader -airdrop` | `scweet` | `batch1probe` | `91` | default pack |
| `2026-04-01` | `topic_product` | `"OpenClaw" (startup OR SaaS OR product OR team OR launch) -crypto -trader -airdrop` | `scweet` | `batch2` | `97` | default pack |
| `2026-04-01` | `topic_agentic` | `"OpenClaw" (agentic OR copilot OR copilots OR assistant OR assistants OR operators) -crypto -trader -airdrop` | `scweet` | `batch2` | `95` | default pack |
| `2026-04-01` | `topic_stack` | `"OpenClaw" (cursor OR claude OR gpt OR terminal OR ide) -crypto -trader -airdrop` | `scweet` | `batch3` | `96` | alt pack |
| `2026-04-01` | `topic_shipping` | `"OpenClaw" (shipping OR shipped OR building OR maker OR stack) -crypto -trader -airdrop` | `scweet` | `batch3` | `98` | alt pack |
| `2026-04-01` | `topic_discourse` | `"OpenClaw" (thoughts OR trying OR tested OR thread OR discussion) -crypto -trader -airdrop` | `scweet` | `batch3` | `93` | alt pack |
| `2026-04-01` | `topic_install` | `"OpenClaw" (install OR setup OR guide OR github OR repo)` | `bird_cli` | `batch4_bird` | `40` | bird exploration |
| `2026-04-01` | `topic_compare` | `"OpenClaw" ("vs" OR compare OR comparison OR alternative OR competitor)` | `bird_cli` | `batch4_bird` | `40` | bird exploration |
| `2026-04-01` | `topic_usage` | `"OpenClaw" (browser OR desktop OR automation OR agent OR workflow)` | `bird_cli` | `batch4_bird` | `40` | bird exploration |
| `2026-04-01` | `topic_feedback` | `"OpenClaw" (feedback OR experience OR trying OR tested OR thoughts)` | `bird_cli` | `batch4_bird` | `40` | bird exploration |

### 2.2.2 `Claude`

定位：

- 今日建议主 topic 先用 `Claude`
- 目标是优先做大盘 discovery，服务 `200` 个英语区 AI 热门博主候选池
- `Claude Code` 暂不单独拆成主 topic，先作为部分扩展词混入 `Claude` 组里

执行建议：

- 今天先用 `Claude`
- 明天如需继续细筛 dev / coding / terminal 人群，再单开 `Claude Code`
- 今天的 `Claude` 矩阵以“AI锁定词 + 扩展层”为核心

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Core` | `topic_core` | `"Claude" (AI OR LLM OR "AI tools" OR "generative AI" OR Anthropic) -crypto -trader -airdrop` | 起盘，找泛 AI 讨论人群 |
| `Workflow` | `topic_workflow` | `"Claude" ("AI workflow" OR "AI automation" OR "use case" OR productivity OR research) -crypto -trader -airdrop` | 找真实使用场景用户 |
| `Builder` | `topic_roles` | `"Claude" (builder OR founder OR engineer OR researcher OR creator) (AI OR LLM OR automation) -crypto -trader -airdrop` | 找 builder / founder / engineer 型账号 |
| `Content` | `topic_content` | `"Claude" (tutorial OR review OR demo OR walkthrough OR comparison) (AI OR LLM OR assistant) -crypto -trader -airdrop` | 找会产出内容的博主 |
| `Compare` | `topic_compare` | `"Claude" (compare OR comparison OR \"vs\" OR alternative OR competitor) (AI OR LLM OR chatbot) -crypto -trader -airdrop` | 找有购买决策影响力的人 |
| `Discussion` | `topic_discourse` | `"Claude" (thoughts OR tested OR trying OR thread OR discussion) (AI OR LLM OR assistant) -crypto -trader -airdrop` | 找观点型、讨论型账号 |
| `Coding` | `topic_coding` | `"Claude" ("AI coding" OR "developer tools" OR terminal OR IDE OR "Claude Code") -crypto -trader -airdrop` | 给今天的主 topic 补 dev / coding 人群 |
| `Writing` | `topic_writing` | `"Claude" (writing OR essays OR content OR copywriting OR summarization) (AI OR assistant OR productivity) -crypto -trader -airdrop` | 找偏写作和知识工作流人群 |
| `Prompting` | `topic_prompting` | `"Claude" (prompts OR prompting OR prompt-engineering OR jailbreak OR system prompt) (AI OR LLM) -crypto -trader -airdrop` | 找高活跃 prompt / power user 人群 |
| `Tools Stack` | `topic_stack` | `"Claude" (ChatGPT OR Cursor OR Perplexity OR Midjourney OR "Claude Code") -crypto -trader -airdrop` | 找会公开比较 AI 工具栈的人 |

建议分配方式：

- `Cookie 1 / Run 1`: `topic_core`, `topic_workflow`, `topic_roles`, `topic_content`, `topic_compare`
- `Cookie 1 / Run 2`: `topic_discourse`, `topic_coding`, `topic_writing`, `topic_prompting`, `topic_stack`
- `Cookie 1 / Run 3`: 从以上 10 条里挑表现最好的 `5-6` 条复跑或变体
- `Cookie 2 / Run 1`: 补第一轮未覆盖的强 query
- `Cookie 2 / Run 2`: 重点补 `coding / compare / content`
- `Cookie 2 / Run 3`: 补低重合、高增量 query

备注：

- 这是今天可执行的 planned matrix，不是历史 runlog
- 等今天实际执行后，可把结果回填到本节，增加 `Date / Provider / Batch / Result Count`
- 如后续单独开 `Claude Code`，建议新建 `2.2.3 Claude Code`
- `2026-04-02` intake 已确认：`X | en | 5000+ views | 1000+ followers | 过去 7 天 | Claude | 2 cookies, 每个 3 次`
- `2026-04-02` 默认执行边界：先按上面 `10` 条 planned matrix 拆到 `6` 个 runs，不在 intake 阶段新增 topic，避免 query 面铺得过宽
- `2026-04-08` Batch 1 override：用户指定用 Claude 最新模型词 `Mythos`；执行时保留 `topic_core`, `topic_workflow`, `topic_content` 这三个已落库 Query Names，但 query text 增加 `Mythos`，并用官方最新模型词 `Claude Opus 4.6` / `Claude Sonnet 4.6` 做兜底，避免单一别名搜偏。

2026-04-08 Batch 1 planned override:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Core` | `topic_core` | `("Claude Mythos" OR Mythos OR "Claude Opus 4.6" OR "Claude Sonnet 4.6") (AI OR LLM OR "AI tools" OR Anthropic) -crypto -trader -airdrop` | 用用户指定最新模型词起盘，同时保留官方最新模型兜底 |
| `Workflow` | `topic_workflow` | `("Claude Mythos" OR Mythos OR "Claude Opus 4.6" OR "Claude Sonnet 4.6") ("AI workflow" OR "AI automation" OR "use case" OR productivity OR research) -crypto -trader -airdrop` | 找最新模型相关的真实使用场景和工作流用户 |
| `Content` | `topic_content` | `("Claude Mythos" OR Mythos OR "Claude Opus 4.6" OR "Claude Sonnet 4.6") (tutorial OR review OR demo OR walkthrough OR comparison) (AI OR LLM OR assistant) -crypto -trader -airdrop` | 找围绕最新模型做教程、评测、对比的内容型账号 |

### 2.2.3 `Claude Code`

定位：

- 今日建议把主 topic 从泛 `Claude` 收窄到 `Claude Code`
- 目标是优先找英语区、近 `7` 天内在 `X` 上发布过 `Claude Code` 相关热帖的 KOL
- 相比 `Claude`，`Claude Code` 更偏开发者、agent workflow、terminal-native builder、人机协作效率流
- 这批更适合开发者工具、automation、agent infra、MCP、AI coding workflow 类商单

执行建议：

- 今天采用 `2 cookies x 3 batches` 的运行上限
- 但不把 `6` 个 batch 都视为必须跑完，而是把它们看作 `6` 个独立运行窗口
- 先跑 `4` 个核心 batch，重点观察：
  - `query relevance`
  - `overlap ratio`
  - `net-new handle yield`
  - `cookie stability`
- 若前 `4` 批后已拿到足够的 `L2 eligible` 和 `L3 shortlist`，则第 `6` 批可不启用
- 若 coding / stack / MCP 类 query 出现高相关低重合，则优先消耗第 `5` 批，而不是扩新 topic

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Core` | `cc_core` | `"Claude Code" ("AI coding" OR coding OR developer OR engineering OR terminal) -crypto -trader -airdrop` | 起盘，锁定真正讨论 Claude Code 的开发者与重度用户 |
| `Builder` | `cc_builder` | `"Claude Code" (builder OR founder OR engineer OR researcher OR creator) -crypto -trader -airdrop` | 找 builder / founder / engineer 型账号 |
| `Workflow` | `cc_workflow` | `"Claude Code" (workflow OR automation OR "use case" OR productivity OR systems) -crypto -trader -airdrop` | 找真实应用场景用户 |
| `Tutorial` | `cc_tutorial` | `"Claude Code" (tutorial OR walkthrough OR guide OR demo OR setup) -crypto -trader -airdrop` | 找能做内容交付的教程型 KOL |
| `Stack` | `cc_stack` | `"Claude Code" (Cursor OR Codex OR Cline OR Warp OR IDE OR terminal) -crypto -trader -airdrop` | 找公开比较 AI coding 工具栈的人 |
| `Compare` | `cc_compare` | `"Claude Code" (compare OR comparison OR "vs" OR alternative OR competitor) -crypto -trader -airdrop` | 找决策型、购买影响型账号 |
| `MCP` | `cc_mcp` | `"Claude Code" (MCP OR "Model Context Protocol" OR tools OR connectors OR server) -crypto -trader -airdrop` | 找 infra / ecosystem / advanced workflow 账号 |
| `Commands` | `cc_commands` | `"Claude Code" (slash commands OR "/plan" OR "/review" OR "/loop" OR commands) -crypto -trader -airdrop` | 找 power user 和实操流玩家 |
| `Agentic` | `cc_agentic` | `"Claude Code" (agents OR agentic OR multi-agent OR orchestration OR worktree) -crypto -trader -airdrop` | 找偏 agent workflow 和并行协作的人 |
| `Shipping` | `cc_shipping` | `"Claude Code" (shipping OR shipped OR building OR launch OR deployed) -crypto -trader -airdrop` | 找 build-in-public 与实战交付型账号 |
| `Prompting` | `cc_prompting` | `"Claude Code" (prompt OR prompting OR spec OR instructions OR system) -crypto -trader -airdrop` | 找 prompt/spec/workflow 设计型账号 |
| `Review` | `cc_review` | `"Claude Code" (review OR benchmark OR tested OR experiment OR thoughts) -crypto -trader -airdrop` | 找评测和观点型账号 |

建议 batch 分配：

- `Cookie 1 / Batch 1`:
  - `cc_core`
  - `cc_builder`
  - `cc_workflow`
- `Cookie 1 / Batch 2`:
  - `cc_tutorial`
  - `cc_shipping`
  - `cc_review`
- `Cookie 1 / Batch 3`:
  - 从前 `6` 条里挑 `2-3` 条低重合高表现 query 做复跑
  - 若 cookie 不稳，则把该窗口留给 `Cookie 2` 承接
- `Cookie 2 / Batch 1`:
  - `cc_stack`
  - `cc_compare`
  - `cc_agentic`
- `Cookie 2 / Batch 2`:
  - `cc_mcp`
  - `cc_commands`
  - `cc_prompting`
- `Cookie 2 / Batch 3`:
  - 只在以下情况启用：
  - 前 `5` 批后 `L2 eligible` 仍不足
  - coding / MCP / compare 净新增仍明显
  - 某一 cookie 出现明显不稳定，需要跨 cookie 补跑

运行判断：

- 若前 `4` 批后已经达到：
  - `L1 candidates >= 450`
  - `L2 eligible >= 150`
  - `L3 shortlist >= 100`
  则可直接停止，不强行跑满第 `5-6` 批
- 若前 `4` 批后 `overlap` 很高、但 `compare / stack / MCP` 表现突出，则优先跑第 `5` 批
- 第 `6` 批默认是 rescue batch，不是 mandatory batch

备注：

- `Claude Code` 比 `Claude` 更窄，天然更容易出现 query 重合
- 因此今天的重点不是“把 batch 跑满”，而是“把 net-new KOL 跑够”
- 默认仍沿用：
  - `X | en | 5000+ views | 1000+ followers | past 7 days`
- 默认排除词先沿用：
  - `crypto`, `trader`, `airdrop`
- 若今日跑完后发现大量抓到官方号、资讯搬运号或纯 leak 讨论号，明天可再补一轮负面词治理

### 2.2.4 `Codex`

定位：

- 今日建议把 `Codex` 作为独立 topic 新增到 matrix，而不是只作为 `Claude Code / Stack` 的扩展词
- 目标是优先找英语区、近 `7` 天内在 `X` 上发布过 `Codex` / `OpenAI Codex` / AI coding workflow 相关热帖的 KOL
- 相比 `Claude Code`，`Codex` 更适合覆盖 OpenAI ecosystem、agentic coding、terminal / IDE workflow、multi-agent engineering 与 build-in-public 人群
- 今日目标为 `100` 人，因此 `Codex` 占 `4` 组，`Claude / Claude Code` 占 `2` 组，用 `2 cookies x 3 batches` 做增量覆盖

执行建议：

- 今天采用 `2 cookies x 3 batches`
- `Claude` 只跑 `2` 组，用于维持泛 AI / Claude Code 开发者覆盖

### 2.2.5 `AI Real People / Claude Code + Codex + Cursor + MCP`

定位：

- 本组不是泛 `AI 工具博主` 搜索，而是优先抓 `真人 AI 从业者 / builder / engineer / operator`
- 今天目标不是最大化内容号数量，而是先提高 `真人号密度`
- 主题词不再只押单一品牌，而是用 `Claude Code + Codex + Cursor + MCP` 作为真人 AI 实操信号池

执行建议：

- intake 固定为：`X | en | 3000+ views | 1000+ followers | past 7 days`
- 当前按单 cookie 运行，先采用 `1 cookie x 3 batches`
- 第一批先跑 `4` 条 core query 做 probe，不追求一次跑满
- 若 probe 后营销号比例仍高，再继续收紧负面词和身份词，而不是先盲目扩 topic

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Builder Core` | `ai_real_builder` | `("Claude Code" OR Codex OR "OpenAI Codex" OR Cursor OR MCP) (builder OR founder OR engineer OR developer OR "indie hacker") (AI OR LLM OR agents OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 起盘，优先锁真人 builder / founder / engineer |
| `Practitioner` | `ai_real_practitioner` | `("Claude Code" OR Codex OR Cursor OR MCP) ("I use" OR using OR "built with" OR "working on" OR testing) (AI OR LLM OR agents OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 找真实使用者和实操流玩家 |
| `Engineering` | `ai_real_engineering` | `("Claude Code" OR Codex OR Cursor OR MCP) (engineer OR developer OR researcher OR scientist) (evals OR inference OR RAG OR agents OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 找更硬核的工程 / 研究型真人账号 |
| `Operator` | `ai_real_operator` | `("Claude Code" OR Codex OR Cursor OR MCP) (operator OR consultant OR product OR founder) (automation OR workflow OR deployment OR "use case") -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 找产品 / 业务 / 自动化实战真人号 |
| `Agentic` | `ai_real_agentic` | `("Claude Code" OR Codex OR Cursor OR MCP) (agents OR agentic OR orchestration OR "multi-agent" OR MCP) (builder OR engineer OR developer) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 agent workflow 与 infra 人群 |
| `Shipping` | `ai_real_shipping` | `("Claude Code" OR Codex OR Cursor OR MCP) (building OR shipping OR launched OR prototype OR repo) (builder OR founder OR engineer OR developer) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 build in public 和真实项目交付人群 |
| `Founder Signal` | `ai_real_founder_signal` | `("Claude Code" OR Codex OR Cursor OR MCP) (founder OR cofounder OR startup OR product) (AI OR automation OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | rescue batch，用于补 founder / operator 真人号 |
| `Research Signal` | `ai_real_research_signal` | `("Claude Code" OR Codex OR Cursor OR MCP) (research OR benchmark OR experiment OR evals OR paper) (researcher OR engineer OR scientist) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | rescue batch，用于补研究型真人号 |

建议 batch 分配：

- `Cookie 1 / Batch 1`:
  - `ai_real_builder`
  - `ai_real_practitioner`
  - `ai_real_engineering`
  - `ai_real_operator`
- `Cookie 1 / Batch 2`:
  - `ai_real_agentic`
  - `ai_real_shipping`
- `Cookie 1 / Batch 3`:
  - `ai_real_founder_signal`
  - `ai_real_research_signal`
  - 仅在前两批后真人池仍不足时启用

运行判断：

- 若 `Batch 1` 后已出现明显更高真人密度，则优先保留这组 query 继续扩跑
- 若 `Batch 1` 后营销号仍高，则先加重负面词，再决定是否启 `Batch 2`
- 若 `Batch 2` 后 `L3 shortlist < 80`，再启 `Batch 3`
- 今日核心目标是 `100` 个可用真人号，不是跑满所有 query

2026-05-17 variant extension:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Personal Build Log` | `ai_real_personal_build` | `("Claude Code" OR Codex OR Cursor OR MCP) ("I built" OR "I shipped" OR "my workflow" OR "my stack" OR "I use") (engineer OR founder OR developer OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补更强第一人称实践者 |
| `Founder Dev Loop` | `ai_real_founder_dev` | `("Claude Code" OR Codex OR Cursor OR MCP) (founder OR cofounder OR CEO OR engineer) (built OR shipping OR workflow OR repo OR product) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补个人 founder / operator / dev 混合号 |
| `Research Workflow` | `ai_real_research_workflow` | `("Claude Code" OR Codex OR Cursor OR MCP) (engineer OR researcher OR developer) (benchmark OR evals OR "my workflow" OR "my setup" OR experiment) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补研究 / setup / experiment 型真人号 |
| `Agent Builder` | `ai_real_agent_builder_v2` | `("Claude Code" OR Codex OR Cursor OR MCP) (agents OR subagents OR hooks OR skills OR MCP) (builder OR engineer OR founder OR developer) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 agent workflow builder |

2026-05-17 outer expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `MCP Builder Outer` | `ai_outer_mcp_builder` | `(MCP OR "Model Context Protocol" OR "AI agents" OR agentic) (builder OR founder OR engineer OR developer) (workflow OR tools OR connectors OR automation) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 外扩到 MCP / toolchain builder 真人号 |
| `Agent Infra Outer` | `ai_outer_agent_infra` | `("AI agents" OR agentic OR orchestration OR subagents OR hooks) (engineer OR developer OR researcher OR founder) (repo OR infra OR workflow OR benchmark) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 agent infra / orchestration 真人号 |
| `Automation Operator Outer` | `ai_outer_automation_operator` | `("AI automation" OR automation OR workflow OR MCP) (operator OR consultant OR founder OR builder) (shipping OR deployed OR usecase OR product) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 automation operator / founder 真人号 |
| `Personal AI Workflow Outer` | `ai_outer_personal_workflow` | `("my workflow" OR "I built" OR "I use" OR "my setup") (AI OR agents OR MCP OR automation) (engineer OR founder OR developer OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补第一人称 AI workflow 真人号 |

2026-05-17 coding expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Coding Builder` | `ai_coding_builder_v3` | `("AI coding" OR devtools OR coding OR "developer tools") (builder OR founder OR engineer OR developer) (workflow OR repo OR product OR shipped) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 外扩 AI coding builder 真人号 |
| `OSS Agent Builder` | `ai_oss_agent_builder` | `("open source" OR OSS OR repo OR GitHub) (agents OR MCP OR automation OR devtools) (engineer OR developer OR founder OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 OSS / GitHub builder |
| `Dev Workflow Operator` | `ai_dev_workflow_operator` | `("developer workflow" OR automation OR "engineering workflow" OR devtools) (operator OR founder OR consultant OR builder) (AI OR agents OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 dev workflow operator 真人号 |
| `Shipping Engineer` | `ai_shipping_engineer_v3` | `(shipping OR shipped OR building OR launched OR deployed) (AI OR agents OR devtools OR coding) (engineer OR developer OR founder OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 shipping/practitioner 真人号 |

2026-05-17 infra oss expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Infra Builder` | `ai_infra_builder_v5` | `(infra OR infrastructure OR backend OR platform engineering) (AI OR agents OR MCP OR automation) (engineer OR developer OR founder OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 infra / backend builder 真人号 |
| `DevOps Agent` | `ai_devops_agent_v5` | `(devops OR sre OR deployment OR ci/cd OR observability) (AI OR agents OR automation OR coding) (engineer OR developer OR builder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 devops/automation 真人号 |
| `OSS Maintainer` | `ai_oss_maintainer_v5` | `(opensource OR "open source" OR maintainer OR repo OR github) (AI OR agents OR devtools OR automation) (engineer OR developer OR founder) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 OSS maintainer 真人号 |
| `MCP Tooling` | `ai_mcp_tooling_v5` | `(MCP OR "Model Context Protocol" OR tooling OR connectors) (engineer OR developer OR founder OR builder) (repo OR github OR automation OR workflow) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 MCP tooling 真人号 |

2026-05-17 indie educator expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Indie Builder` | `ai_indie_builder_v6` | `(indie OR solopreneur OR solo OR builder) (AI OR agents OR coding OR automation) (developer OR founder OR engineer) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补独立开发 / solo builder 真人号 |
| `AI Educator Practitioner` | `ai_educator_practitioner_v6` | `(tutorial OR walkthrough OR guide OR setup) (AI OR coding OR agents OR MCP) (engineer OR developer OR founder OR educator) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补会教但仍偏实践的真人号 |
| `Product Engineer AI` | `ai_product_engineer_v6` | `(product engineer OR product engineering OR software engineer) (AI OR devtools OR coding OR automation) (workflow OR built OR repo OR shipped) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 product/software engineer 真人号 |
| `AI Workflow Builder` | `ai_workflow_builder_v6` | `(workflow builder OR automation builder OR ai workflow) (founder OR builder OR engineer OR developer) (AI OR agents OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 workflow builder 真人号 |

2026-05-17 product operator expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Product Operator` | `ai_product_operator_v7` | `("AI product" OR product OR pm OR operator) (founder OR builder OR engineer OR consultant) (automation OR workflow OR coding OR agents) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 AI product/operator 真人号 |
| `Startup Engineer AI` | `ai_startup_engineer_v7` | `(startup OR founder OR early-stage) (engineer OR developer OR builder) (AI OR coding OR devtools OR automation) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 startup engineer / founder 真人号 |
| `PM Builder AI` | `ai_pm_builder_v7` | `(pm OR "product manager" OR builder) (AI OR agents OR automation OR coding) (workflow OR shipped OR built OR product) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 PM/builder 真人号 |
| `Automation Founder` | `ai_automation_founder_v7` | `(automation OR "AI workflow" OR agents) (founder OR ceo OR builder OR operator) (product OR startup OR shipped OR deployed) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 founder/operator 真人号 |

2026-05-17 implementer expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Implementer` | `ai_implementer_v8` | `(implementer OR consultant OR freelancer OR operator) (AI OR automation OR agents OR coding) (workflow OR deployed OR shipped OR client) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补真实交付型个人号 |
| `Technical Founder` | `ai_technical_founder_v8` | `(founder OR cofounder OR ceo) (engineer OR developer OR technical) (AI OR automation OR devtools OR coding) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补技术型 founder 真人号 |
| `Startup Operator` | `ai_startup_operator_v8` | `(startup OR operator OR product) (AI OR automation OR agents) (builder OR founder OR engineer OR consultant) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 startup operator 真人号 |
| `Client Automation Builder` | `ai_client_automation_v8` | `(client OR business OR operations) (automation OR workflow OR AI agents) (builder OR consultant OR founder OR operator) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 client-facing automation 个人号 |

2026-05-17 consultant strategist expansion:

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Consultant` | `ai_consultant_v9` | `(consultant OR advisor OR strategist OR specialist) (AI OR automation OR agents OR coding) (builder OR founder OR engineer OR operator) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补顾问/顾问型个人号 |
| `Automation Specialist` | `ai_automation_specialist_v9` | `(specialist OR advisor OR consultant) (automation OR workflow OR AI agents) (deployed OR implementation OR systems OR ops) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 automation specialist |
| `Technical Advisor` | `ai_technical_advisor_v9` | `(advisor OR consultant OR operator) (technical OR engineering OR devtools) (AI OR coding OR automation) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 technical advisor |
| `Freelance Builder` | `ai_freelance_builder_v9` | `(freelance OR contractor OR consultant OR builder) (AI OR automation OR coding OR devtools) (founder OR engineer OR developer OR operator) -crypto -trader -airdrop -newsletter -media -agency -marketing -growth -seo` | 补 freelance/contractor 真人号 |

2026-05-17 business fallback:

- `ai_business_founder_v10`
- `ai_business_ops_v10`
- `ai_builder_product_v10`
- `Codex` 跑 `4` 组，作为今日主力新增 topic
- 前 `4` 批重点观察：
  - `query relevance`
  - `overlap ratio`
  - `net-new handle yield`
  - `cookie stability`
- 若前 `5` 批后 `L3 shortlist >= 100`，第 `6` 批只做质量补强或可暂停
- 若 `Codex` 直接搜索出现代码仓库、官方公告、新闻搬运号过多，则优先加 `developer / builder / terminal / IDE / workflow` 约束，不急着扩宽 topic

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Core` | `codex_core` | `"Codex" ("AI coding" OR coding OR developer OR engineering OR terminal OR IDE) -crypto -trader -airdrop` | 起盘，锁定真正讨论 Codex 与 AI coding 的开发者和重度用户 |
| `OpenAI` | `codex_openai` | `"OpenAI Codex" (developer OR coding OR engineering OR agents OR automation) -crypto -trader -airdrop` | 降低 Codex 泛词歧义，锁定 OpenAI Codex 语境 |
| `Builder` | `codex_builder` | `"Codex" (builder OR founder OR engineer OR indiehacker OR creator) ("AI coding" OR agent OR automation) -crypto -trader -airdrop` | 找 builder / founder / engineer 型账号 |
| `Workflow` | `codex_workflow` | `"Codex" (workflow OR automation OR "use case" OR productivity OR systems) ("AI coding" OR developer) -crypto -trader -airdrop` | 找真实应用场景和效率工作流用户 |
| `Tutorial` | `codex_tutorial` | `"Codex" (tutorial OR walkthrough OR guide OR demo OR setup) ("AI coding" OR developer) -crypto -trader -airdrop` | 找能做教程、演示和内容交付的 KOL |
| `Review` | `codex_review` | `"Codex" (review OR benchmark OR tested OR experiment OR thoughts) ("AI coding" OR developer) -crypto -trader -airdrop` | 找评测、观点和实测型账号 |
| `Compare` | `codex_compare` | `"Codex" (compare OR comparison OR "vs" OR alternative OR competitor) (Claude OR Cursor OR Cline OR "AI coding") -crypto -trader -airdrop` | 找购买决策和工具选型影响者 |
| `Stack` | `codex_stack` | `"Codex" (Claude Code OR Cursor OR Cline OR Warp OR terminal OR IDE) -crypto -trader -airdrop` | 找公开比较 AI coding 工具栈的人 |
| `Agentic` | `codex_agentic` | `"Codex" (agents OR agentic OR multi-agent OR orchestration OR worktree) ("AI coding" OR developer) -crypto -trader -airdrop` | 找 agent workflow 和并行工程协作人群 |
| `Shipping` | `codex_shipping` | `"Codex" (shipping OR shipped OR building OR launch OR deployed) ("AI coding" OR developer) -crypto -trader -airdrop` | 找 build-in-public 与实战交付型账号 |
| `Commands` | `codex_commands` | `"Codex" (CLI OR terminal OR commands OR prompt OR instructions OR spec) ("AI coding" OR developer) -crypto -trader -airdrop` | 找命令行、prompt/spec 和 power user 人群 |
| `Rescue Best` | `codex_rescue_best` | 从前 `5` 批里选择低重合、高相关、高净新增的 `2-3` 条 `Codex` query 复跑 | 第 6 批兜底补量，不作为固定 query |

建议 batch 分配：

- `Cookie 1 / Batch 1`:
  - `topic_core`
  - `topic_workflow`
  - `topic_content`
- `Cookie 1 / Batch 2`:
  - `codex_core`
  - `codex_openai`
  - `codex_builder`
- `Cookie 1 / Batch 3`:
  - `codex_workflow`
  - `codex_tutorial`
  - `codex_review`
- `Cookie 2 / Batch 4`:
  - `cc_stack`
  - `cc_agentic`
  - `cc_mcp`
- `Cookie 2 / Batch 5`:
  - `codex_compare`
  - `codex_stack`
  - `codex_agentic`
- `Cookie 2 / Batch 6`:
  - `codex_shipping`
  - `codex_commands`
  - `codex_rescue_best`

运行判断：

- 若前 `4` 批后已经达到：
  - `L1 candidates >= 450`
  - `L2 eligible >= 150`
  - `L3 shortlist >= 100`
  则第 `5-6` 批可改为质量补强，而不是强行扩量
- 若 `Claude` 两组与历史 `Claude Code` 重合高，则后续优先把资源让给 `Codex`
- 若 `Codex` batch 的净新增明显高，则第 `6` 批复跑 `Codex` 最优 query，不再扩新 topic
- 若出现大量官方号、资讯号、组织号，只按明确 handle denylist 移除；宽泛可疑组织词进入审计，不默认删除

备注：

- `2026-04-08` intake 已确认：`X | en | 目标 100 人 | Claude 2 组 | Codex 4 组 | 2 cookies, 各自 3 组`
- 默认仍沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
- 默认排除词先沿用：
  - `crypto`, `trader`, `airdrop`
- 今日执行时先由本节 query names 生成当天 `spec / implementation plan / batch allocation / todo`，再进入 pipeline

### 2.2.5 `AI Coding Rescue`

定位：

- 本节用于 `2026-04-08` 后半场补量，前提是 master 硬过滤、账号去重、`1000+ followers` 保持不变
- 与 `2.2.4 Codex` 不同，本节不再只押 `Codex` 窄词，而是围绕 AI coding 工具栈做三组扩展
- 今日确认的三组为：
  - `Cursor`
  - `OpenCode`
  - `Codex CLI`
- 目标是补齐 `2000+ views` 下的 net-new KOL 缺口，而不是替代原本 `5000+ views` 主池

执行建议：

- 每组单独作为一个 batch
- `views gate` 可设置为 `2000+`
- `followers gate` 继续保持 `1000+`
- `discovery master` 继续硬过滤，不允许放开
- 若某一组出现大量官方号或组织号，先用明确 handle denylist；不要用泛关键词误伤个人开发者

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Cursor` | `rescue_cursor_stack` | `"Cursor" ("AI coding" OR "coding agent" OR "developer tools" OR IDE OR workflow OR agents) -crypto -trader -airdrop` | 找 Cursor 相关 AI coding / IDE / agent workflow 账号 |
| `OpenCode` | `rescue_opencode_stack` | `"OpenCode" ("AI coding" OR "coding agent" OR CLI OR terminal OR developer OR workflow) -crypto -trader -airdrop` | 找 OpenCode 与 CLI / terminal-native AI coding 人群 |
| `Codex CLI` | `rescue_codex_cli_stack` | `"Codex CLI" (terminal OR CLI OR commands OR "AI coding" OR developer OR agents) -crypto -trader -airdrop` | 找 Codex CLI power users、terminal workflow 和实操型开发者 |

建议 batch 分配：

- `Batch 7`:
  - `rescue_cursor_stack`
- `Batch 8`:
  - `rescue_opencode_stack`
- `Batch 9`:
  - `rescue_codex_cli_stack`

运行判断：

- 若 `Batch 7-9` 任一批出现高相关低量，可保留为质量补充，不强行扩成宽泛 AI 词
- 若 `Cursor` 组组织号过多，优先精确移除官方/公司 handle，不删除个人创作者
- 若三批后仍不足 `100`，再考虑新增下一节 topic，而不是在本节临时发明 query names

### 2.2.6 `AI Coding Rescue II`

定位：

- 本节用于 `2026-04-08` 继续冲 `100` 人目标，前提是 master 硬过滤、账号去重、`1000+ followers` 保持不变
- `2.2.5` 执行后仍不足 `100`，因此本节采用更宽但仍在 AI coding 语境内的工具栈扩展
- 不放开 master，不进入 DM fill，不默认删除宽泛可疑组织关键词

执行建议：

- 每组单独作为一个 batch
- `views gate` 继续使用 `2000+`
- `followers gate` 继续保持 `1000+`
- 若出现官方号或媒体号，只按明确 handle denylist 删除；个人号即使 bio/name 含 `labs / inc / agency / newsletter` 也先进入审计

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Cline` | `rescue_cline_stack` | `"Cline" ("AI coding" OR "coding agent" OR VSCode OR IDE OR workflow OR agents) -crypto -trader -airdrop` | 找 Cline / VSCode agent workflow 的开发者与实操型账号 |
| `Warp` | `rescue_warp_terminal_stack` | `"Warp" (terminal OR CLI OR "AI coding" OR "coding agent" OR developer OR workflow) -crypto -trader -airdrop` | 找 Warp terminal 与 AI coding CLI 工作流用户 |
| `GitHub Copilot` | `rescue_github_copilot_stack` | `"GitHub Copilot" ("AI coding" OR coding OR developer OR workflow OR agents OR IDE) -crypto -trader -airdrop` | 找 Copilot 相关 AI coding / IDE / developer workflow 账号 |
| `Agent Workflow Broad` | `rescue_agent_workflow_broad` | `("AI coding agent" OR "coding agent" OR "agentic coding") (Cursor OR Cline OR Codex OR "Claude Code" OR Warp OR terminal OR IDE) -crypto -trader -airdrop` | 用宽泛 agent workflow 补齐工具栈重度用户与内容创作者 |

建议 batch 分配：

- `Batch 10`:
  - `rescue_cline_stack`
- `Batch 11`:
  - `rescue_warp_terminal_stack`
- `Batch 12`:
  - `rescue_github_copilot_stack`
- `Batch 13`:
  - `rescue_agent_workflow_broad`

运行判断：

- 若任一批触发 X 429，则停止当前 cookie，优先保留另一个 cookie 做下一批
- 若合并后 `kept_rows >= 100`，停止补量并只做合并审计，不进入 DM fill
- 若四批后仍不足 `100`，再评估是否需要降低 views gate 到 `1000-1999 review-only`，不直接进主 DM 表

### 2.2.7 `AI Coding Rescue III`

定位：

- 本节用于 `2026-04-08` 在 `82` 人基础上继续补足到 `100`
- 继续保持 `master` 硬过滤、`2000+ views`、`1000+ followers`、账号去重不变
- 避开今天已验证低效或强重合的窄词，转向更可能产出个人开发者账号的 AI coding 工具与 workflow 语境

执行建议：

- 每组单独作为一个 batch
- 仍然只移除明确机构号；宽泛关键词疑似组织号继续审计不默认删除
- 若任一组大量命中官方号，则只补充明确 handle denylist，不在 query 文本里临时改写

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Windsurf` | `rescue_windsurf_stack` | `"Windsurf" ("AI coding" OR "coding agent" OR IDE OR workflow OR terminal OR developer) -crypto -trader -airdrop` | 找 Windsurf 相关 AI coding / IDE / workflow 创作者与重度用户 |
| `Replit Agent` | `rescue_replit_agent_stack` | `("Replit Agent" OR "Replit AI") ("AI coding" OR coding OR developer OR workflow OR builder) -crypto -trader -airdrop` | 找 Replit Agent / Replit AI builder 与开发者内容账号 |
| `VS Code AI` | `rescue_vscode_ai_stack` | `("VS Code" OR VSCode) ("AI coding" OR "coding agent" OR Copilot OR Cline OR workflow OR developer) -crypto -trader -airdrop` | 找 VS Code AI coding / extension / workflow 个人账号 |
| `Terminal Agent Workflow` | `rescue_terminal_agent_workflow` | `("terminal workflow" OR "terminal agent" OR "CLI agent") ("AI coding" OR Codex OR Cursor OR Cline OR Warp OR developer) -crypto -trader -airdrop` | 找 terminal-native AI coding power users 与 workflow 创作者 |

建议 batch 分配：

- `Batch 14`:
  - `rescue_windsurf_stack`
- `Batch 15`:
  - `rescue_replit_agent_stack`
- `Batch 16`:
  - `rescue_vscode_ai_stack`
- `Batch 17`:
  - `rescue_terminal_agent_workflow`

运行判断：

- 若前两批后新增仍显著偏低，剩余两批继续执行，但只作为最终补量，不再另开更宽 topic
- 若合并后 `kept_rows >= 100`，立即停止，不进入 DM fill
- 若四批完成后仍不足 `100`，当天建议止损，次日换新时间窗和新 topic 重开

### 2.2.8 `Gemini`

定位：

- 本节用于 `2026-04-09` 在 `OpenClaw + Claude + AI coding agent` 首轮之后，继续补量冲击 `100`
- `Gemini` 作为新的正式 topic，必须先入 `QUERY_LIBRARY.md` 再进入 spec / batch run
- 目标是优先补充英语区、近 `7` 天内围绕 `Gemini` 产出教程、评测、工作流内容的 AI creator
- 相比今天弱表现的 `AI coding agent` broad 组，`Gemini` 更可能带来泛 AI creator 增量，而不是高重合的 devtools 老人池

执行建议：

- 当前先使用 `2` 组最稳的 `content / workflow`
- 若 `Gemini` 后续表现好，再考虑追加 `compare / roles`
- 默认继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Content` | `gemini_content` | `"Gemini" (tutorial OR review OR demo OR walkthrough OR comparison) (AI OR LLM OR assistant) -crypto -trader -airdrop` | 找围绕 Gemini 产出教程、评测、对比内容的 creator |
| `Workflow` | `gemini_workflow` | `"Gemini" ("AI workflow" OR "AI automation" OR "use case" OR productivity OR research) -crypto -trader -airdrop` | 找 Gemini 真实使用场景与工作流创作者 |

建议 batch 分配：

- 第二轮 `Batch 5`:
  - `gemini_content`
- 第二轮 `Batch 6`:
  - `gemini_workflow`

运行判断：

- 若 `Gemini` 两批都表现稳定，可把它升级为后续常驻 topic
- 若 `Gemini` 出现高量但重合高，优先改用 `compare / roles`，不要继续重复 `content / workflow`
- 若 `Gemini` 也明显偏弱，当天应优先止损，不再继续追加泛 AI 宽词

第二轮扩展建议：

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Compare` | `gemini_compare` | `"Gemini" (compare OR comparison OR "vs" OR alternative OR competitor) (AI OR LLM OR assistant) -crypto -trader -airdrop` | 找对 Gemini 有购买决策和工具对比影响力的 creator |
| `Roles` | `gemini_roles` | `"Gemini" (builder OR founder OR engineer OR researcher OR creator) (AI OR LLM OR automation) -crypto -trader -airdrop` | 找围绕 Gemini 发声的 builder / engineer / creator 型账号 |

### 2.2.9 `Meta Muse Spark`

定位：

- 本节用于 `2026-04-09` 第三轮补量，借当天海外 AI 热点中的 `Meta` 新模型线索
- 当前只先注册最稳的 `content / workflow` 两组，不直接扩到更宽的 compare/roles
- 目标是测试 `Muse Spark` 是否已经形成可抓取的 creator 讨论面，而不是只看官方号和媒体号

执行建议：

- 默认继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`
- 若模型名噪音过低或量过窄，可后续切到更宽的 `Meta AI`

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Content` | `muse_spark_content` | `"Muse Spark" (tutorial OR review OR demo OR walkthrough OR comparison) (AI OR LLM OR Meta) -crypto -trader -airdrop` | 找围绕 Meta 新模型做教程、评测、演示的 creator |
| `Workflow` | `muse_spark_workflow` | `"Muse Spark" ("AI workflow" OR "use case" OR productivity OR research OR "Meta AI") -crypto -trader -airdrop` | 找围绕新模型做使用场景、工作流讨论的账号 |
| `Meta AI Workflow` | `meta_ai_workflow` | `"Meta AI" ("AI workflow" OR "use case" OR productivity OR assistant OR research) -crypto -trader -airdrop` | 用更宽的 Meta AI 语境补充 Muse Spark 可能漏掉的 creator 与 use-case 账号 |

运行判断：

- 若 `Muse Spark` 两批结果稀疏，但质量高，可保留为热点响应 topic
- 若 `Muse Spark` 明显偏空，不建议当天继续加更宽 Meta 词，优先回到 `Claude / Gemini`

### 2.2.10 `AI News Hooks - April 2026`

定位：

- 本节用于 `2026-04-09` 新一轮补量，目标继续冲 `100` 人，但不重复当天已经跑过的 `Gemini content/workflow` 与 `Muse Spark content/workflow`
- 当前策略是用过去 `72` 小时内较新的海外 AI 新闻做 topic hook，同时尽量保持 query 更接近 creator 讨论面，而不是纯媒体资讯抓取
- 新增 query name 必须先入 `QUERY_LIBRARY.md`，再进入 spec / batch run

执行建议：

- 默认继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`
- 本轮优先测试：
  - 热点模型名：`Muse Spark`, `Gemma 4`, `Veo 3.1 Lite`
  - 更宽上位叙事：`personal superintelligence`, `Search Live`, `Gemini 3.1 Flash Live`
- 若某个新闻名过窄，优先切到其上位叙事词，而不是继续硬跑同一模型名

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Compare` | `muse_spark_compare` | `"Muse Spark" (compare OR comparison OR "vs" OR benchmark OR eval) (AI OR LLM OR Meta) -crypto -trader -airdrop` | 找围绕 Meta 新模型做对比、benchmark、观点输出的 creator |
| `Open Model` | `gemma4` | `"Gemma 4" ("open model" OR local OR on-device OR developer OR benchmark) -crypto -trader -airdrop` | 找围绕 Gemma 4、open model、local AI 发声的开发者与 creator |
| `Video Model` | `veo_3_1_lite` | `("Veo 3.1 Lite" OR "Veo Lite") (video OR demo OR workflow OR creator OR filmmaking) -crypto -trader -airdrop` | 找 AI video / creative tool / demo creator |
| `Meta Narrative` | `meta_superintelligence` | `("personal superintelligence" OR "Superintelligence Labs") (Meta OR "Meta AI" OR Muse) -crypto -trader -airdrop` | 借 Meta 上位叙事抓趋势讨论型 creator |
| `Search UX` | `search_live` | `("Search Live" OR "AI Mode") (demo OR tested OR workflow OR "use case" OR tips) -crypto -trader -airdrop` | 找围绕 Google 新搜索体验做演示、测试、技巧内容的人 |
| `Realtime Voice` | `flash_live_voice_model` | `("Gemini 3.1 Flash Live" OR "Flash Live") (voice OR audio OR realtime OR camera OR demo) -crypto -trader -airdrop` | 找围绕 Gemini 实时语音/视频交互做体验和工作流内容的人 |

运行判断：

- 若 `muse_spark_compare` 出现质量高但量小，说明热点词适合作为补量钩子，但不适合当天主轴
- 若 `gemma4` 和 `flash_live_voice_model` 表现稳定，可后续升级成常驻 Google 开发者向 topic
- 若 `search_live` 出现高媒体噪音，应保留 query name，但后续改向 `tips / tested / workflow` 更强的版本

### 2.2.11 `Broad AI Creator Terms`

定位：

- 当热点词太窄、出量不足时，优先回到更基础的大词
- 目标不是抓“今天最热的新闻讨论者”，而是抓持续输出 AI 内容、AI workflow、AI coding、AI video 的 creator / builder / engineer
- 这组 query 适合作为当天冲量主轴，也适合作为后续 rescue batch 的常驻大词库
- 相比单点模型词，这组更容易出量，但需要依靠 `creator / builder / tutorial / workflow / review` 等行为词约束，避免媒体噪音过大

执行建议：

- 当单点热点词连续两组总净新增不足 `20` 时，优先切回本组
- 采用 `2 cookies x 3 batches` 运行，但每组 query 都可独立复用为 rescue batch
- 若发现 `AI agent` 或 `LLM` 结果过宽，可先保留 query name，后续再加更强的角色或动作词，而不是直接废弃

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Tools` | `ai_tools_creator` | `("AI tools" OR "AI tool") (creator OR review OR tutorial OR workflow) -crypto -trader -airdrop` | 找长期发布 AI tools 教程、评测、工作流内容的 creator |
| `AI Workflow` | `ai_workflow_builder` | `("AI workflow" OR "AI automation") (builder OR founder OR creator OR engineer) -crypto -trader -airdrop` | 找重度使用 AI workflow / automation 的 builder 与 founder |
| `AI Coding` | `ai_coding_creator` | `("AI coding" OR "coding with AI") (creator OR tutorial OR workflow OR review) -crypto -trader -airdrop` | 找 AI coding 内容作者与教程型账号 |
| `AI Agent` | `ai_agent_builder` | `("AI agent" OR "AI agents") (builder OR engineer OR workflow OR tutorial) -crypto -trader -airdrop` | 找 agent builder、工程流、教程流账号 |
| `AI Video` | `ai_video_creator` | `("AI video" OR "video generation") (creator OR tutorial OR review OR workflow) -crypto -trader -airdrop` | 找 AI video / content creation / workflow creator |
| `LLM` | `llm_builder` | `(LLM OR "large language model") (builder OR engineer OR tutorial OR workflow) -crypto -trader -airdrop` | 找讨论 LLM 工程、教程、workflow 的开发者与 creator |

运行判断：

- 若 `ai_tools_creator` 和 `ai_workflow_builder` 仍然出量偏低，说明不是热点词问题，而是当天整个平台 AI creator 池偏薄
- 若 `ai_agent_builder` 媒体噪音过大，优先后续细化到 `builder / workflow / tutorial` 更强的版本
- 若 `ai_video_creator` 表现优于 `ai_coding_creator`，说明当天更适合向 content-creation creator 池扩张

### 2.2.12 `Broad AI Expansion Terms`

定位：

- 本节用于在基础大词已经验证有效后，继续向相邻高产方向扩量
- 目标是优先补足第二个 merge 池的净新增，而不是追求更窄的 topic 精准度
- 当前优先沿着上一轮表现更好的 `AI agent / AI video / LLM` 方向外扩，再补一个更宽的 `AI builder / automation / GenAI creator` 池

执行建议：

- 继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`
- 若本节中某组大词产出很多机构号，后续优先保留 query name，再在人审阶段做窄口径 obvious-org 清理
- 若本节跑完后第二个 merge 池仍然不足 `80`，再考虑降低 views 门槛，而不是在本轮提前降阈值

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Agent Creator` | `ai_agent_creator` | `("AI agent" OR "AI agents") (creator OR review OR demo OR tutorial OR workflow) -crypto -trader -airdrop` | 在 agent builder 之外补 creator / demo / review 型账号 |
| `AI Video Workflow` | `ai_video_workflow` | `("AI video" OR "video generation") (workflow OR demo OR filmmaking OR creator OR tutorial) -crypto -trader -airdrop` | 强化 AI video / demo / filmmaking creator 池 |
| `LLM Tutorial` | `llm_tutorial` | `(LLM OR "large language model") (tutorial OR guide OR demo OR workflow OR review) -crypto -trader -airdrop` | 在 LLM builder 之外补教程与演示型账号 |
| `AI Builder` | `ai_builder` | `(AI OR "GenAI") (builder OR founder OR engineer OR creator) -crypto -trader -airdrop` | 用最宽的 builder 大词补量 |
| `AI Automation Creator` | `ai_automation_creator` | `("AI automation" OR automation) (creator OR founder OR builder OR workflow) -crypto -trader -airdrop` | 抓 workflow / automation creator 与 builder |
| `GenAI Creator` | `genai_creator` | `(GenAI OR "generative AI") (creator OR tutorial OR review OR workflow) -crypto -trader -airdrop` | 用 generative AI 大词抓更泛的 creator 池 |

运行判断：

- 若 `ai_agent_creator` 与 `ai_video_workflow` 继续高产，说明这天最适合向 demo / creator / workflow 人群扩，不必再回到新闻词
- 若 `ai_builder` 明显比其他组更宽但仍高产，可保留为后续长期救量词
- 若 `genai_creator` 媒体噪音偏高，可保留 query name，后续改强 `creator / tutorial / workflow` 约束而不是废弃

### 2.2.13 `Tomorrow Hot 6 - 2026-04-12`

定位：

- 本节用于 `2026-04-12` 的 `X KOL fuzzy discovery` 预执行准备
- 目标是围绕当天已锁定的 `6` 个热词 anchors，直接拆成 `6` 个独立 batch
- 目标人群是 `X` 上英语区、近 `7` 天内有热帖、偏 `creator / builder / workflow / tutorial / review` 的 net-new creator
- 默认继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`
- 本轮不允许用新闻热点单点词直接起盘，不只押单一模型名、单一发布会词、单一品牌新功能词
- 已检查现有 Part 2：以下 `6` 个 anchor-specific `Query Name` 均未重名，因此本轮按新名称注册

执行建议：

- 每个 batch 只跑 `1` 个 anchor query，避免混锚点导致 overlap 难分析
- query 统一加上 `creator / builder / workflow / tutorial / review / demo` 等行为词，优先抓个人创作者而不是媒体和官方号
- 为了降低媒体号、品牌号、官方号噪音，本轮 query text 统一追加保守负向词：
  - `-news -media -official -brand -company`
- 若某组前排结果明显被媒体号占满，优先停该 batch，不要在同 anchor 上追加更宽词

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Sam Altman` | `sam_altman_creator_signal` | `("Sam Altman") (creator OR builder OR founder OR engineer OR workflow OR tutorial OR demo OR review) (AI OR tooling OR startup OR product) -crypto -trader -airdrop -news -media -official -brand -company` | 借强讨论锚点抓围绕 Sam Altman 产出观点、教程、workflow、产品实测的个人 creator，而不是媒体转述号 |
| `Hermes Agent` | `hermes_agent_creator_signal` | `("Hermes Agent") (creator OR builder OR demo OR tutorial OR workflow OR review) (AI OR agent OR automation OR tooling) -crypto -trader -airdrop -news -media -official -brand -company` | 借新 agent 工具词抓早期 builder、demo 型 creator 和实操流账号，优先 net-new |
| `AI Agents` | `ai_agents_creator_signal` | `("AI agent" OR "AI agents") (creator OR builder OR demo OR tutorial OR workflow OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 用成熟大词稳定补量，同时用 creator/workflow/tutorial 约束减少纯资讯号 |
| `AI Video` | `ai_video_creator_signal` | `("AI video" OR "video generation" OR "AI filmmaking") (creator OR demo OR tutorial OR workflow OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 当天高概率能抓到 demo、filmmaking、review 型内容创作者，适合补 creator 池 |
| `AI Automation` | `ai_automation_creator_signal` | `("AI automation" OR automation) (creator OR builder OR workflow OR demo OR tutorial) -crypto -trader -airdrop -news -media -official -brand -company` | 直接偏向 workflow 和 builder 讨论面，通常比纯新闻词更容易产出可转化 creator |
| `AI Coding Tools` | `ai_coding_tools_creator_signal` | `("AI coding tools" OR "AI coding" OR "coding agent") (creator OR builder OR demo OR tutorial OR workflow OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 对准 AI coding / coding agent 讨论面，优先挖实操、评测、工作流输出型 creator |

运行判断：

- 若 `Sam Altman` 与 `Hermes Agent` 结果偏窄但前排质量高，说明热点 anchor 适合作为高质量补充批次而非冲量主轴
- 若 `AI agents / AI automation / AI coding tools` 稳定产出 net-new creator，可作为后续救量常驻 query
- 若 `AI video` 表现优于其他组，说明当天更适合向内容创作型 creator 池倾斜，而不是继续追新闻词

### 2.2.14 `Tomorrow Hot 6 Expansion - 2026-04-12`

定位：

- 本节用于 `2026-04-12` 首轮 `6` 个 batch 跑完后继续冲量，目标把 `S2 cold` 总量从 `38` 提升到 `80+`
- 扩量策略不再平均分配，而是优先给已经验证出量的 `AI agents / AI automation / AI coding tools`
- 每个主题优先拆成 `creator` 与 `builder / workflow` 两类变体，提升 net-new creator 覆盖
- `Sam Altman` 继续保留，但仅作为高质量补充，不再占主配额

执行建议：

- 默认继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - `past 7 days`
  - `crypto`, `trader`, `airdrop`
- 继续保留保守负向词：
  - `-news -media -official -brand -company`
- 扩量批次按优先级分三层：
  - 主冲量层：`6` 个 batch
  - 第二扩量层：`4` 个 batch
  - 高质量补充层：`2` 个 batch

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Agents Creator` | `ai_agents_creator_case` | `("AI agent" OR "AI agents") (creator OR demo OR workflow OR tutorial OR review OR "case study") -crypto -trader -airdrop -news -media -official -brand -company` | 在首轮 agent 基础上更偏 demo / tutorial / case-study creator，继续冲量 |
| `AI Agents Builder` | `ai_agents_builder_stack` | `("AI agent" OR "AI agents") (builder OR engineer OR founder OR shipped OR stack OR orchestration) -crypto -trader -airdrop -news -media -official -brand -company` | 抓偏工程、系统、stack 视角的 agent builder |
| `AI Automation Workflow` | `ai_automation_workflow_ops` | `("AI automation" OR automation) (workflow OR systems OR ops OR tutorial OR "use case" OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 强化 workflow / ops / use-case 创作者池 |
| `AI Automation Builder` | `ai_automation_builder_creator` | `("AI automation" OR automation) (builder OR founder OR engineer OR creator OR agency) -crypto -trader -airdrop -news -media -official -brand -company` | 补 builder / founder / creator 侧的 automation 人群 |
| `AI Coding Tools Tutorial` | `ai_coding_tools_tutorial_workflow` | `("AI coding tools" OR "AI coding" OR "coding agent") (tutorial OR walkthrough OR demo OR review OR workflow) -crypto -trader -airdrop -news -media -official -brand -company` | 继续扩 AI coding 教程、实操、工作流内容创作者 |
| `AI Coding Tools Builder` | `ai_coding_tools_builder_stack` | `("AI coding tools" OR "AI coding" OR "coding agent") (builder OR engineer OR founder OR shipped OR stack) -crypto -trader -airdrop -news -media -official -brand -company` | 抓偏工程实践和 build-in-public 的 coding tool builder |
| `AI Video Creator` | `ai_video_creator_filmmaking` | `("AI video" OR "video generation" OR "AI filmmaking") (creator OR demo OR tutorial OR review OR workflow OR "short film") -crypto -trader -airdrop -news -media -official -brand -company` | 扩 AI video / filmmaking / short-film creator 池 |
| `AI Video Workflow` | `ai_video_workflow_editing` | `("AI video" OR "video generation") (workflow OR prompt OR editing OR filmmaking OR "behind the scenes") -crypto -trader -airdrop -news -media -official -brand -company` | 抓偏制作流程、editing、幕后工作流的创作者 |
| `Hermes Agent Builder` | `hermes_agent_builder_ops` | `("Hermes Agent") (builder OR engineer OR demo OR workflow OR tutorial OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 在首轮 Hermes 基础上继续抓 builder 和教程型 creator |
| `Hermes Agent Adjacent` | `hermes_agent_stack_demo` | `("Hermes Agent") (agent OR automation OR stack OR orchestration OR "use case" OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 用相邻 agent / automation 语境补 Hermes 讨论面 |
| `Sam Altman Creator` | `sam_altman_creator_workflow` | `("Sam Altman") (builder OR creator OR workflow OR tutorial OR review OR "product thoughts") -crypto -trader -airdrop -news -media -official -brand -company` | 保留 Sam Altman 作为高质量补充批次，抓观点与产品实践 creator |
| `Sam Altman Startup` | `sam_altman_startup_tools` | `("Sam Altman") (startup OR product OR "AI tools" OR builder OR founder OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 用 startup / product / tools 语境补更偏 builder 的个人账号 |

运行判断：

- 若 `AI agents / AI automation / AI coding tools` 扩量组继续稳定出量，应把它们升级为当天主轴
- 若 `AI video` 两组中有一组显著高于平均值，后续应继续偏内容创作 creator 池扩张
- 若 `Hermes Agent` 连续两组低于预期，应保留高质量样本，但不再继续扩该 anchor
- 若 `Sam Altman` 两组仍然偏低，则维持其“高质量补充”定位，不再追加更多批次

### 2.2.15 `Chinese AI KOL - Hermes / OpenClaw / Claude / Codex`

定位：

- 本节用于 `2026-04-16` 中文区 AI KOL discovery。
- 目标是在 X 上挖掘中文 / 华语 AI 工具、AI 编程、AI Agent、效率工作流相关 KOL。
- 今日用户确认关键词锚点为：`Hermes`、`OpenClaw`、`Claude`、`Codex`。
- 今日目标为 `100` 人，执行上限为 `6` 个 batch。
- 继续沿用：
  - `5000+ views`
  - `1000+ followers`
  - 过去 `7` 天
  - discovery master 硬过滤
- 中文区策略不同于英语区：
  - `Codex / Claude` 作为主冲量锚点。
  - `OpenClaw / Hermes` 作为高相关补充锚点。
  - 第 `5-6` 批用中文 AI coding / Agent workflow 大词做 rescue。

执行建议：

- 每个 batch 跑 `3` 个 query，便于比较 query yield 与重合率。
- 若 `Hermes / OpenClaw` 量窄但质量高，保留样本，不继续硬扩同一锚点。
- 若前 `4` 批后 `L3 shortlist >= 80`，第 `5-6` 批偏质量补强。
- 若前 `4` 批后低于 `60`，第 `5-6` 批优先切中文 AI coding / agent workflow 宽词。
- 明显机构号只在 merge 阶段做保守复核，不在 query 阶段用宽泛中文词误杀个人号。

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `Codex Core` | `zh_codex_core` | `"Codex" ("AI 编程" OR "代码智能体" OR "编程智能体" OR "开发者工具" OR "命令行") -crypto -trader -airdrop` | 找中文 Codex / AI coding / developer workflow 讨论者 |
| `Codex Workflow` | `zh_codex_workflow` | `"OpenAI Codex" ("AI 编程" OR "自动写代码" OR "开发工作流" OR "CLI" OR "终端") -crypto -trader -airdrop` | 降低 Codex 泛词歧义，锁定 OpenAI Codex 语境 |
| `Codex Tutorial` | `zh_codex_tutorial` | `"Codex" ("教程" OR "测评" OR "演示" OR "实测" OR "上手") ("AI" OR "编程" OR "开发者") -crypto -trader -airdrop` | 找教程、测评、上手体验型账号 |
| `Claude Code Core` | `zh_claude_code_core` | `"Claude Code" ("AI 编程" OR "代码助手" OR "开发者" OR "终端" OR "IDE") -crypto -trader -airdrop` | 找中文 Claude Code 开发者和重度用户 |
| `Claude Workflow` | `zh_claude_workflow` | `"Claude" ("AI 工作流" OR "AI 自动化" OR "效率工具" OR "知识管理" OR "生产力") -crypto -trader -airdrop` | 找 Claude 知识工作流和生产力账号 |
| `Claude Compare` | `zh_claude_compare` | `"Claude Code" ("对比" OR "测评" OR "替代" OR "Cursor" OR "Codex") -crypto -trader -airdrop` | 找工具选型、对比、购买决策影响者 |
| `OpenClaw Core` | `zh_openclaw_core` | `"OpenClaw" ("AI" OR "AI Agent" OR "智能体" OR "自动化" OR "开发者工具") -crypto -trader -airdrop` | 找 OpenClaw 中文早期传播者 |
| `OpenClaw Demo` | `zh_openclaw_demo` | `"OpenClaw" ("教程" OR "演示" OR "测评" OR "上手" OR "实测") -crypto -trader -airdrop` | 找 OpenClaw 教程、实测、演示账号 |
| `OpenClaw Workflow` | `zh_openclaw_workflow` | `"OpenClaw" ("工作流" OR "自动化" OR "浏览器" OR "桌面" OR "agent") -crypto -trader -airdrop` | 找 OpenClaw agent workflow 和自动化人群 |
| `Hermes Core` | `zh_hermes_core` | `("Hermes" OR "Hermes Agent") ("AI Agent" OR "智能体" OR "自动化" OR "工作流") -crypto -trader -airdrop` | 找 Hermes / Hermes Agent 中文讨论者 |
| `Hermes Agent Demo` | `zh_hermes_agent_demo` | `("Hermes Agent") ("教程" OR "演示" OR "测评" OR "实测" OR "体验") -crypto -trader -airdrop` | 找 Hermes Agent 教程、体验、实测账号 |
| `Hermes Workflow` | `zh_hermes_workflow` | `("Hermes" OR "Hermes Agent") ("工具" OR "用例" OR "workflow" OR "agent" OR "自动化") -crypto -trader -airdrop` | 找 Hermes 工具用例与 workflow 讨论 |
| `AI Coding Stack` | `zh_ai_coding_stack` | `("AI 编程" OR "代码智能体" OR "编程智能体") (Codex OR "Claude Code" OR OpenClaw OR Hermes OR Cursor) -crypto -trader -airdrop` | 用中文 AI coding 大词补量 |
| `Agent Workflow Stack` | `zh_agent_workflow_stack` | `("AI Agent" OR "智能体" OR "Agent 工作流") (Codex OR Claude OR OpenClaw OR Hermes) -crypto -trader -airdrop` | 用中文 agent workflow 大词补量 |
| `Tool Compare Stack` | `zh_tool_compare_stack` | `("AI 工具" OR "AI工具" OR "效率工具") (测评 OR 教程 OR 实测 OR 工作流 OR 自动化) (Claude OR Codex OR OpenClaw OR Hermes) -crypto -trader -airdrop` | 找中文工具测评、教程、效率工具账号 |
| `Rescue Best 1` | `zh_rescue_best_1` | `("AI 编程" OR "AI coding" OR "代码助手") ("Claude Code" OR Codex OR Cursor OR Cline) (教程 OR 测评 OR 工作流 OR 开发者) -crypto -trader -airdrop` | 第 6 批 rescue：AI coding / coding assistant |
| `Rescue Best 2` | `zh_rescue_best_2` | `("AI Agent" OR 智能体 OR "AI智能体") (教程 OR 案例 OR 工作流 OR 自动化 OR 实测) -crypto -trader -airdrop` | 第 6 批 rescue：中文 agent creator 池 |
| `Rescue Best 3` | `zh_rescue_best_3` | `(Claude OR Codex OR OpenClaw OR Hermes) ("独立开发者" OR "产品经理" OR "AI创业" OR "效率工具" OR "自动化") -crypto -trader -airdrop` | 第 6 批 rescue：中文独立开发者和 AI 创业人群 |
| `Rescue Claude Codex Builder` | `zh_rescue_claude_codex_builder` | `("Claude Code" OR Codex OR Cursor) ("AI 编程" OR "开发者" OR "教程" OR "测评") -crypto -trader -airdrop` | 第 6 批 fallback：更短、更稳的 AI coding creator query |
| `Rescue AI Agent Case` | `zh_rescue_ai_agent_case` | `("AI Agent" OR "AI智能体" OR "智能体") ("案例" OR "工作流" OR "教程" OR "自动化") -crypto -trader -airdrop` | 第 6 批 fallback：中文 agent case / workflow creator |
| `Rescue Tool Review` | `zh_rescue_tool_review` | `(Claude OR Codex OR OpenClaw OR Hermes) ("测评" OR "教程" OR "实测" OR "效率工具") -crypto -trader -airdrop` | 第 6 批 fallback：工具测评与教程账号 |
| `Topup Claude Code Workflow` | `zh_topup_claude_code_workflow` | `"Claude Code" ("实战" OR "案例" OR "工作流" OR "自动化" OR "AI Agent") -crypto -trader -airdrop` | 100 人补量：复用高产 Claude Code 方向 |
| `Topup OpenClaw Coding` | `zh_topup_openclaw_coding` | `"OpenClaw" ("Claude" OR "Codex" OR "AI编程" OR "Vibe Coding" OR "独立开发") -crypto -trader -airdrop` | 100 人补量：复用高产 OpenClaw 方向 |
| `Topup AI Coding Creator` | `zh_topup_ai_coding_creator` | `("AI编程" OR "AI 编程" OR "Vibe Coding") ("教程" OR "实战" OR "独立开发" OR "产品") -crypto -trader -airdrop` | 100 人补量：更泛但仍锁定中文 AI coding creator |

建议 batch 分配：

- `Batch 1`: `zh_codex_core`, `zh_codex_workflow`, `zh_codex_tutorial`
- `Batch 2`: `zh_claude_code_core`, `zh_claude_workflow`, `zh_claude_compare`
- `Batch 3`: `zh_openclaw_core`, `zh_openclaw_demo`, `zh_openclaw_workflow`
- `Batch 4`: `zh_hermes_core`, `zh_hermes_agent_demo`, `zh_hermes_workflow`
- `Batch 5`: `zh_ai_coding_stack`, `zh_agent_workflow_stack`, `zh_tool_compare_stack`
- `Batch 6`: first try `zh_rescue_best_1`, `zh_rescue_best_2`, `zh_rescue_best_3`; if provider fails, use `zh_rescue_claude_codex_builder`, `zh_rescue_ai_agent_case`, `zh_rescue_tool_review`
- `Batch 7`: `zh_topup_claude_code_workflow`, `zh_topup_openclaw_coding`, `zh_topup_ai_coding_creator`

运行判断：

- 若 `Batch 1-2` 高产，说明中文区 AI coding / Claude Code 是主轴，第 `5-6` 批继续强化 coding stack。
- 若 `Batch 3-4` 低量但高质量，保留为高相关补充，不继续在窄词上消耗配额。
- 若 `Batch 5` 明显高产，第 `6` 批可以复用其最佳 query 的变体；否则使用已注册 rescue 三组。
- 合并后目标为 `100` 人；若不足 `80`，次轮建议改用 `Cursor / Manus / Gemini / AI编程 / AI智能体 / 独立开发者` 扩池。

### 2.2.16 `AI Hot Terms 6 Batch - 2026-04-17`

定位：

- 本节用于 `2026-04-17` 的 X KOL discovery 正式执行。
- 今日目标为合并后 `60` 人，执行上限为 `6` 个 batch。
- 用户确认关键词锚点为：`AI 热词`、`Claude Code`、`Codex`、`OpenClaw`、`小龙虾`、`Hermes`。
- 今日阈值从历史默认值调整为：
  - `3000+ views`
  - `1000+ followers`
  - 最近 `14` 天
  - discovery master 硬过滤
- 搜索策略是 `hot-post-led KOL mining`，优先保留个人 creator / builder / engineer / founder / researcher / workflow account，明显机构号在 merge 后复核移除。

执行建议：

- 每个 batch 跑 `3` 个 query，便于从窄词与宽词之间平衡出量。
- `AI 热词` 和 `Claude Code / Codex` 作为主冲量轴。
- `OpenClaw / Hermes / 小龙虾` 作为高相关补充轴，如出量窄但质量高则保留样本，不继续硬扩。
- 若前 `4` 批净新增不足 `40`，第 `5-6` 批允许用更泛的 AI coding / agent workflow query rescue。

| Matrix Group | Query Name | Planned Query Text | Use |
| --- | --- | --- | --- |
| `AI Hot Broad` | `ai_hot_terms_builder_signal_20260417` | `("AI agent" OR "AI agents" OR "vibe coding" OR "coding agent" OR "AI automation") (builder OR creator OR engineer OR founder OR workflow OR tutorial OR demo OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 主冲量：抓 AI agent / vibe coding / coding agent 近期热帖背后的个人账号 |
| `AI Hot Workflow` | `ai_hot_terms_workflow_signal_20260417` | `("AI workflow" OR "AI automation" OR "agent workflow" OR "AI tools") (tutorial OR demo OR usecase OR "case study" OR productivity OR creator) -crypto -trader -airdrop -news -media -official -brand -company` | 抓 workflow / automation / use-case 型 creator |
| `AI Hot Devtools` | `ai_hot_terms_devtools_signal_20260417` | `("AI devtools" OR "developer tools" OR "AI coding tools" OR "coding agents") (builder OR engineer OR shipped OR stack OR demo OR tutorial) -crypto -trader -airdrop -news -media -official -brand -company` | 抓 devtools / coding tools / stack 视角账号 |
| `Claude Code Core` | `claude_code_core_signal_20260417` | `"Claude Code" (builder OR engineer OR creator OR developer OR tutorial OR demo OR workflow OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 找 Claude Code 真实使用者、教程和工作流分享者 |
| `Claude Code Compare` | `claude_code_compare_signal_20260417` | `"Claude Code" (Codex OR Cursor OR Cline OR "coding agent" OR "vibe coding") (compare OR review OR workflow OR tutorial OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 找工具对比、购买决策和替代方案影响者 |
| `Claude Code Chinese` | `claude_code_zh_signal_20260417` | `"Claude Code" ("AI 编程" OR "代码助手" OR "开发者" OR "教程" OR "测评" OR "工作流" OR "实战") -crypto -trader -airdrop` | 捕捉中文 / 双语 Claude Code creator |
| `Codex Core` | `codex_core_signal_20260417` | `("OpenAI Codex" OR Codex) ("AI coding" OR "coding agent" OR developer OR terminal OR CLI OR workflow OR tutorial OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 找 OpenAI Codex / coding agent 实操讨论者 |
| `Codex Builder` | `codex_builder_signal_20260417` | `(Codex OR "OpenAI Codex") (builder OR engineer OR founder OR shipped OR stack OR "build in public" OR "devtools") -crypto -trader -airdrop -news -media -official -brand -company` | 抓工程实践、build-in-public、开发者工具账号 |
| `Codex Chinese` | `codex_zh_signal_20260417` | `(Codex OR "OpenAI Codex") ("AI 编程" OR "自动写代码" OR "开发工作流" OR "教程" OR "测评" OR "实测") -crypto -trader -airdrop` | 捕捉中文 / 双语 Codex 讨论者 |
| `OpenClaw Core` | `openclaw_core_signal_20260417` | `"OpenClaw" (AI OR agent OR automation OR "developer tools" OR builder OR demo OR tutorial OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 找 OpenClaw 早期传播者和实操账号 |
| `OpenClaw Workflow` | `openclaw_workflow_signal_20260417` | `"OpenClaw" (workflow OR automation OR browser OR desktop OR agent OR usecase OR demo OR tutorial) -crypto -trader -airdrop -news -media -official -brand -company` | 找 OpenClaw workflow / browser automation 人群 |
| `OpenClaw Chinese` | `openclaw_zh_signal_20260417` | `"OpenClaw" ("AI Agent" OR "智能体" OR "自动化" OR "教程" OR "测评" OR "工作流" OR "实测") -crypto -trader -airdrop` | 捕捉中文 / 双语 OpenClaw 账号 |
| `Xiaolongxia Core` | `xiaolongxia_core_signal_20260417` | `("小龙虾") ("AI" OR "AI 编程" OR "智能体" OR "Claude Code" OR Codex OR OpenClaw OR Hermes) -crypto -trader -airdrop` | 用小龙虾锚点捕捉中文圈相关讨论，避免纯生活噪音 |
| `Xiaolongxia Coding` | `xiaolongxia_coding_signal_20260417` | `("小龙虾") ("教程" OR "测评" OR "工作流" OR "开发者" OR "独立开发" OR "效率工具") ("AI" OR Claude OR Codex OR Cursor) -crypto -trader -airdrop` | 进一步锁定 AI coding / workflow 语境 |
| `Chinese AI Coding Rescue` | `zh_ai_coding_rescue_signal_20260417` | `("AI 编程" OR "AI coding" OR "代码智能体" OR "编程智能体") ("Claude Code" OR Codex OR Cursor OR OpenClaw OR Hermes) ("教程" OR "测评" OR "工作流" OR "开发者") -crypto -trader -airdrop` | 小龙虾低产时的中文 AI coding rescue |
| `Hermes Core` | `hermes_core_signal_20260417` | `("Hermes" OR "Hermes Agent") ("AI agent" OR agent OR automation OR workflow OR builder OR demo OR tutorial OR review) -crypto -trader -airdrop -news -media -official -brand -company` | 找 Hermes / Hermes Agent 英文与双语讨论者 |
| `Hermes Workflow` | `hermes_workflow_signal_20260417` | `("Hermes Agent" OR Hermes) (workflow OR stack OR orchestration OR usecase OR automation OR tutorial OR demo) -crypto -trader -airdrop -news -media -official -brand -company` | 抓 Hermes workflow / orchestration 账号 |
| `Hermes Chinese` | `hermes_zh_signal_20260417` | `("Hermes" OR "Hermes Agent") ("AI Agent" OR "智能体" OR "自动化" OR "工作流" OR "教程" OR "实测") -crypto -trader -airdrop` | 捕捉中文 / 双语 Hermes 讨论者 |

建议 batch 分配：

- `Batch 1`: `ai_hot_terms_builder_signal_20260417`, `ai_hot_terms_workflow_signal_20260417`, `ai_hot_terms_devtools_signal_20260417`
- `Batch 2`: `claude_code_core_signal_20260417`, `claude_code_compare_signal_20260417`, `claude_code_zh_signal_20260417`
- `Batch 3`: `codex_core_signal_20260417`, `codex_builder_signal_20260417`, `codex_zh_signal_20260417`
- `Batch 4`: `openclaw_core_signal_20260417`, `openclaw_workflow_signal_20260417`, `openclaw_zh_signal_20260417`
- `Batch 5`: `xiaolongxia_core_signal_20260417`, `xiaolongxia_coding_signal_20260417`, `zh_ai_coding_rescue_signal_20260417`
- `Batch 6`: `hermes_core_signal_20260417`, `hermes_workflow_signal_20260417`, `hermes_zh_signal_20260417`

运行判断：

- 若 `AI Hot / Claude Code / Codex` 三组已达到 `60` 人目标，后续窄词批次作为质量补充，不再追加 topup。
- 若 `OpenClaw / Hermes / 小龙虾` 低量但命中高相关个人账号，保留进入 S2 review，不因为低量自动 drop。
- 合并后若不足 `60`，下一轮优先从 `AI coding / coding agent / vibe coding / Cursor / Cline` 扩池。
