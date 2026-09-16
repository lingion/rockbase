# Replied Master Field Dictionary

## Purpose

This file is the full field dictionary for `【S3 ReplyOps】Corestar-Replied-KOL.csv`.

Use it to answer:

- what each column is for
- which skill or person owns it
- what kind of value belongs in it
- whether it is historical, current-effective, manual-first, or audit-only

Detailed overwrite rules still live in:

- `FIELD_GOVERNANCE.md`
- `MASTER_WRITEBACK_POLICY.md`
- `replied_master_field_manifest.json`

## Stability Rule

- Field names are the stable protocol.
- Excel column letters or positions are not stable protocol.
- Agents must read, reason, and write by field name.
- Reordering columns should not change behavior as long as field names stay the same.
- If a spreadsheet app shows a different display label, resolve it back to the canonical field name in `replied_master_field_manifest.json`.

## Ownership Legend

- `manual-first`: mainly human-owned, agent should not overwrite casually
- `recovery`: written by `.agent/skills/S3-ag-reply-recovery-sync`
- `draft-ops`: written by `.agent/skills/S3-ag-reply-draft-ops`
- `shared-guarded`: may be initialized by agent but must be overwritten conservatively

## A. Pipeline And Identity

### `Pipeline_Stage`

- Owner: `shared-guarded`
- Purpose: top-level operational stage used by the ops queue
- Content: values such as `M1_2_Waiting`, `M2_3_Replied_Review`, `Z_Manual_Review`
- Rule: recovery may initialize or refresh only when the row is still in a waiting/drafted style stage

### `Source_Tag`

- Owner: `manual-first`
- Purpose: remember which source list or source workflow the row came from
- Content: source label such as campaign/list origin

### `账号ID`

- Owner: `manual-first`
- Purpose: stable row identifier for the creator/contact
- Content: one creator/account id string
- Rule: this is one of the main matching keys and should stay stable

### `频道/作者名称`

- Owner: `manual-first`
- Purpose: readable creator name
- Content: creator/channel display name
- Rule: useful for ops reading, but should not be the only join key

### `平台`

- Owner: `manual-first`
- Purpose: primary platform label
- Content: `YouTube`, `TikTok`, `Instagram`, `X`, etc.

### `账号链接`

- Owner: `manual-first`
- Purpose: profile URL
- Content: one main account/profile link

### `语言`

- Owner: `manual-first`
- Purpose: working language / creator language
- Content: language label such as `English`

## B. Current Effective Reply Intelligence

### `Reply_Contact_Email`

- Owner: `recovery`
- Purpose: current contact email observed in the reply thread
- Content: one normalized email address

### `Reply_Thread_ID`

- Owner: `recovery`
- Purpose: Gmail thread id for the active reply thread
- Content: one Gmail thread id string

### `Reply_Last_Message_ID`

- Owner: `recovery`
- Purpose: newest inbound message id stored on the row
- Content: one Gmail message id

### `Reply_Last_Subject`

- Owner: `recovery`
- Purpose: subject line of the latest relevant inbound
- Content: one email subject string

### `Reply_Last_At`

- Owner: `recovery`
- Purpose: timestamp of the latest relevant inbound
- Content: one email date string

### `Reply_Main_Dedicated_Rate`

- Owner: `recovery`
- Purpose: single compact main dedicated price for the current effective offer
- Content: only fill when a dedicated/main video rate is explicit and usable
- Rule: leave blank if only bundle/integration exists or platform is too unclear

### `Reply_Comprehensive_Pricing`

- Owner: `recovery`
- Purpose: structured current effective pricing summary
- Content: only explicit platform/form/price mappings
- Rule: leave blank when the evidence has price but cannot be mapped confidently

### `Reply_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: current effective pricing evidence snippet
- Content: one short raw evidence sentence or compressed excerpt
- Rule: do not add wrapper text such as `(High-confidence body): ...`

## C. Wave Pricing History

### `Mail1_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: preserve the pricing evidence found in the `Mail1` reply wave
- Content: short raw evidence sentence or excerpt
- Rule: history only, not the main structured pricing field

### `Mail2_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: preserve the pricing evidence found in the `Mail2` reply wave
- Content: short raw evidence sentence or excerpt
- Rule: use this to remember M2 pricing even when effective price later changes again

### `Mail3_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: preserve the pricing evidence found in the `Mail3` reply wave
- Content: short raw evidence sentence or excerpt
- Rule: history only

### `Pricing_Effective_Wave`

- Owner: `recovery`
- Purpose: mark which wave currently owns the effective price
- Content: `mail1`, `mail2`, `mail3`, or blank

### `Pricing_Change_Type`

- Owner: `recovery`
- Purpose: describe how current effective price relates to earlier waves
- Content: values such as `first_price_mail1`, `first_price_after_followup`, `revised_from_mail1`, `confirmed_same_as_mail1`

## D. Mail1 Outbound And Reply Block

### `Mail1_Subject`

- Owner: `draft-ops`
- Purpose: subject used for the first outbound email
- Content: one subject line

### `Mail1_Template`

- Owner: `draft-ops`
- Purpose: template label or template family used for Mail1
- Content: one template id/name

### `Mail1_Body_Final`

- Owner: `draft-ops`
- Purpose: final outbound body content for Mail1
- Content: final email body text

### `Mail1_Status`

- Owner: `draft-ops`
- Purpose: status of Mail1 execution
- Content: values such as `drafted`, `sent`, `waiting`, `replied`

### `Mail1_Draft_ID`

- Owner: `draft-ops`
- Purpose: Gmail draft id for Mail1 when applicable
- Content: one Gmail draft id

### `Mail1_Sent_At`

- Owner: `draft-ops`
- Purpose: send timestamp of Mail1
- Content: one send time string

### `Mail1_Reply_At`

- Owner: `recovery`
- Purpose: timestamp of the reply that belongs to Mail1
- Content: one inbound reply date string

### `Mail1_Reply_Summary`

- Owner: `recovery`
- Purpose: compressed summary of the Mail1 reply body
- Content: short one-line summary

### `Mail1_Reply`

- Owner: `recovery`
- Purpose: raw reply text captured for the Mail1 wave
- Content: reply body text

### `Mail1_Attachment_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: pricing evidence extracted from Mail1 attachments
- Content: raw short excerpt from attachment/OCR

## E. Mail2 Outbound And Reply Block

### `Mail2_Reply_Template`

- Owner: `draft-ops`
- Purpose: template label used for the second outbound follow-up
- Content: one template id/name

### `Mail2_Body_Final`

- Owner: `draft-ops`
- Purpose: final outbound body content for Mail2
- Content: final email body text

### `Mail2_Status`

- Owner: `draft-ops`
- Purpose: execution status of Mail2
- Content: values such as `drafted`, `sent`, `waiting`, `replied`

### `Mail2_Draft_ID`

- Owner: `draft-ops`
- Purpose: Gmail draft id for Mail2
- Content: one Gmail draft id

### `Mail2_Reply_At`

- Owner: `recovery`
- Purpose: timestamp of the reply that belongs to Mail2
- Content: one inbound reply date string

### `Mail2_Reply_Summary`

- Owner: `recovery`
- Purpose: compressed summary of the Mail2 reply body
- Content: short one-line summary

### `Mail2_Reply`

- Owner: `recovery`
- Purpose: raw reply text captured for the Mail2 wave
- Content: reply body text

### `Mail2_Attachment_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: pricing evidence extracted from Mail2 attachments
- Content: raw short excerpt from attachment/OCR

## F. Mail3 Outbound And Reply Block

### `Mail3_Reply_Template`

- Owner: `draft-ops`
- Purpose: template label used for the third outbound follow-up
- Content: one template id/name

### `Mail3_Body_Final`

- Owner: `draft-ops`
- Purpose: final outbound body content for Mail3
- Content: final email body text

### `Mail3_Status`

- Owner: `draft-ops`
- Purpose: execution status of Mail3
- Content: values such as `drafted`, `sent`, `waiting`, `replied`

### `Mail3_Draft_ID`

- Owner: `draft-ops`
- Purpose: Gmail draft id for Mail3
- Content: one Gmail draft id

### `Mail3_Reply_At`

- Owner: `recovery`
- Purpose: timestamp of the reply that belongs to Mail3
- Content: one inbound reply date string

### `Mail3_Reply_Summary`

- Owner: `recovery`
- Purpose: compressed summary of the Mail3 reply body
- Content: short one-line summary

### `Mail3_Reply`

- Owner: `recovery`
- Purpose: raw reply text captured for the Mail3 wave
- Content: reply body text

### `Mail3_Attachment_Pricing_Excerpt`

- Owner: `recovery`
- Purpose: pricing evidence extracted from Mail3 attachments
- Content: raw short excerpt from attachment/OCR

## G. Recovery Status And Review

### `Reply_Status`

- Owner: `recovery`
- Purpose: high-level row reply state
- Content: usually `replied` when a valid inbound has been captured

### `Reply_Needs_Manual_Review`

- Owner: `recovery`
- Purpose: flag rows that still need human review
- Content: `yes` or blank
- Rule: set when matching, pricing mapping, or stream classification is still unstable

### `Reply_Body_File`

- Owner: `recovery`
- Purpose: pointer to the saved latest body text file
- Content: relative or canonical stored body path

### `Reply_Stage`

- Owner: `recovery`
- Purpose: stage of the reply lifecycle
- Content: values such as `mail1_waiting_reply`, `mail1_replied_waiting_mail2`, `mail2_replied`, `manual_review`

## H. Manual Ops Fields

### `Owner`

- Owner: `manual-first`
- Purpose: who owns the row operationally
- Content: team member / assignee name

### `Priority`

- Owner: `manual-first`
- Purpose: ops priority or urgency
- Content: priority label

### `Final_Outcome`

- Owner: `manual-first`
- Purpose: final business outcome when the case closes
- Content: close result such as booked / no response / declined / stop

### `Ops_Notes`

- Owner: `manual-first`
- Purpose: shared operator note field
- Content: short human notes, edge cases, review comments, append-only recovery notes
- Rule: agents should not erase existing notes; recovery may append short machine notes when policy allows

## I. Recovery Tracking And Audit

### `Outbound_Message_IDs`

- Owner: `recovery`
- Purpose: map outbound Gmail message ids for wave attribution
- Content: compressed mapping such as `mail1:<id>|mail2:<id>|mail3:<id>`

### `Latest_Inbound_Message_ID`

- Owner: `recovery`
- Purpose: newest inbound Gmail message id
- Content: one Gmail message id string

### `Latest_Inbound_InReplyTo`

- Owner: `recovery`
- Purpose: newest inbound email header `In-Reply-To`
- Content: one message id from the email header
- Typical use: compare against `Outbound_Message_IDs` to infer wave

### `Capture_Run_ID`

- Owner: `recovery`
- Purpose: identify which recovery run wrote the row
- Content: one run id string

### `Capture_At`

- Owner: `recovery`
- Purpose: timestamp of the last recovery writeback
- Content: one timestamp string

### `Reply_Stream`

- Owner: `recovery`
- Purpose: classify whether the reply belongs to outreach, workstream, or manual review
- Content: `Outreach`, `Workstream`, or `Manual_Review`

### `Reply_Analysis`

- Owner: `recovery`
- Purpose: compact machine-readable summary of the latest reply
- Content: short string like `category=<...> | summary=<...> | next=<...>`
- Rule: helpful for ops review and downstream routing, but not the final template label

## Boundary Reminder

This dictionary covers what each CSV field means.

This skill only:

- captures reply intelligence
- stores history
- updates current effective pricing
- writes back to CSV

This skill does not:

- choose reply template labels
- decide next-email strategy
- draft Mail2 or Mail3 text

That belongs to:

- `.agent/skills/S3-ag-reply-draft-ops`
