# Filtering Strategy

日期：2026-05-06

## 目标

这份策略现在回答 3 个问题：

1. 这封邮件是不是 ReplyOps 应该接管的 thread
2. 如果相关，它归谁处理
3. 如果归 auto-reply，它现在到底需不需要回复

重点已经从“先套模板”改成：

> 先把 thread 调度做稳，再决定要不要 draft。

## 四层过滤

### Step A：相关性过滤

先分：

- `A1_outreach_reply`
- `A2_workstream_execution`
- `A3_system_or_noise`
- `A4_unknown_manual_review`

只有 `A1_outreach_reply` 才进入 ReplyOps 主流程。

### Step B：归属过滤

相关 thread 还不够，必须再判断 ownership：

- `O1_auto_reply`
- `O2_steve_handle`
- `O3_workstream`
- `O4_ignore`
- `O5_manual_review`

判定思路：

#### `O1_auto_reply`

- thread 明确仍处在 outreach / pricing / brief / verification 阶段
- 回应目标比较清晰
- 不需要 Steve 亲自接手的人情或复杂判断

#### `O2_steve_handle`

- 需要 Steve 亲自判断关系或策略
- 语气、背景、隐含上下文过于个性化
- 明显是你自己想保留手感处理的 thread

#### `O3_workstream`

- 已进入执行
- 主题是交付、排期、链接替换、素材、脚本、rough cut、上线

#### `O4_ignore`

- 系统噪音
- 低价值通知
- 与当前业务推进无关

#### `O5_manual_review`

- 身份混乱
- thread 太短
- 相关但归属不清

### Step C：是否需要回复

这是旧流程最容易漏掉的一层。

推荐字段：

- `reply_needed_from_us`
- `no_reply_needed_latest_outbound_ours`
- `contact_update_only`
- `closed_no_reply_needed`
- `unclear_manual_review`

判定必须回答：

1. 最新整体消息是谁发的
2. 对方最近 inbound 有没有新的 ask / quote / redirect / constraint
3. 我方是否已经在那之后回过

如果我方最后一封整体消息晚于对方最近 inbound：

- 直接落 `no_reply_needed_latest_outbound_ours`

如果对方只是给了新联系人或让我们改邮箱：

- 落 `contact_update_only`

### Step D：动作过滤

最后才决定动作：

- `draft_queue`
- `missed_reply_queue`
- `ocr_queue`
- `contact_update_queue`
- `manual_review`
- `excluded`

## 新增：Missed Reply Surface

不能只扫 inbox 新消息。

还要补一层：

> 哪些 thread 其实还没闭环，但因为时间窗、字段缺失、或前次 triage 漏判，没有进入 draft queue。

这类 thread 统一进入：

- `missed_reply_queue`

典型命中条件：

- `Ownership = auto_reply`
- `Need_Reply_State = reply_needed_from_us`
- 最新消息来自对方
- 当前 `Next_Reply_Action = stale_thread_refresh_required` 或等价状态

## 为什么这比旧方法稳

旧方法更像：

- 先扫邮箱
- 先猜是不是相关
- 很快进入 draft

新方法更像：

- 先做 relevance
- 再做 ownership
- 再做 need-reply
- 再做 confidence/action routing

所以它能更稳地解决两类痛点：

1. 不该你参与的 thread 被卷进来
2. 明明该回的 thread 却漏掉

## 最低执行要求

每次跑批至少要留下这些结果：

- relevance label
- ownership label
- need-reply state
- action queue
- queue reason

没有这些中间判断，就不算可审计的 ReplyOps 执行。
