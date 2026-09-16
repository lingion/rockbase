# WF Daily Automation Loop

## Purpose

把 `S3-codex-plugin-reply` 从“扫新回复并尝试起草”的工具，升级成一条稳定的 ReplyOps dispatcher。

每日循环目标：

1. 扫 Gmail inbox
2. 扫 unresolved threads
3. 做 dispatcher gates
4. 把 thread 分流到正确队列
5. 只对高置信 case 进入 draft
6. 输出 summary 给 Steve

## North Star

每天自动完成：

1. 区分普通办公 / 噪音 / outreach / workstream
2. 区分 `auto_reply / steve_handle / manual_review`
3. 找到真正需要我方回复的 thread
4. 补捞历史漏回 thread
5. 更新价格、阶段、附件状态
6. 生成高置信 reply drafts
7. 给 Steve 一份可信 summary

## Run Modes

### Mode A: daily inbox sweep

用途：

- 发现最近 24h - 72h 的新回复
- 快速 triage

### Mode B: unresolved thread sweep

用途：

- 不依赖今天是否新进 inbox
- 专门抓最新整体消息来自对方、但尚未被我们回复的 thread

这条分支是修复“明明需要回复却漏掉”的核心。

## Core Execution Principle

### Model-first judgment, script-first execution

大模型负责：

- relevance
- ownership
- need-reply
- pricing round
- usable price
- `Next_Reply_Action`

脚本负责：

- 时间窗扫描
- 队列落盘
- OCR 调用
- Gmail draft 写入
- CSV / summary 写回

## Daily Loop

### Step 1. Read checkpoint

读取：

- `output/automation_checkpoint.json`

确定今天跑：

- inbox sweep
- unresolved sweep
- 或两者都跑

### Step 2. Scan inbox

优先扫描最近 24h - 72h。

先做：

- `A1_outreach_reply`
- `A2_workstream_execution`
- `A3_system_or_noise`
- `A4_unknown_manual_review`

### Step 3. Scan unresolved threads

从 master 或 thread 锚点侧再扫一遍：

- `Ownership = auto_reply`
- thread 未 closed
- 最新消息来自对方
- 我方没有在其后回复

命中后直接进入：

- `missed_reply_queue`
- 或重新回到完整 thread refresh

### Step 4. Build reply intelligence

只对 relevant threads 继续：

1. 判断 ownership
2. 判断 need-reply
3. 判断有无 usable 价格
4. 判断价格来自正文、附件、或两者
5. 判断下一步动作：
   - `draft_queue`
   - `missed_reply_queue`
   - `ocr_queue`
   - `contact_update_queue`
   - `manual_review`
   - `excluded`

### Step 5. OCR branch

若附件决定价格或合作条件：

- 进入 `ocr_queue`

若正文已有清晰价格：

- 正文价格先入主真相层
- OCR 状态保留为证据补强

### Step 6. Shadow master writeback

优先写：

- `workbench/{YYYY-MM-DD}/...shadow...csv`

建议最低写回字段：

- `Reply_Ownership`
- `Need_Reply_State`
- `Latest_Thread_Speaker`
- `Current_Reply_Scenario`
- `Next_Reply_Action`
- `Attachment_OCR_Status`
- `latest_price_*`
- `Pricing_Round`
- `current_price_summary`

### Step 7. Draft branch

只有这些 case 才进入 draft：

- outreach reply
- ownership 明确是 `auto_reply`
- `Need_Reply_State = reply_needed_from_us`
- 最新整体消息来自对方
- 当前不属于 `ocr_first / update_contact_only / manual_review / stale_thread_refresh_required`

### Step 8. Summary

每天 summary 至少要包含：

1. 扫了多少封
2. 命中多少条 outreach thread
3. `draft_queue` 多少条
4. `missed_reply_queue` 多少条
5. `ocr_queue` 多少条
6. `manual_review` 多少条
7. `contact_update_queue` 多少条
8. 最重要的 3 - 5 条发现

## Promotion Rule

需要回复但因 thread stale 还不能直接 draft 的 case，不得沉底。

必须显式进入：

- `missed_reply_queue`

这个队列的目的不是永远挂起，而是提醒系统：

- 需要 refresh thread
- 需要重建 context
- 需要尽快补回

## Go Live Rule

只有当以下稳定后，才切 live：

1. ownership 稳定
2. need-reply 稳定
3. missed-reply surfacing 稳定
4. OCR merge 稳定
5. draft gate 稳定
6. summary 稳定
