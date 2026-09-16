# Gmail Reply Draft Ops System Spec

## Goal

`ag-reply-draft-ops` is the drafting phase that runs after reply recovery.

It is responsible for:

- reading structured reply intelligence from the replied master
- choosing a shared reply template code
- generating reply body text
- creating Gmail reply drafts inside the original thread
- writing draft results back

It is not responsible for:

- re-fetching Gmail replies
- re-parsing attachments
- rebuilding pricing intelligence from scratch

## Source Of Truth

The main working table is:

- `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL.csv`

## Stable Keys

Preferred keys:

- `账号ID`
- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`

Do not use display-only fields as unique ids.

## Shared Template Principle

- `M1 / M2 / M3` share one template system
- template choice is based on reply intent, not wave number
- default greeting is always `Hi,`

## Gmail Draft Principle

This skill must follow the same verified draft path pattern as `S2-ag-gmail-bulk-drafts`:

- Gmail OAuth token
- manifest-driven execution
- sample then full
- resumable statuses

Reply drafts add these required thread bindings:

- `threadId`
- `In-Reply-To`
- `References`

## Output Principle

The key outputs of this phase are:

- template-coded rows
- final reply body text
- reply draft manifest
- Gmail drafts
- draft write-back
