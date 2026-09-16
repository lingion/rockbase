# S3 Reply Draft Ops Upgrade TODO

## Goal

Upgrade this skill into a simpler, stronger reply-drafting system that:

- uses one shared template library across `M1 / M2 / M3`
- stores only `template code + template name` for review
- keeps actual email wording in a dedicated template reference file
- uses the same verified Gmail draft pipeline pattern as `S2-ag-gmail-bulk-drafts`
- creates reply drafts only inside the original Gmail thread

## Upgrade Scope

- [x] back up current skill folder into `workbench/2026-03-20/skill-bak/`
- [x] analyze current table and current template coverage
- [x] define new template taxonomy and numbering direction
- [x] simplify `SKILL.md`
- [x] simplify or replace outdated spec docs
- [x] rewrite `phase2_reply_workflow.md`
- [x] rewrite `phase2_reply_table.md`
- [x] rewrite `phase2_reply_templates.md`
- [x] align Gmail drafting path with `S2-ag-gmail-bulk-drafts`
- [x] add manifest-based reply draft scripts
- [x] keep reply drafts bound to original `threadId`
- [x] document writeback fields and sample/full run order
- [x] run basic script validation

## Decisions Already Confirmed

- default greeting is always `Hi,`
- no dedicated `Greeting_Name` field is required
- `M1 / M2 / M3` should use one shared template system
- template review field should mainly expose `code + name`
- if the agent is not confident, it should mark manual review instead of guessing
- if the creator clearly does not want to collaborate, no reply is needed

## Current Working Template Codes

- `RQ1` `quoted_send_details`
- `RQ2` `quoted_accept_standard`
- `RQ3` `quoted_accept_discounted`
- `RI1` `interested_request_rate`
- `RI2` `interested_send_details_no_price`
- `RI3` `ask_budget_first`
- `RI4` `verification_or_brief_gate`
- `RX1` `no_reply_decline`
- `RX2` `manual_review_required`
