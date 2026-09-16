# S3 Reply Recovery Sync Upgrade Log

## Purpose

This file is the live upgrade log for `S3-ag-reply-recovery-sync`.

Use it to track:

- what the upgrade is trying to achieve
- what has been completed
- what is currently in progress
- what remains pending

## Upgrade Goal

Build `S3-ag-reply-recovery-sync` into the recovery intelligence center for:

1. large-scale outreach follow-up
2. continuous reply recovery
3. pricing update sync
4. `M1 / M2 / M3` state progression support
5. clean handoff into reply drafting

## Status Legend

- `[x]` completed
- `[-]` in progress
- `[ ]` pending

## Work Plan

- `[x]` Step 1. Create upgrade scaffolding and progress log
- `[x]` Step 2. Build the field responsibility map for `【S3 ReplyOps】Corestar-Replied-KOL.csv`
- `[x]` Step 3. Define the `Reply_Stage -> Pipeline_Stage` mapping policy
- `[x]` Step 4. Define pricing update policy: main value, evidence, notes
- `[x]` Step 5. Design the long-term `reply-recovery-hub`
- `[x]` Step 6. Define checkpoint, overlap, and ledger strategy
- `[x]` Step 7. Upgrade recovery script architecture without breaking current auth
- `[x]` Step 8. Upgrade sync logic for replied master writeback
- `[x]` Step 9. Verify recovery outputs, status progression, and price updates
- `[x]` Step 10. Mark old assumptions deprecated and finalize the new operating model

## Current Notes

- The old system had useful recovery logic, but mixed too many responsibilities.
- The new direction keeps old strengths and upgrades structure, state management, and sync discipline.
- Gmail auth must remain compatible with the currently verified token-based path.
- `Reply_Stream` is now a real gate, not just a documentation concept.
- Only `Outreach` replies should enter `【S3 ReplyOps】Corestar-Replied-KOL.csv`; `Workstream` and `Manual_Review` must stay in audit / review paths.

## Change Log

- `2026-03-19` Created this live upgrade log.
- `2026-03-19` Step 1 completed. Step 2 started.
- `2026-03-19` Step 2 completed. Added FIELD_GOVERNANCE.md and started Step 3.
- `2026-03-19` Step 3 completed. Added STAGE_MAPPING_POLICY.md.
- `2026-03-19` Step 4 completed. Pricing policy is now formalized in FIELD_GOVERNANCE.md and UPGRADE_BLUEPRINT.md.
- `2026-03-19` Step 5 completed. Created workbench/reply-recovery-hub scaffold.
- `2026-03-19` Step 6 completed. Added checkpoint and message ledger scaffolding.
- `2026-03-19` Step 7 started. capture_recent_reply_window.py is being upgraded to use hub + checkpoint + ledger.
- `2026-03-19` Step 7 completed. capture_recent_reply_window.py now supports hub-root, checkpoint overlap, ledger, wave-specific reply field writeback, and guarded Pipeline_Stage initialization.
- `2026-03-19` Step 8 completed. Added MASTER_WRITEBACK_POLICY.md and upgraded sync scripts with append-only recovery notes.
- `2026-03-19` Step 9 completed. Verified py_compile, CLI help, stage mapping behavior, and synthetic pricing writeback flow.
- `2026-03-19` Step 10 completed. Deprecated old date-project workbench assumption in favor of reply-recovery-hub.
- `2026-03-19` Added `Reply_Stream` to `【S3 ReplyOps】Corestar-Replied-KOL.csv` and upgraded `capture_recent_reply_window.py` so only `Outreach` replies enter the replied master.
- `2026-03-19` Added Gmail API retry handling for `IncompleteRead` / transient `HttpError` in `capture_recent_reply_window.py` to keep live recovery stable without changing the token-based auth path.
- `2026-03-19` First live recovery run completed through the upgraded hub and stream gate: `2026-03-19_run-002`.
- `2026-03-19` Validated `subject + email` bootstrap on `103` unmatched outreach replies: `94` direct auto matches, `6` same-contact multi-platform collapses, `1` bounce exclusion.
- `2026-03-19` Upgraded `capture_recent_reply_window.py` so `no_master_match` now attempts S2 bootstrap by `normalized subject + from_email`, supports same-contact multi-platform collapse, and excludes bounce messages from replied-master bootstrap.
- `2026-03-20` Upgraded pricing method for recovery sync: only treat `channel/form + price` as high-confidence evidence, keep `Reply_Pricing_Excerpt` as raw evidence, and only write `Reply_Comprehensive_Pricing` when platform/form mapping is explicit.
- `2026-03-20` Deprecated placeholder pricing templates such as `dedicated - | integration -` and removed the default `[No explicit pricing] ...` fallback from Phase 1 pricing extraction.
- `2026-03-20` Updated `build_pricing_review_table_v3.py`, `SKILL.md`, `FIELD_GOVERNANCE.md`, `phase1_output_tables.md`, and `recovery_case_notes.md` to align docs and script behavior.
- `2026-03-20` Upgraded `download_and_extract_attachments.py` to dual OCR by default for images and rasterized PDF pages, with OCR candidate metadata written into `attachment_extraction_report.csv`.
- `2026-03-20` Upgraded `build_pricing_review_table_v3.py` to expose attachment-native `渠道 + 价格` evidence and emit template-friendly signals (`reply_intent`, `template_code_suggestion`, `template_confidence`, `auto_template_ready`) for downstream draft mapping.
- `2026-03-20` Added foreign-language normalization to Phase 1 review generation so non-English/non-Chinese reply text, attachment text, and OCR evidence are auto-translated to English before pricing extraction, intent detection, and master writeback.
- `2026-03-20` Updated pricing-layer policy: `Reply_Pricing_Excerpt` is now treated as a human-curated summary slot, while machine recovery should write richer body+attachment pricing analysis into `Mail1/2/3_Pricing_Excerpt`.
