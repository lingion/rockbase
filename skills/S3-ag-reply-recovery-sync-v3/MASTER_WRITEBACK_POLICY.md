# Master Writeback Policy

## Purpose

This document defines how `S3-ag-reply-recovery-sync` writes back into:

- `【S3 ReplyOps】Corestar-Replied-KOL.csv`

## Required Sequence

1. physical backup
2. preview
3. audit
4. write master

## Protected Fields

The recovery sync should never clear or overwrite these by default:

- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`

## Allowed Recovery Fields

Recovery-owned fields may be refreshed when newer intelligence is found:

- reply identity fields
- latest inbound fields
- current effective pricing fields
- wave-specific pricing history fields
- `Reply_Status`
- `Reply_Needs_Manual_Review`
- `Reply_Body_File`
- `Reply_Stream`
- `Reply_Stage`
- `Reply_Analysis`

Wave-specific reply fields may also be refreshed when the latest inbound clearly maps to a wave:

- `Mail1_Reply_*`
- `Mail2_Reply_*`
- `Mail3_Reply_*`
- `Mail1_Pricing_Excerpt`
- `Mail2_Pricing_Excerpt`
- `Mail3_Pricing_Excerpt`

Recovery sync does not set outbound draft template fields such as:

- `Mail2_Reply_Template`
- `Mail3_Reply_Template`
- any reply label / reply template recommendation fields owned by `S3-ag-reply-draft-ops`

## Pricing Writeback Policy

### Layer 1. History

`Mail1 / Mail2 / Mail3` pricing fields preserve what was explicitly present in that wave.

- write only to the matched wave excerpt field
- do not backfill another wave's fields
- do not clear an earlier wave when a later wave arrives
- machine recovery should prefer writing rich evidence blocks into the matched wave field, combining body + attachment context when possible
- rich evidence blocks may keep package scope, deliverables, usage rights, add-ons, and cross-platform notes if they materially help downstream review

### Layer 2. Current Effective Roll-up

`Reply_Main_Dedicated_Rate` and `Reply_Comprehensive_Pricing` represent the current effective price.

- later waves may replace the current effective layer
- replacement is allowed only when the newer wave provides equal or better pricing evidence quality
- if the newer wave has price but mapping is unclear, keep excerpt evidence and leave structured fields conservative

`Reply_Pricing_Excerpt` should be treated as a human-curated summary slot.

- if the user has manually edited it, recovery sync should preserve it
- wave-specific machine analysis should not automatically overwrite it

### Audit Fields

When price roll-up changes, recovery sync should also maintain:

- `Pricing_Effective_Wave`
- `Pricing_Change_Type`
- `Reply_Needs_Manual_Review` when mapping remains ambiguous

## Identity And Metadata Guardrails

Recovery must not write a normal replied row if it cannot reliably resolve the creator identity.

Hard rules:

- if `账号ID` or `频道/作者名称` cannot be resolved, route the row to audit / manual review instead of leaving a blank-identity replied row
- if a manager / talent agency / assistant email replies, first try to re-attach the reply back to the original creator row by subject / original outreach target
- if `Mail1_Reply` or `Mail2_Reply` or `Mail3_Reply` is written, recovery should also write:
  - `Reply_Last_Message_ID`
  - `Latest_Inbound_Message_ID`
  - `Reply_Stage`
  - `Reply_Stream`
- if those linked metadata fields are missing after capture, treat the writeback as incomplete and keep it out of the normal queue

## Ops Note Policy

If enabled, recovery sync may append a short machine note to `Ops_Notes`, for example:

`[recovery] source=recent_capture | pricing updated`

Rules:

- append-only
- never delete manual notes
- avoid duplicate identical notes

## Sorting Policy

Prefer generating a sorted preview before reordering the master.

Suggested preview sort priority:

1. `Pipeline_Stage`
2. `Priority`
3. `Reply_Last_At`
