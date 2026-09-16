# Phase 2 Thread Drafting

## Verified Path

Reply drafts must follow the same verified Gmail draft pattern as `S2-ag-gmail-bulk-drafts`:

- Gmail OAuth token
- manifest-driven jobs
- sample first
- then full batches
- resumable statuses

## Reply-Specific Requirement

Unlike normal drafts, reply drafts must be bound to the original thread.

Required fields:

- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Contact_Email`

Required request bindings:

- `threadId = Reply_Thread_ID`
- `In-Reply-To = original Message-ID`
- `References = prior References + original Message-ID`

## Canonical Scripts

- `scripts/prepare_reply_jobs.py`
- `scripts/sample_reply_drafts.py`
- `scripts/bulk_reply_drafts.py`

## Fixed Order

1. build manifest
2. create 1 sample draft
3. create 5 sample drafts
4. user confirms thread binding and tone
5. run bulk reply drafts

## Guardrails

- do not draft rows marked `RX1 | no_reply_decline`
- do not auto-draft rows marked `RX2 | manual_review_required`
- do not create reply drafts without `Reply_Thread_ID`
- do not create reply drafts without `Reply_Last_Message_ID`
