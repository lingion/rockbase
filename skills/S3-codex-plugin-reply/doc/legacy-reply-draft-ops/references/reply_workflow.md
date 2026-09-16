# Phase 2 Reply Workflow

## Goal

Phase 2 takes already-structured reply intelligence and does four things:

- choose a shared template code
- generate reply body text
- create Gmail reply drafts inside the original thread
- write draft results back to the master table

## Core Principle

This phase does not think in separate `Mail2` and `Mail3` template universes.

It uses one shared template system across all waves.
Wave only affects:

- which body field is being written now
- which draft id / status field is being updated now
- which outbound message slot will be used next

## Standard Order

### Step 1. Confirm reply intelligence is usable

Minimum required fields:

- `账号ID`
- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Stage`
- latest relevant reply text in `Mail1_Reply` or `Mail2_Reply` or `Mail3_Reply`

Before template review for `Mail2` or `Mail3`, also bring back the immediately previous outbound body evidence:

- if reviewing `Mail2`, make sure `Mail1_Body_Final` is available
- if reviewing `Mail3`, make sure `Mail2_Body_Final` is available
- if the table field is blank but `Outbound_Message_IDs` contains the prior wave message id, fetch the sent message body from Gmail and write it back first

If pricing or intent is still unstable:

- stop
- mark `RX2 | manual_review_required`
- if recovery already emitted `template_code_suggestion / template_confidence / auto_template_ready`, use those first

### Step 2. Map template code

Map each row into one shared reply template code:

- `RQ*` quoted
- `RI*` interested but incomplete
- `RX*` exception

Template choice depends on reply intent, not on the wave name.

Suggested helper:

- `scripts/suggest_reply_templates.py`
- `scripts/backfill_outbound_bodies_from_gmail.py`

### Step 3. Generate body

The template field should primarily hold:

```text
RQ2 | quoted_accept_standard
```

The actual email wording comes from:

- `phase2_reply_templates.md`

Default greeting:

```text
Hi,
```

### Step 4. Build reply draft manifest

Create a manifest in `workbench/{YYYY-MM-DD}/` for the rows that are ready to draft.

The manifest is the source of truth for:

- sample sending
- full sending
- resume
- audit

### Step 5. Sample first

Fixed order:

1. create 1 draft
2. create 5 sample drafts
3. user confirms thread binding and tone

### Step 6. Bulk reply drafts

Only after sample confirmation:

- create more reply drafts in batches
- keep resume support
- keep manifest statuses updated

### Step 7. Write back

At minimum, write back:

- `Mail2_Reply_Template` or `Mail3_Reply_Template`
- `Mail2_Body_Final` or `Mail3_Body_Final`
- `Mail2_Draft_ID` or `Mail3_Draft_ID`
- `Mail2_Status` or `Mail3_Status`

## No-Reply Rule

If the row maps to:

```text
RX1 | no_reply_decline
```

Then:

- do not generate body
- do not create draft
- operator may move it to stop/closed flow

## Manual Review Rule

If the row maps to:

```text
RX2 | manual_review_required
```

Then:

- do not auto-draft
- leave the final decision to manual review

## Gmail Path Rule

Use the same verified draft-creation pattern as `S2-ag-gmail-bulk-drafts`:

- Gmail OAuth token
- manifest-driven execution
- sample then full
- resumable statuses

But reply drafts add:

- `threadId`
- `In-Reply-To`
- `References`
