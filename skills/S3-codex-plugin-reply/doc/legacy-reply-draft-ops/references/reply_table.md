# Phase 2 Reply Table

## Goal

This phase does not need a separate complicated reply table.

The operational source of truth remains:

- `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL.csv`

Phase 2 should only use the fields needed to:

- understand the latest reply
- choose a shared template code
- generate body text
- create a reply draft in the original thread
- write the result back

## Minimum Required Fields

- `账号ID`
- `频道/作者名称`
- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Stage`
- `Reply_Pricing_Excerpt`
- `Reply_Comprehensive_Pricing`
- one of:
  - `Mail1_Reply`
  - `Mail2_Reply`
  - `Mail3_Reply`

## Template Writeback Fields

Use existing fields:

- `Mail2_Reply_Template`
- `Mail2_Body_Final`
- `Mail2_Draft_ID`
- `Mail2_Status`
- `Mail3_Reply_Template`
- `Mail3_Body_Final`
- `Mail3_Draft_ID`
- `Mail3_Status`

Recommended template value format:

```text
RQ2 | quoted_accept_standard
```

## Which Wave Gets Written

- If the next outbound is `Mail2`, write to the `Mail2_*` fields
- If the next outbound is `Mail3`, write to the `Mail3_*` fields

Template system itself is shared.
Only the destination field block changes.

## Rows That Should Not Auto-Draft

- `RX1 | no_reply_decline`
- `RX2 | manual_review_required`
- rows without `Reply_Thread_ID`
- rows without `Reply_Last_Message_ID`
- rows with unclear pricing when pricing is necessary to choose the reply

## Reply Body Rule

- `Mail2_Body_Final` / `Mail3_Body_Final` store the final body text only
- no greeting-name dependency
- default greeting is always `Hi,`

## Manifest Rule

All reply drafting runs should first build a manifest in:

- `workbench/{YYYY-MM-DD}/`

Suggested manifest fields:

- `job_id`
- `row_id`
- `account_id`
- `reply_wave`
- `template_code`
- `template_name`
- `to`
- `subject`
- `body`
- `thread_id`
- `latest_message_id`
- `status`
- `draft_id`
- `error`
