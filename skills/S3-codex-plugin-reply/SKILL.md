---
name: s3-codex-plugin-reply
description: Use when handling Rockbase Gmail reply operations for KOL outreach, especially when you need to separate default price recovery from later-stage price negotiation, decide whether a thread belongs in ReplyOps at all, and sync grounded reply state back to S3 master.
---

# S3-codex-plugin-reply

## Purpose

这个 skill 现在要解决的，不只是“怎么写 reply”。

它要先解决另外一个更关键的问题：

> `默认拿价` 和 `后续压价` 不能混成一条 workflow。

新的定位是：

> `ReplyOps dispatcher + two-track reply system`

也就是把可回复 case 明确分进两条独立 workflow：

- `WF-1-Price-Recovery-Default.md`
- `WF-2-Price-Negotiation-Followup.md`

## Default Mode

默认模式是：

- `WF-2 disabled by default`

也就是：

- 默认只运行 `WF-1`
- `WF-2` 只有在 Steve 明确指定时才允许启用

如果用户没有明确说：

- `开启 WF2`
- `这批开始压价`
- `进入 negotiation mode`

则一律不得自动进入 `WF-2`。

## Runtime Entry And Account

- `S3-codex-plugin-reply` 是 S3 ReplyOps 的唯一直接运行入口。
- `S3-ag-reply-recovery-sync-v3` 与 `S3-ag-reply-draft-ops` 只作为本 skill 按队列调度的能力层，不单独启动完整任务。
- 默认 Gmail 账户是 `<YOUR_ACCOUNT_EMAIL>`；脚本必须使用该账户的 OAuth token，不得回退到历史账户默认值。
- 正式主表固定为 `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`。
- 本 skill 中的 `legacy-recovery-sync-v3` 和 `legacy-reply-draft-ops` 目录是内部兼容实现；只能由本 skill 调用，不能作为独立入口。

## Core Upgrade

旧理解的问题在于：

- 把“问价 / 拉报价 / 解释我们是谁”与“压 first-collab rate / 继续谈 starter option”写进同一套路
- 结果正文会同时承担两个目标，读起来像在拧巴地套话

新的理解：

- 先判断这条 thread 是否归 ReplyOps 管
- 再判断它是否真的需要回复
- 再判断它当前属于：
  - `price_recovery_default`
  - `price_negotiation_followup`
- 最后才进入对应的 full-thread draft

一句话：

> 先解决 “这条该不该管”，再解决 “这一轮到底是在拿价，还是在压价”。

## When To Use

优先用于这些场景：

- 需要扫描 Gmail inbox，区分 KOL outreach reply 与普通办公邮件
- 需要把 thread 分配为：
  - `auto_reply`
  - `steve_handle`
  - `workstream`
  - `ignore`
  - `manual_review`
- 需要判断某条 thread 当前是否真的需要我方回复
- 需要补捞“应该回复但没进 draft 队列”的 missed replies
- 需要基于完整 thread 起草 `Mail2+` 回复
- 需要优先把“没拿到 usable quote”的 thread 拉回到价格回收流程
- 需要只在后续轮次中执行压价 / starter-option negotiation
- 需要把 reply 阶段、价格状态、ownership、need-reply 状态同步回 S3 master

## Read Order

1. 本 `SKILL.md`
2. 若存在，先读 `output/wf1_latest_resume.md`
3. 若存在，再读 `output/wf1_latest_checkpoint.json`
4. `references/FILTERING-STRATEGY-2026-05-06.md`
5. `references/REFERENCE-full-thread-reply-gate-template-2026-05-15.md`
6. `WF-1-Price-Recovery-Default.md`
7. `references/REFERENCE-price-recovery-reply-framework-2026-05-20.md`
8. `WF-2-Price-Negotiation-Followup.md`
9. `references/REFERENCE-price-negotiation-reply-framework-2026-05-20.md`
10. `doc/WF_Gmail-Plugin-Reply-Auto-Draft.md`
11. `doc/WF_Daily-Automation-Loop-2026-05-08.md`
12. `doc/V3-FIELD-MAPPING-2026-05-07.md`

## Latest Pointer Rule

以后运行这个 skill 时，不应该靠用户提醒“上次看到哪里”。

固定要求：

1. 如果 `output/wf1_latest_resume.md` 存在，先读它
2. 如果 `output/wf1_latest_checkpoint.json` 存在，再读它
3. 只有在这两个文件都不存在，或明确失真时，才允许退回日期目录手工翻 `workbench/{YYYY-MM-DD}/...`

一句话：

> `output/` 里的 pointer files 是默认入口，`workbench/{date}` 只是归档层。

## Scan Direction Rule

扫描方向固定如下：

1. 永远从当前 Gmail INBOX 顶部开始
2. 按时间从新到旧往回扫
3. 一直扫到上一次确认的 stop point
4. 接上 stop point 后才允许继续更老历史

禁止：

1. 把旧 checkpoint 当成新的起点往未来扫
2. 先钻 page-deep history，再回头补今天顶部
3. 混用“上次开始点”和“上次结束点”

统计口径也要分开：

1. 今日新检测到报价 thread 数
2. 今日新写回本地 master 的价格数
3. 今日新进入回复队列 / 草稿队列数
4. 今日新写回 Feishu 的价格数

## Dispatcher Gates

所有 thread 进入 draft 之前，必须先过 4 个 gate。

### Gate 1. Relevance

先分：

- `A1_outreach_reply`
- `A2_workstream_execution`
- `A3_system_or_noise`
- `A4_unknown_manual_review`

不是 `A1_outreach_reply` 的，不进入 auto-draft。

### Gate 2. Ownership

每条相关 thread 都要先落一个稳定 ownership：

- `auto_reply`
- `steve_handle`
- `workstream`
- `ignore`
- `manual_review`

没有 ownership 的 thread，不允许假装进入 auto-draft。

### Gate 3. Need Reply

不是“对方来信了就回复”。

必须先回答：

- 最新整体消息是谁发的
- 对方最近这封有没有给出新的 ask / quote / redirect / condition
- 我方是否已经在对方最后一封之后回过

推荐状态：

- `reply_needed_from_us`
- `no_reply_needed_latest_outbound_ours`
- `contact_update_only`
- `closed_no_reply_needed`
- `unclear_manual_review`

### Gate 4. Confidence

需要回复，不等于适合自动起草。

动作层只允许落到：

- `draft_queue`
- `missed_reply_queue`
- `ocr_queue`
- `contact_update_queue`
- `manual_review`
- `excluded`

## Draft Rules

只有同时满足下面条件，才允许进入 draft：

1. `Relevance = A1_outreach_reply`
2. `Ownership = auto_reply`
3. `Need_Reply_State = reply_needed_from_us`
4. 最新整体消息来自对方，而不是我方
5. 不属于 `ocr_first / update_contact_only / manual_review`
6. 当前模型已读完整 thread，并先写：
   - `Thread Synopsis`
   - `Scenario Decision`
   - `Draft Plan`
   - `Reply Self-Check`
7. 当前 workflow 已明确为：
   - `price_recovery_default`
   - 或 `price_negotiation_followup`

## Two Workflow Contract

### WF 1. Price Recovery Default

这是默认 workflow。

适用于：

- 对方还没给 usable quote
- 对方只发了 media kit / channel links / vague interest
- 对方先问我们公司、品牌、brief、合作方式
- 对方报价信息不完整，仍需追问 deliverable / format / platform / usage

这条 workflow 的主目标是：

- 把所有价格拉回本地
- 追到 usable quote
- 必要时给最小充分的 Rockbase / brand context
- 不提前进入压价

### WF 2. Price Negotiation Followup

这是第二条 workflow，不是默认 workflow。

只在下面情况使用：

- 已经拿到 usable quote
- 价格结构已经够清晰，可以进入下一轮推进
- 当前这封的主要目标已经不是继续索价，而是压价 / 拆 starter option / 要更优 first-collab 结构

这条 workflow 的主目标是：

- 压价
- 拿 first-collab / agency rate
- 把同价交付做大或把过大 bundle 拆小
- 将报价推进到更适合 first test 的起点

## WF-2 Activation Rule

`WF-2` 必须满足两个条件才允许运行：

1. thread 本身已经满足 negotiation entry gate
2. Steve 在当前任务里明确指定要启用 `WF-2`

缺少任一条件，都必须留在：

- `WF-1`
- 或 `workstream`

## Missed Reply Principle

这个 skill 必须具备“补捞漏回”的能力。

不能只扫“今天的新邮件”。

还要每天显式检查：

- thread 仍归 `auto_reply`
- 最新消息来自对方
- 我方尚未在其后回复
- 当前仍未 closed

这类 thread 即使不在最新 inbox snippet 里，也必须进入：

- `missed_reply_queue`

## Resume And Dedupe Rule

以后任何 `WF-1` inbox tranche 都必须同时留下：

1. 归档产物
   - `workbench/{YYYY-MM-DD}/wf1_gmail_review/...`
2. 固定指针
   - `output/wf1_latest_resume.md`
   - `output/wf1_latest_checkpoint.json`

去重与续跑硬规则：

1. 主键使用 `Reply_Thread_ID`
2. 刷新键使用 `Latest_Inbound_Message_ID`
3. 同 `Reply_Thread_ID` 且同 `Latest_Inbound_Message_ID` = 重复
4. 同 `Reply_Thread_ID` 但 `Latest_Inbound_Message_ID` 更新 = 同线程刷新，不算重复
5. 禁止只靠 `subject` 或 `sender` 做续跑判断

## Core Rules

1. 必须先看完整 thread，而不是只看 latest message。
2. 起草前必须先产出 `thread synopsis` 和 `scenario decision`。
3. 只要 thread 中已经拿到可写回本地的报价，优先先写回本地。
4. 默认 workflow 是 `price_recovery_default`，不是 `price_negotiation_followup`。
5. `WF-2` 默认关闭，只有 Steve 明确指定时才允许启用。
6. 只有已经拿到 usable quote 且 Steve 明确指定时，才允许切到 negotiation workflow。
7. 第一轮拿到报价后，不允许机械套用固定压价文案；先判断当前运营目标是不是继续补齐价格结构，还是已经可以进入谈价。
8. 第二轮报价不能装作第一轮。
9. 回复正文只写新增内容，不手工拼 quoted history。
10. 若距离对方上一封 inbound 超过两天，默认加入 delay softener。
11. 联系人或 creator / manager 身份不清时，正文命名必须保守。
12. Gmail 草稿上传前必须实时刷新完整 thread；若当前 latest inbound 已变，旧 draft 作废重建。
13. 若我方最新 outbound 已晚于对方最近 inbound，则必须标记 `no_reply_needed_latest_outbound_ours`，不得重复起草。
14. `unknown` 不得沉底，必须进入显式 `manual_review` 或 `missed_reply_queue`。

## Relationship To Other S3 Skills

- `S3-ag-reply-recovery-sync-v3`
  - thread / attachment recovery
  - OCR
  - 价格证据层
  - writeback 主协议

- `S3-ag-reply-draft-ops`
  - reply 模板与历史场景

- `S3-codex-plugin-reply`
  - inbox triage
  - ownership
  - need-reply detection
  - missed-reply surfacing
  - thread-aware draft gating
  - Gmail plugin read + local OAuth draft writeback

## Current Goal

把 reply 流程升级成：

`inbox scan + unresolved scan -> dispatcher gates -> WF-1 or WF-2 full-thread judgment -> draft / OCR / contact update / manual review -> master sync`
