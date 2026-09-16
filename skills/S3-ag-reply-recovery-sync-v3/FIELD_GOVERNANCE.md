# Replied Master Field Governance

## Purpose

This document defines how `【S3 ReplyOps】Corestar-Replied-KOL.csv` should be managed.

It answers 4 questions:

1. which fields are written by recovery
2. which fields are written by reply drafting
3. which fields are manual-first
4. how `Reply_Stage` and `Pipeline_Stage` should connect

Quick per-column definitions live in:

- `references/shared/replied_master_field_dictionary.md`

## Field Groups

### Group A. Identity Fields

Manual-first / seeded from source:

- `Source_Tag`
- `账号ID`
- `频道/作者名称`
- `平台`
- `账号链接`
- `语言`

### Group B. Recovery-Owned Fields

Written by `S3-ag-reply-recovery-sync`:

- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Last_At`
- `Reply_Main_Dedicated_Rate`
- `Reply_Comprehensive_Pricing`
- `Reply_Pricing_Excerpt`
- `Mail1_Pricing_Excerpt`
- `Mail2_Pricing_Excerpt`
- `Mail3_Pricing_Excerpt`
- `Pricing_Effective_Wave`
- `Pricing_Change_Type`
- `Reply_Status`
- `Reply_Needs_Manual_Review`
- `Manual_Review_Reason`
- `Manual_Review_Focus`
- `Reply_Body_File`
- `Reply_Stream`
- `Reply_Stage`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Analysis`

### Group C. Draft-Owned Fields

Written by `S3-ag-reply-draft-ops`:

- `Mail1_Template`
- `Mail1_Body_Final`
- `Mail1_Status`
- `Mail1_Draft_ID`
- `Mail1_Sent_At`
- `Mail1_Reply_At`
- `Mail1_Reply_Summary`
- `Mail1_Reply`
- `Mail1_Reply_Category`
- `Mail1_Reply_Next_Action`
- `Mail2_Reply_Template`
- `Mail2_Body_Final`
- `Mail2_Status`
- `Mail2_Draft_ID`
- `Mail2_Reply_At`
- `Mail2_Reply_Summary`
- `Mail2_Reply`
- `Mail2_Reply_Category`
- `Mail2_Reply_Next_Action`
- `Mail3_Reply_Template`
- `Mail3_Body_Final`
- `Mail3_Status`
- `Mail3_Draft_ID`
- `Mail3_Reply_At`
- `Mail3_Reply_Summary`
- `Mail3_Reply`
- `Mail3_Reply_Category`
- `Mail3_Reply_Next_Action`

## Wave Writeback Rule

When recovery identifies the latest inbound as a `Mail1 / Mail2 / Mail3` reply, it must write the captured reply back into the matching wave block inside `【S3 ReplyOps】Corestar-Replied-KOL.csv`.

- `Mail1` reply writes into:
  - `Mail1_Reply_At`
  - `Mail1_Reply_Summary`
  - `Mail1_Reply`
  - `Mail1_Reply_Category`
  - `Mail1_Reply_Next_Action`
- `Mail2` reply writes into:
  - `Mail2_Reply_At`
  - `Mail2_Reply_Summary`
  - `Mail2_Reply`
  - `Mail2_Reply_Category`
  - `Mail2_Reply_Next_Action`
- `Mail3` reply writes into:
  - `Mail3_Reply_At`
  - `Mail3_Reply_Summary`
  - `Mail3_Reply`
  - `Mail3_Reply_Category`
  - `Mail3_Reply_Next_Action`

Recovery does not decide the outbound draft template itself. Template choice lives in `S3-ag-reply-draft-ops`.

### Group D. Shared but Guarded

May be initialized by recovery, but should not be aggressively overwritten:

- `Pipeline_Stage`

Manual-first:

- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`

## Core Rules

### Rule 1. Recovery does not draft

Recovery can understand reply content, but it does not generate Mail2 or Mail3 text.

### Rule 2. Drafting does not re-fetch history

Reply drafting uses structured reply intelligence; it should not re-run Gmail recovery logic.

### Rule 3. Pipeline_Stage is not the first layer

First determine:

- what the latest inbound replied to
- what the current `Reply_Stage` is

Then derive:

- `Pipeline_Stage`

### Rule 4. Manual notes are protected

The skill should not clear:

- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`

But machine-generated audit guidance may write:

- `Manual_Review_Reason`
- `Manual_Review_Focus`

These two columns are review-assist fields, not freeform human notes.

### Rule 5. First-touch outreach replies may bootstrap from S2

If an `Outreach` reply does not match an existing S3 row, recovery should try:

- `normalized subject + from_email`
- then `subject only`
- then `email only`

If the candidates are really the same contact duplicated across platforms, recovery should collapse them to one contact-level bootstrap target instead of treating them as a hard conflict.

This bootstrap path is valid for `M1` first replies.

### Rule 6. Bounce is not replied master data

`mailer-daemon`, delivery failure notices, and similar bounce messages must not bootstrap into `【S3 ReplyOps】Corestar-Replied-KOL.csv`.

### Rule 7. Blank identity rows are not valid replied rows

If recovery has reply content but still cannot resolve:

- `账号ID`
- `频道/作者名称`

then it should not silently write a normal replied row with those fields blank.

Instead:

- try subject-based reattachment to the original S2 outreach row
- if still unresolved, mark `manual_review`
- keep the row out of the normal replied queue

### Rule 8. Reply text without message metadata is incomplete

If recovery writes:

- `Mail1_Reply`
- `Mail2_Reply`
- `Mail3_Reply`

then it should also write:

- `Reply_Last_Message_ID`
- `Latest_Inbound_Message_ID`
- `Reply_Stage`
- `Reply_Stream`

Missing those linked fields means the capture is incomplete and should be treated as audit / repair work, not as a finished replied row.

## Reply_Stage Policy

Recovery should maintain:

- `mail1_waiting_reply`
- `mail1_replied_waiting_mail2`
- `mail2_waiting_reply`
- `mail2_replied`
- `mail3_waiting_reply`
- `mail3_replied`
- `closed`
- `manual_review`

## Pipeline_Stage Policy

Draft / ops should maintain:

- `M1_1_Drafted`
- `M1_2_Waiting`
- `M1_3_Replied_Review`
- `M2_1_Drafted`
- `M2_2_Waiting`
- `M2_3_Replied_Review`
- `M3_1_Drafted`
- `M3_2_Waiting`
- `M3_3_Replied_Review`
- `D1_Done`
- `D2_Stop`
- `Z_Manual_Review`

## Mapping Principle

Typical mapping:

- `Reply_Stage = mail1_waiting_reply` -> `Pipeline_Stage = M1_2_Waiting`
- `Reply_Stage = mail1_replied_waiting_mail2` -> `Pipeline_Stage = M1_3_Replied_Review`
- `Reply_Stage = mail2_waiting_reply` -> `Pipeline_Stage = M2_2_Waiting`
- `Reply_Stage = mail2_replied` -> `Pipeline_Stage = M2_3_Replied_Review`
- `Reply_Stage = mail3_waiting_reply` -> `Pipeline_Stage = M3_2_Waiting`
- `Reply_Stage = mail3_replied` -> `Pipeline_Stage = M3_3_Replied_Review`
- `Reply_Stage = closed` -> `Pipeline_Stage = D1_Done`
- `Reply_Stage = manual_review` -> `Pipeline_Stage = Z_Manual_Review`

## Pricing Policy

The pricing layer uses two layers:

- wave history layer
- current effective layer

### Wave History Layer

These fields preserve what each wave explicitly contained:

- `Mail1_Pricing_Excerpt`
- `Mail2_Pricing_Excerpt`
- `Mail3_Pricing_Excerpt`

Rule:

- A matched `Mail1 / Mail2 / Mail3` reply can update only its own wave pricing block.
- A later wave must not erase an earlier wave's price history.

### Current Effective Layer

These fields answer “what is the current usable price now”:

- main value: `Reply_Main_Dedicated_Rate`
- structured evidence: `Reply_Comprehensive_Pricing`
- raw evidence / note: `Reply_Pricing_Excerpt`
- source wave: `Pricing_Effective_Wave`
- change classification: `Pricing_Change_Type`

### Pricing Fill Rule

- review table / master 的内容字段只能落英文或中文；其他语言需先自动翻译
- `Reply_Pricing_Excerpt` 默认保留给人工整理摘要；机器 recovery 不应把它当作默认自动落点。
- 机器重新分析出来的价格证据，应优先写入对应波次的 `Mail1_Pricing_Excerpt / Mail2_Pricing_Excerpt / Mail3_Pricing_Excerpt`。
- 波次价格字段应保留可判断上下文：package、deliverables、usage、add-on、bundle、cross-post、平台覆盖、二次投放条件等，而不只是一个孤立价格。
- `Reply_Comprehensive_Pricing` 只写结构化且能明确对应的平台 / 形式 / 价格。
- 没有价格，不填。
- 有价格但对应不上具体平台 / 形式，不要硬填到 `Reply_Comprehensive_Pricing`，只保留在 `Reply_Pricing_Excerpt`。
- 不允许生成占位模板，例如：
  - `(Bundle Package): -`
  - `(YouTube): dedicated - | integration -`
  - 其他整套 `-` 模板
- 跨平台打包 / cross-post / bundle / package，可写入：
  - `Bundle Package: ...`
- `Reply_Main_Dedicated_Rate` 只在“明确 dedicated 且可对应主平台”时填写。
- 如果 `Reply_Stage = manual_review`，必须尽量补充：
  - `Manual_Review_Reason`: 为什么不能自动放行
  - `Manual_Review_Focus`: 人工需要确认什么

### Manual Review Guidance Rule

推荐把人工审核说明放在 `Reply_Needs_Manual_Review` 后面的两列：

- `Manual_Review_Reason`
- `Manual_Review_Focus`

原因：

- `Ops_Notes` 是人工运营备注位，语义过宽
- `Reply_Analysis` 适合长分析，不适合快速扫表
- 审核原因和审核动作需要一眼可见，最好与 `Reply_Needs_Manual_Review` 紧邻

建议写法：

- `Manual_Review_Reason`: `Wave attribution unclear; price evidence exists but it is not confirmed as Mail2.`
- `Manual_Review_Focus`: `Confirm whether the quote belongs to Mail1, Mail2, or attachment-only evidence before choosing template.`

### Effective Price Rule By Wave

- `Mail1` 首次给价时：
  - 更新 `Mail1_Pricing_Excerpt`
  - 更新 `Reply_*`
  - `Pricing_Effective_Wave = mail1`
  - `Pricing_Change_Type = first_price_mail1`
- `Mail2 / Mail3` 首次给价且前面没有有效价格时：
  - 更新对应波次的 `MailX_Pricing_Excerpt`
  - 更新 `Reply_*`
  - `Pricing_Effective_Wave = mail2` 或 `mail3`
  - `Pricing_Change_Type = first_price_after_followup`
- `Mail2 / Mail3` 明确替代旧价时：
  - 保留旧波次历史价格
  - 当前有效层改成新价
  - `Pricing_Change_Type = revised_from_mail1` / `revised_from_mail2`
- `Mail2 / Mail3` 只是确认旧价时：
  - 当前有效层可不变
  - `Pricing_Change_Type = confirmed_same_as_mail1` / `confirmed_same_as_mail2`
- 新波次有价格，但平台 / 形式仍对不上时：
  - 只更新对应波次的 `MailX_Pricing_Excerpt`
  - 当前有效结构化层可留空
  - `Reply_Needs_Manual_Review = yes`

### Structured Pricing Examples

- `Dedicated YouTube Video: $500`
  - `Reply_Pricing_Excerpt`: 原句保留
  - `Reply_Comprehensive_Pricing`: `YouTube: dedicated $500`
- `YouTube Integration: $350`
  - `Reply_Comprehensive_Pricing`: `YouTube: integration $350`
- `TikTok + Instagram Cross-post: $2,000`
  - `Reply_Comprehensive_Pricing`: `Bundle Package: TikTok + Instagram Cross-post: $2,000`
- `for a dedicated video is $4995`
  - 平台不明，`Reply_Comprehensive_Pricing` 留空
  - `Reply_Pricing_Excerpt` 保留原句
- `$12,000 for the integration`
  - 平台不明，`Reply_Comprehensive_Pricing` 留空
  - `Reply_Pricing_Excerpt` 保留原句

Recovery may also append the latest pricing context to:

- `Reply_Analysis`
- `Ops_Notes` only if the writeback policy explicitly allows append-only updates

## Sorting Policy

Suggested operational sort priority:

1. `Pipeline_Stage`
2. `Priority`
3. `Reply_Last_At`

The skill should prefer generating a sorted preview before rewriting the master order.
