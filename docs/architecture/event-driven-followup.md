# Event-Driven Follow-up Contract

**Status:** Proposed target contract
**Date:** 2026-09-23
**Scope:** inbound delivery, immediate follow-up preparation, and polling compatibility

## Current evidence

`mailkit/mailkit/receiver.py` persists `POST /api/inbound` and emits a stderr record, but no consumer is connected to that record. `mailkit/mailkit/postfix_pipe.py` already provides push delivery into the receiver. `mailkit/mailkit/fetch_replies.py` separately polls `/api/emails`. `mailkit/mailkit/master_sync.py` already deduplicates a stored inbound message by external ID and matches replies by `In-Reply-To`/`References`.

## Target flow

```text
Postfix pipe / provider push
        |
        v
receiver: validate -> SQLite commit -> 200
        |                         \
        |                          \-> polling fallback remains available
        v
signed inbound.accepted event (at-least-once)
        |
        v
follow-up worker: verify -> durable ledger claim -> single-flight master lock
        |
        +-> reply sync -> semantic intent/summary -> draft preparation
        |
        +-> no-reply deadline scheduler (separate periodic invocation)
        |
        v
existing send approval gate; never direct auto-send
```

## Event contract

The event is an internal notification, not an email mirror. It contains identifiers and routing metadata only:

```json
{
  "schema_version": 1,
  "event": "inbound.accepted",
  "event_id": "stable-receiver-message-event-id",
  "message_id": "receiver-sqlite-message-id",
  "external_id": "provider-message-id-or-empty",
  "mailbox": "recipient@example.invalid",
  "received_at": "2026-09-23T12:34:56Z",
  "attempt": 1
}
```

The event MUST NOT contain `raw`, `text`, `html`, credentials, API keys, or full sender content. The worker reads the committed message through the receiver's authenticated storage/API boundary.

The event is signed with HMAC-SHA256 over the canonical JSON bytes using the `x-rockbase-event-signature` header. The receiver only sends to a configured internal dispatch URL. The worker rejects invalid signatures, unknown schema versions, and missing `event_id`.

## Delivery and idempotency

Delivery is at-least-once. The receiver commits the message before dispatch. Dispatch is bounded and asynchronous so a slow or unavailable worker cannot delay SMTP acknowledgement. A dispatch failure is observable and recoverable through a bounded retry/outbox mechanism; it does not roll back the message.

The worker maintains a durable SQLite ledger keyed by `event_id`. Claiming an event is atomic. A duplicate event returns `duplicate` and does not run synchronization twice. The existing `external_id` guard in `master_sync.py` remains a second defense for push plus polling overlap.

Master CSV mutation is protected by one process lock shared by push workers, polling runs, and operator-triggered pipelines. The lock covers read-modify-write, not network calls or LLM latency. Failed runs retain retryable status and bounded backoff; successful runs record `run_id` and stage state.

## Follow-up behavior

An inbound event immediately prepares the next action. It may synchronize the reply, classify intent, summarize conditions, and create a Gmail draft. It MUST stop at the existing `send` approval gate. Opt-out, rate limits, and policy checks remain deterministic and authoritative.

No-reply follow-ups use a separate periodic scheduler that computes due jobs from existing sent/replied/closed fields. The scheduler creates draft jobs only. It does not invoke SMTP and does not invent a second source of truth for message state.

## Polling fallback

`fetch_replies.py` remains supported for mail providers without push delivery and for recovery after dispatch outage. Both paths call the same reply synchronization and idempotency logic. Polling is not a second semantic or CSV-write implementation.

## Failure behavior

| Failure | Required behavior |
|---|---|
| Worker unavailable | receiver acknowledges committed mail; signed event is retried/outboxed and operator-visible |
| Invalid event signature | worker returns 401/403; no ledger claim or pipeline execution |
| Duplicate event | duplicate result recorded; no second mutation |
| Master lock busy | bounded retry; no partial CSV write |
| LLM unavailable/invalid | deterministic preview/fallback plus `manual_review`; no automatic send |
| Gmail draft API failure | retryable worker state; no send attempt |
| Approval absent | draft remains pending; no SMTP call |

## Operational contract

The worker exposes health and metrics for accepted, duplicate, failed, retrying, locked, and approval-pending events. Logs contain event IDs and run IDs, not message bodies or secrets. Operators can inspect the ledger, replay a failed event by ID, and disable dispatch without disabling inbound storage.

## Deliberate non-goals

- Exactly-once delivery.
- Automatic outbound sending.
- Replacing the existing receiver database or master CSV.
- Removing polling before push delivery is proven in production.
- Using an LLM for authentication, matching, deduplication, opt-out, rate limiting, or schedule arithmetic.
