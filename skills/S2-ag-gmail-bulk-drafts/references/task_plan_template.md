# Bulk Draft Task Plan Template

## Task Summary

- Request:
- Source type:
- Target action:
- Expected volume:

## Inputs

- Source file or sheet:
- Recipient field:
- Subject field:
- Body field:
- Row filter:
- Additional filters:

## Execution Decision

- Draft only or send:
- Sample size:
- Full run allowed:
- Resume allowed:
- Deduplication needed:

## Delivery Path

- Auth path:
- API path:
- Fallback path:

## Idempotency

- Primary key:
- Secondary key:
- Existing artifact reconciliation rule:

## Run Plan

1. Prepare manifest
2. Create 1 draft sample
3. Create 5 draft sample
4. User confirmation
5. Run bulk batches
6. Reconcile
7. Dedupe
8. Backfill missing

## Risks

- Ambiguous recipient fields:
- Duplicate risk:
- Missing field risk:
- Auth risk:

## Acceptance

- Target count:
- Allowed duplicate count:
- Allowed missing count:
- Verification method:
