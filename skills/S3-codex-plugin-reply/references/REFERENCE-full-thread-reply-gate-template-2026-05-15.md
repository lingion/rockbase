# REFERENCE Full Thread Reply Gate Template

## Purpose

这份模板不是给脚本用的。

它是给当前执行 reply draft 的大模型用的，目的是强制每封候选回复在写正文前，先完成：

1. `thread synopsis`
2. `scenario decision`
3. `reply self-check`

只要这 3 个产物没有先完成，就不算真正完成了 full-thread reasoning。

## Non-Negotiable Rule

下面这些内容必须基于当前模型亲自读完整 thread 后得出：

- 我方最初 outbound
- 对方最新 inbound
- 中间关键往返
- 价格轮次
- 当前 operator goal

禁止用下面这些东西替代阅读：

- latest inbound 单封内容
- Gmail 列表页 snippet
- 插件摘要
- master 里的 `Reply_Stage`、`latest_price_*`、`current_price_summary`
- 别的脚本或上一次运行留下的二手总结

## Required Output Skeleton

每封候选 reply，进入 draft 前至少先写出下面结构。

### 1. Thread Synopsis

```md
Thread Synopsis
- Initial outbound:
- Latest inbound:
- Intervening negotiation:
- Current round:
- Known constraints:
- Operator goal:
```

字段说明：

- `Initial outbound`
  我方第一封真正说了什么，是否已经发过 brief / pricing ask / deliverable ask。
- `Latest inbound`
  对方最近一封真正回复了什么，问题、条件、价格、推迟、拒绝、转介绍都写清。
- `Intervening negotiation`
  中间若发生过多轮来回，必须交代价格、scope、timeline、bundle、manager/creator 分工等关键变化。
- `Current round`
  明确这是 fresh reply、first quote、second round、follow-up、closing，还是 waiting state。
- `Known constraints`
  thread 中已经明确给出的限制条件，例如预算、交付形式、国家限制、发布时间、必须先看 brief、只能对接 manager。
- `Operator goal`
  这封回复的唯一主目标是什么，例如压第一轮报价、继续索取 usable rate、确认 scope 后再压价、先保温、先要 media kit。

### 2. Scenario Decision

```md
Scenario Decision
- Pricing state:
- Intent state:
- Operator goal:
- Template code:
- Why not other scenarios:
```

字段说明：

- `Pricing state`
  例如：`no_rate_yet` / `first_quote_received` / `second_round_negotiation` / `quoted_waiting_scope` / `not_pricing_related`
- `Intent state`
  例如：`interested` / `pricing_only` / `needs_details` / `soft_no` / `handoff_to_manager` / `waiting`
- `Operator goal`
  这里必须和上面的 synopsis 对齐，不能飘。
- `Template code`
  必须先选模板，再写正文。
- `Why not other scenarios`
  必须用一句话解释，为什么它不是别的常见场景。这个字段是防止“明明第二轮却按第一轮回”。

### 3. Draft Plan

```md
Draft Plan
- Opening move:
- Main ask or negotiation move:
- Supporting detail:
- Tone guardrail:
- Naming guardrail:
```

字段说明：

- `Opening move`
  开头先做什么，比如 acknowledge、delay softener、brief acknowledgment。
- `Main ask or negotiation move`
  本封真正推进动作是什么。
- `Supporting detail`
  允许加的 supporting context，例如短预算锚点、test framing、deliverable clarification。
- `Tone guardrail`
  避免太硬、太软、太像 fresh cold outreach、太像模板腔。
- `Naming guardrail`
  如果 thread 里 creator / manager / channel 名称不清楚，这里要先写明保守称呼策略。

### 4. Reply Self-Check

```md
Reply Self-Check
- Responds to latest inbound: yes / no
- Matches pricing round: yes / no
- Carries forward key constraints: yes / no
- No scenario drift: yes / no
- Clean body only: yes / no
- Ready for draft upload: yes / no
```

任何一项不是 `yes`，都不能上传 draft。

## Pass / Fail Standard

### Pass

只有满足以下条件才算 pass：

- 当前模型已经读完整 thread
- 已写 `thread synopsis`
- 已写 `scenario decision`
- 已写 `draft plan`
- 已写 `reply self-check`
- `reply self-check` 全部为 `yes`

### Fail

以下任一情况直接视为 fail：

- 只复述 latest inbound
- 没交代中间价格往返
- 没说明当前是第几轮
- 没说明为什么不用其他 scenario
- 正文和 `operator goal` 不一致
- 明明是 manager thread，却把人名或关系叫错
- 直接把旧 quoted history 粘进新正文

## Recommended Minimal Runtime Record

如果是 live 批量执行，至少要把下面 3 段保存在运行记录、manifest 注释、或 review note 中：

1. `Thread Synopsis`
2. `Scenario Decision`
3. `Reply Self-Check`

这样后面复盘时，能快速判断这封 draft 是不是基于完整 thread 理解而写出来的。
