# Reply Template System Upgrade Plan

## Template Code Table

| 编号 | English | 中文解释 |
| --- | --- | --- |
| `RQ1` | `quoted_send_details` | 已拿到报价，但当前仍希望继续压价、继续试探 agency rate，回复目标是推动对方再给更优价格或更多可谈空间 |
| `RQ2` | `quoted_accept_standard` | 我方接受对方当前报价，即使对方没有降价，也先保留合作并等待合适项目推进，后续是否再谈价格另说 |
| `RQ3` | `quoted_accept_discounted` | 我方接受对方已经给出的折扣价 / 首次合作优惠价，并把该价格视为当前可推进的合作价格 |
| `RI1` | `interested_request_rate` | 对方表达兴趣，但还没有给出可用报价，需要继续索要 rate |
| `RI2` | `interested_send_details_no_price` | 对方发了 media kit / channel details / audience info，但仍未给出清晰价格 |
| `RI3` | `ask_budget_first` | 对方先问我们的预算、offer 或可接受区间，再决定是否继续 |
| `RI4` | `verification_or_brief_gate` | 对方要求先做身份验证、提供官网/company info，或先看 brief 后再继续 |
| `RX1` | `no_reply_decline` | 对方明确不合作、不适合，或当前无需继续回复 |
| `RX2` | `manual_review_required` | 信息混杂或判断不稳，交给人工审核决定下一步模板 |

## Goal

Upgrade `S3-ag-reply-draft-ops` into a simpler shared reply system that:

- uses one template library across `M1 / M2 / M3`
- keeps the review layer as `code + name`
- keeps actual email wording in one dedicated template reference file
- defaults every email to `Hi,`
- does not depend on `Greeting_Name`
- uses the same verified Gmail draft pattern as `S2-ag-gmail-bulk-drafts`
- creates reply drafts only inside the original Gmail thread

## Structural Change

This skill should no longer present itself as a `Mail2` folder plus `Mail3` folder system.

The shared references should live in:

- `references/system_spec.md`
- `references/reply_workflow.md`
- `references/reply_table.md`
- `references/reply_templates.md`
- `references/thread_drafting.md`

The canonical scripts should live in:

- `scripts/common.py`
- `scripts/prepare_reply_jobs.py`
- `scripts/sample_reply_drafts.py`
- `scripts/bulk_reply_drafts.py`

## Business Logic Change

Old mindset:

- different waves imply different template sets

New mindset:

- wave only determines which destination fields are written
- reply intent determines the template

In other words:

- `Mail2_*` and `Mail3_*` are writeback destinations
- `RQ / RI / RX` are the actual shared decision system

## Gmail Drafting Change

This skill should follow the same proven manifest pattern as `S2-ag-gmail-bulk-drafts`:

1. build manifest
2. sample one
3. sample five
4. user confirms
5. bulk drafts

Reply drafts add:

- `threadId`
- `In-Reply-To`
- `References`

## Operator Rule

If the agent is not confident:

- do not guess
- write `RX2 | manual_review_required`

If the creator clearly does not want to proceed:

- use `RX1 | no_reply_decline`
- do not draft
