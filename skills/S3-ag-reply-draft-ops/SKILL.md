---
name: ag-reply-draft-ops
description: 当用户要基于 `【S3 ReplyOps】Corestar-Replied-KOL.csv` 的回复结果，给每条 thread 映射共享回复模板、生成 `Mail2 / Mail3` 正文、在原 thread 内创建 Gmail reply drafts、并回写 draft 状态时使用。不负责重新抓 Gmail 回复。
---

# Reply Draft Ops

## 调用边界

- 本 skill 只接收 `S3-codex-plugin-reply` 已完成 dispatcher gate 的 `draft_queue`。
- 不单独扫描收件箱，也不直接接管完整 ReplyOps 任务。
- 默认 Gmail 账户为 `<YOUR_ACCOUNT_EMAIL>`；创建草稿前仍须遵循 1 封、5 封、全量确认的顺序。

## 只负责什么

- 读取 replied master 中已经整理好的 reply intelligence
- 补齐 thread 内上一封 outbound body evidence，例如 `Mail1_Body_Final` / `Mail2_Body_Final`
- 基于 reply intent 映射共享模板代码
- 生成 `Mail2 / Mail3` 正文
- 在原 Gmail thread 内创建 reply drafts
- 回写 `Mail2 / Mail3` 的 draft id、status、template

## 不负责什么

- 不重新做 Gmail recovery
- 不重新解析附件价格
- 价格 intelligence 不清楚时，不硬选模板
- 不按 `M1 / M2 / M3` 维护三套独立模板库

## 默认入口

1. 先读本 `SKILL.md`
2. 再读 `docs/UPGRADE_TODO.md`
3. 再读 `references/system_spec.md`
4. 再读 `references/reply_workflow.md`
5. 涉及表结构时读 `references/reply_table.md`
6. 涉及模板时读 `references/reply_templates.md`
7. 涉及 thread draft 时读 `references/thread_drafting.md`

## Shared Template Rule

- `M1 / M2 / M3` 使用同一套 reply template system
- 模板选择按 reply intent，不按 wave number
- 如果 recovery 已产出 `template_code_suggestion / template_confidence / auto_template_ready`，优先消费这些信号而不是从零重判
- 默认 greeting 固定为 `Hi,`
- 不依赖 `Greeting_Name`

## Gmail Draft Path

本 skill 必须沿用 `S2-ag-gmail-bulk-drafts` 已验证的 Gmail draft 路线：

- Gmail OAuth token
- manifest 驱动
- sample -> full
- 可 resume
- reply draft 必须额外绑定：
  - `threadId`
  - `In-Reply-To`
  - `References`

## Outbound Evidence Rule

- 当用户要 review `Mail2 / Mail3` 模板是否合理时，不能只看对方回复。
- 必须同时带上上一封我方 outbound body evidence，优先是：
  - `Mail1_Body_Final`
  - `Mail2_Body_Final`
- 如果表里为空，但 `Outbound_Message_IDs` 里存在对应 `mail1:` / `mail2:` message id，必须主动从 Gmail sent message 抓回正文并写回 CSV / review xlsx，而不是把缺口留给用户。
- 推荐脚本：
  - `scripts/backfill_outbound_bodies_from_gmail.py`

## 标准顺序

1. 确认 reply intelligence 已可用
2. 补齐上一封 outbound body evidence
3. 映射模板代码
4. 生成 reply job manifest
5. 先做 1 封
6. 再做 5 封 sample
7. 用户确认后全量
8. 回写 draft id / status / template

## 当前默认策略

- 默认不自动全量起草
- 可先运行 `scripts/suggest_reply_templates.py` 生成模板建议表，把大部分 reply 先分流到 `RQ* / RI* / RX1`
- 遇到模板映射不稳、正文生成边界、字段不一致等问题时，先主动切换工作方法、读参考文档、补脚本或做小样验证，优先自己消化掉大部分问题
- 默认目标是：尽可能自动完成大部分 template / body 填充，只把真正需要业务判断或存在明显歧义的少量案例留给人工 review
- 涉及价格理解时，默认把结构化金额按标准写法理解与呈现：`€1,500`、`$12,000`、`£3,500`
- 模板不确定时，标记 `RX2 | manual_review_required`
- 明确不合作时，标记 `RX1 | no_reply_decline`
