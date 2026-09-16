# WF 2 — Price Negotiation Followup

日期：2026-05-20

## Purpose

这条 workflow 专门处理：

- 已经拿到 usable quote 之后
- 如何继续压价
- 如何把报价改造成更适合 first test 的结构

它不是默认 workflow。

它默认是关闭的。

只有在 Steve 明确指定当前任务要启用 `WF-2` 时，才允许使用。

## End-To-End Contract

以后如果目标就是谈价，直接运行 `WF-2`。

不需要先跑额外前置 workflow。

`WF-2` 自己内部就包含：

1. capture thread evidence
2. full-thread review
3. negotiation entry gate
4. negotiation angle selection
5. local writeback check
6. draft decision
7. negotiation draft writing

一句话：

> `WF-2` 本身就是一条完整 workflow。

## Latest Pointer Rule

即使当前要运行的是 `WF-2`，默认也先看：

1. `output/wf1_latest_resume.md`
2. `output/wf1_latest_checkpoint.json`

原因很简单：

- 多数 `WF-2` case 都是从 `WF-1` 的已拿价 thread 升上来
- 如果不先看最新 pointer，很容易重复判断已经处理过的 thread

## Script vs LLM Contract

这条 workflow 也采用相同边界：

- `脚本 = 拉取 / 证据整理 / 写回 / draft 上传`
- `LLM = entry gate / angle judgment / negotiation drafting`

脚本不应该直接决定：

- 是否已经适合进入谈价
- 该走哪种 negotiation angle
- 应该压到哪里

这些必须由 LLM 基于完整 thread 来做。

## Entry Gate

只有满足下面条件，才允许进入这条 workflow：

1. 已经拿到 usable quote
2. 价格信息已经足够清楚，可以写回本地
3. 当前这一轮的核心问题已经不再是“报价有没有”，而是“报价怎么推进”
4. Steve 已明确指定启用 `WF-2`

如果还没满足，就退回：

- `WF-1-Price-Recovery-Default.md`

## Capture And OCR Gate

`WF-2` 也必须先读完整 thread。

默认顺序：

1. 先抓完整 thread
2. 先确认最新整体消息来自谁
3. 先确认价格是否已经 usable
4. 如价格主要在附件里，先进入 `ocr_first`

硬规则：

- 附件价格未恢复完成前，不允许直接起 negotiation draft
- 没有清晰价格写回基础时，不允许直接进入 `WF-2`

## Main Goals

这条 workflow 的主目标只能是下面几类之一：

1. 压 first-collab / agency rate
2. 要 starter option
3. 拆大 bundle
4. 问 single-unit option
5. 在不直接拒绝的情况下把价格推进到可测试区间

## Core Rule

这条 workflow 才允许压价。

也就是说：

- `压价` 不是 reply skill 的默认动作
- `压价` 是拿到 usable quote 之后的独立动作

## Writeback-Ready Rule

`WF-2` 的共通规则是：

- 先确认本地真相层已经足够完整
- 再进入 negotiation draft

最低要求：

- `latest_price_raw`
- `latest_price_normalized`
- `current_price_summary`
- `Pricing_Round`
- `Current_Reply_Scenario`
- `Next_Reply_Action`

如果这些还不稳，先回到 `WF-1` 补齐。

## Standard Negotiation Angles

### Angle 1. First-Test Framing

适用于价格偏高，但 thread 还值得推进。

核心表达：

- first collaboration
- lighter starting point
- initial test
- shortlist review range

### Angle 2. Starter Option Extraction

适用于对方给的是大 bundle 或高配方案。

核心动作：

- 追问 smaller unit
- 追问 single-platform option
- 追问 single-video option

### Angle 3. Scope Recut

适用于对方价格不一定能降，但 scope 可以重新切。

核心动作：

- 去 usage
- 去 repost
- 去 bundle
- 缩 deliverable

## Standard Judgment Order

每次起草 `WF-2` 时，固定按这个顺序判断：

1. `thread 是否归 ReplyOps 管`
2. `最新整体消息是不是对方发的`
3. `这条 thread 现在需不需要回`
4. `是否仍有 ocr / 价格恢复缺口`
5. `usable quote 是否已经足够清晰`
6. `为什么这轮已经不是 WF-1`
7. `当前适合 first-test / starter-option / scope-recut 哪条角度`
8. `这封发出去后，是要拿更低价，还是拿更小起步方案`

这 `1-8` 步属于 `WF-2` 的核心判断层，默认由 LLM 主导。

## Non-Goal

这条 workflow 不负责：

- 第一次拿报价
- 纯追价
- 纯解释 Rockbase 背景

这些都属于：

- `WF-1-Price-Recovery-Default.md`

## Writeback Standard

这条 workflow 必须在本地已经有清晰价格记录后再运行。

推荐状态：

- `Pricing_Round = first_quote / requote / discounted_quote`
- `Current_Reply_Scenario = price_negotiation_followup`
- `Next_Reply_Action = negotiate_first_test / request_starter_option / compare_internal_then_reply`

## Output Contract

每封候选回复在正文前，至少先写：

1. `Thread Synopsis`
2. `Scenario Decision`
3. `Draft Plan`
4. `Reply Self-Check`

其中 `Scenario Decision` 必须明确写：

- `Workflow = price_negotiation_followup`
- `Negotiation angle = first-test / starter-option / scope-recut`
- `Judgment owner = LLM full-thread review`
