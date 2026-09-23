# Event-Driven Follow-up and LLM Boundary Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn inbound mail delivery into an immediate, idempotent follow-up trigger, add the missing semantic-model steps, remove unnecessary model calls, and add deterministic schedule, safety, observability, and regression coverage.

**Architecture:** The receiver remains the authoritative ingress and SQLite persistence boundary. After a successful transaction it publishes a bounded, authenticated HTTP event to a separate follow-up worker; the worker owns single-flight execution, reply synchronization, semantic classification/drafting, and the existing human approval gate. Polling remains as a compatibility fallback for providers without push delivery. Deterministic parsing, policy, routing, deduplication, JSON repair, OCR post-processing, and rate limiting stay local and never require an LLM.

**Tech Stack:** Python 3.12, stdlib `ThreadingHTTPServer`, SQLite, existing Rockbase stage runner, OpenAI-compatible Python SDK, pytest, Docker Compose.

## Global Constraints

- Do not send email automatically: the existing `send` approval gate, rate limits, opt-out checks, and human review remain mandatory.
- Do not put credentials or full email bodies into events, logs, run state, or audit artifacts.
- Every inbound event is at-least-once; consumers must be idempotent by receiver message ID/external ID.
- Receiver acknowledgement must not wait for LLM calls, CSV writes, Gmail calls, or pipeline execution.
- Existing polling must remain available as a fallback and must not duplicate a push-triggered result.
- Use OpenAI SDK only for semantic classification, summarization, language/meaning extraction, and multimodal interpretation; use deterministic code for protocol, policy, schema, matching, dedupe, and formatting.
- All new behavior requires focused tests and the scoped suite: `PYTHONPATH=. .venv/bin/python -m pytest tests -q -p no:cacheprovider`.
- No release, tag, push, webhook, or external publication is part of implementation without explicit later authorization.

---

## File and Boundary Map

- `mailkit/mailkit/receiver.py`: ingress, SQLite commit, authenticated event dispatch configuration, bounded asynchronous delivery.
- `mailkit/mailkit/events.py`: structured local logging only; it is not the event bus.
- `mailkit/mailkit/followup_worker.py`: event consumer, idempotency ledger, single-flight lock, pipeline invocation, retry/backoff, and approval-gate handoff.
- `mailkit/mailkit/fetch_replies.py`: compatibility polling path; no semantic behavior is added here.
- `mailkit/config.example.toml`: receiver dispatch and follow-up settings.
- `scripts/rockbase_orchestrator.py` and `scripts/run_full_pipeline.py`: optional follow-up stage wiring and stable run identity.
- `skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py`: semantic intent classification with deterministic fallback and confidence/review contract.
- `mailkit/mailkit/master_sync.py`: bounded reply summary contract and optional summary artifact handoff.
- `skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py`: local JSON extraction/repair before any model retry.
- `skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py`: server-safe `auto` engine selection and explicit multimodal fallback.
- `skills/S3-ag-reply-draft-ops/scripts/followup_scheduler.py`: due-date calculation and durable follow-up job generation; it never sends.
- `tests/test_receiver_followup_contract.py`: receiver dispatch and event contract tests.
- `tests/test_followup_worker.py`: idempotency, concurrency, retry, and gate tests.
- `tests/test_semantic_boundaries.py`: LLM-required and deterministic-only behavior tests.
- `tests/test_followup_scheduler.py`: schedule policy and no-send tests.
- `tests/test_llm_json_repair.py`: local JSON repair tests.
- `tests/test_s5_ocr_llm.py`: preserve existing OCR tests and add server auto-engine cases.

---

## Phase 0: Adversarial Design Before Coding

### Task 1: Independent architecture attacks and final contract

**Files:**
- Create: `docs/architecture/event-driven-followup.md`
- Create: `docs/architecture/llm-boundaries.md`

**Interfaces:**
- Produces the exact event schema, retry policy, idempotency key, worker command, schedule contract, and semantic-vs-deterministic decision table consumed by later tasks.

- [ ] **Step 1: Write the proposed contracts**
  - Event payload: `{event: "inbound.accepted", event_id, message_id, external_id, mailbox, received_at, attempt}`.
  - `event_id` is stable for the stored message; `message_id` is the receiver SQLite ID; no body or secret is included.
  - Receiver dispatches `POST /internal/events/inbound` with `x-rockbase-event-signature` HMAC when configured.
  - Worker returns `202` after durable enqueue/ledger write; duplicate `event_id` is a no-op.
  - Worker runs sync, semantic classification, draft preparation, and scheduler evaluation; final send remains gate-blocked.
- [ ] **Step 2: Record the LLM boundary matrix**
  - LLM required: reply intent, nuanced follow-up summary, pricing/condition extraction, language meaning where translation changes business interpretation, image semantic interpretation.
  - Deterministic only: email MIME parsing, authentication, SQLite writes, IDs, dedupe, In-Reply-To matching, rate limits, opt-out, schedule arithmetic, JSON syntax repair, CSV serialization, template code lookup, OCR regex/country normalization.
  - Hybrid: intent and summary use LLM with deterministic validation and manual-review fallback; OCR uses platform vision/tesseract first where available and multimodal fallback on server.
- [ ] **Step 3: Run independent attacks**
  - Ask one subagent to attack event delivery, retries, duplicate events, and shared CSV writes.
  - Ask one subagent to attack LLM placement, prompt injection, cost, and deterministic fallbacks.
  - Ask one subagent to attack scheduling, approval gates, and failure recovery.
- [ ] **Step 4: Resolve findings into the two documents**
  - Reject proposals that block SMTP ingress, bypass approval, expose body data, or rely on exactly-once delivery.
  - Preserve equivalent implementations if they satisfy the contracts.
- [ ] **Step 5: Verify documentation**
  - Run `rg -n "TODO|TBD|implement later|appropriate error" docs/architecture/event-driven-followup.md docs/architecture/llm-boundaries.md` and require no matches.

**Checkpoint A:** Architecture contracts are reviewed by independent agents and the Workflow adversarial verifier before implementation.

---

## Phase 1: Push Ingress and Follow-up Worker

### Task 2: Receiver event dispatch

**Files:**
- Modify: `mailkit/mailkit/receiver.py:serve/main/POST /api/inbound`
- Modify: `mailkit/config.example.toml:[receiver]`
- Test: `tests/test_receiver_followup_contract.py`

**Interfaces:**
- `serve(db, port, api_key, host, dispatch_url="", dispatch_secret="", dispatch_timeout=2.0)`.
- Internal helper `_dispatch_inbound_event(event: dict, url: str, secret: str, timeout: float) -> None`.

- [ ] **Step 1: Write failing tests**
  - Start a local test HTTP endpoint, post inbound mail, assert receiver responds successfully before a deliberately blocked downstream call completes.
  - Assert payload excludes `text`, `html`, `raw`, API keys, and passwords.
  - Assert HMAC signature verifies and event ID remains stable for a duplicate external ID/message.
  - Assert dispatch failure is logged and does not roll back the committed SQLite message.
- [ ] **Step 2: Run focused tests and verify failure**
  - Run `PYTHONPATH=. .venv/bin/python -m pytest tests/test_receiver_followup_contract.py -q`.
  - Expected: missing dispatch arguments/helper or missing event behavior.
- [ ] **Step 3: Implement minimal dispatch**
  - Commit SQLite state first.
  - Build a minimal event from stored identifiers and headers.
  - Use a daemon thread with bounded timeout; catch all network failures and emit a redacted structured event.
  - Add CLI args `--dispatch-url`, `--dispatch-secret`, `--dispatch-timeout` and pass through `serve`.
- [ ] **Step 4: Run focused tests**
  - The endpoint, non-blocking timing, signature, privacy, and persistence tests must pass.
- [ ] **Step 5: Commit**
  - `git add mailkit/mailkit/receiver.py mailkit/config.example.toml tests/test_receiver_followup_contract.py && git commit -m "feat: dispatch inbound follow-up events"`.

### Task 3: Follow-up worker with idempotency and single-flight execution

**Files:**
- Create: `mailkit/mailkit/followup_worker.py`
- Modify: `mailkit/config.example.toml`
- Test: `tests/test_followup_worker.py`

**Interfaces:**
- `EventLedger(path).claim(event_id) -> bool` atomically claims an event.
- `FollowupWorker.handle_event(event: dict) -> dict` returns `{status, event_id, run_id}`.
- `serve_worker(host, port, db, api_key, worker_config) -> ThreadingHTTPServer`.
- CLI module: `python -m mailkit.followup_worker --db ... --master ... --config ...`.

- [ ] **Step 1: Write failing tests**
  - First event claims once; duplicate event returns `duplicate` and does not invoke pipeline twice.
  - Two simultaneous events serialize access to the master CSV using a lock file or process lock.
  - A failed run records retryable status and bounded next attempt; it never marks success.
  - Worker refuses unsigned/invalid events and never invokes a send stage without approval.
  - Successful event calls reply synchronization and draft preparation, and returns a stable run ID.
- [ ] **Step 2: Run focused tests to verify failure**
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/test_followup_worker.py -q` must fail before implementation.
- [ ] **Step 3: Implement ledger and worker**
  - SQLite ledger schema stores event ID, message ID, status, attempts, timestamps, and run ID.
  - Verify HMAC before ledger access.
  - Acquire a single-flight lock around CSV/master mutation only.
  - Invoke existing sync/draft commands through subprocess with redacted logs.
  - Leave send approval as the existing orchestrator gate; no direct SMTP from worker.
- [ ] **Step 4: Add Docker role wiring**
  - Add `followup` role to `deploy/docker-entrypoint.sh` and a Compose service sharing existing volumes.
- [ ] **Step 5: Run focused tests and commit**
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/test_followup_worker.py tests/test_receiver_followup_contract.py -q`.
  - `git commit -m "feat: add idempotent inbound follow-up worker"`.

### Task 4: Compatibility polling and pipeline integration

**Files:**
- Modify: `mailkit/mailkit/fetch_replies.py`
- Modify: `scripts/run_full_pipeline.py`
- Modify: `scripts/rockbase_orchestrator.py`
- Test: `tests/test_full_pipeline.py`, `tests/test_mail_loop.py`

**Interfaces:**
- Push event and polling both feed the same `master_sync replies` idempotent path.
- Existing `--run-id`, state, and approval contracts remain unchanged.

- [ ] **Step 1: Add failing regression tests**
  - A message processed by push then fetched by polling changes the master once.
  - Polling still works when dispatch is unset.
  - Worker-triggered execution records run ID and stage state.
- [ ] **Step 2: Implement only shared-path reuse**
  - Do not add a second reply matcher or second CSV writer.
  - Make polling explicitly report fallback mode in structured output.
- [ ] **Step 3: Verify and commit**
  - Run the focused mail/pipeline suite, then commit `fix: unify push and polling reply synchronization`.

---

## Phase 2: Semantic LLM Boundaries

### Task 5: LLM reply intent classification with deterministic safety fallback

**Files:**
- Modify: `skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py`
- Test: `tests/test_semantic_boundaries.py`

**Interfaces:**
- `classify_reply_intent(row, latest_reply, client=None, model=...) -> IntentResult` with intent, confidence, reason, and `manual_review`.
- Existing deterministic `detect_intent` remains as `detect_intent_deterministic` fallback.

- [ ] **Step 1: Write failing tests**
  - Paraphrases such as budget timing, conditional interest, delegation, and opt-out map correctly under a fake OpenAI client.
  - Invalid/ambiguous model output falls back to deterministic classification and marks manual review when confidence is low.
  - Prompt contains untrusted reply text as delimited data and cannot change the output schema.
  - Existing keyword tests retain behavior when no client is configured.
- [ ] **Step 2: Implement schema-constrained call**
  - Use existing OpenAI SDK style and compatible `response_format` JSON object.
  - Validate intent against the fixed allow-list; never let model choose template code or destination.
  - Compute final template code through local `suggest_template` only.
- [ ] **Step 3: Verify and commit**
  - Focused tests, then `git commit -m "feat: classify reply intent semantically"`.

### Task 6: Semantic reply summaries and bounded master artifacts

**Files:**
- Modify: `mailkit/mailkit/master_sync.py`
- Create: `mailkit/mailkit/reply_semantics.py`
- Test: `tests/test_semantic_boundaries.py`

**Interfaces:**
- `summarize_reply(text, client=None, model=...) -> ReplySummary` containing `summary`, `conditions`, `next_action`, `language`, `confidence`.
- `summary_of` remains a deterministic fallback and is explicitly labeled preview/truncation.

- [ ] **Step 1: Write failing tests**
  - Fake LLM returns a structured summary; master receives bounded fields.
  - Timeout, invalid schema, or missing client stores deterministic preview and `summary_status=manual_review`.
  - Summary never includes secrets or unbounded body content.
- [ ] **Step 2: Implement**
  - Call LLM only for actual inbound reply text, not protocol headers.
  - Validate lengths and fields locally; preserve original evidence separately.
  - Keep matching and state transitions deterministic.
- [ ] **Step 3: Verify and commit**
  - Run semantic and mail-loop tests, commit `feat: add bounded semantic reply summaries`.

### Task 7: Keep translation and template routing deterministic where appropriate

**Files:**
- Modify: `skills/S3-ag-reply-recovery-sync-v3/scripts/translation_utils.py`
- Modify: `skills/S3-ag-reply-draft-ops/scripts/fill_reply_templates_from_master.py`
- Test: `tests/test_semantic_boundaries.py`

**Interfaces:**
- Local translation remains the default for operational normalization; semantic summary/classification carries business meaning.
- Template routing remains local and allow-listed after intent classification.

- [ ] **Step 1: Add tests proving no unnecessary LLM call**
  - Deterministic English text and schema values do not instantiate an LLM client.
  - Template code cannot be supplied by model output.
- [ ] **Step 2: Implement clean boundary documentation and explicit fallback labels**
  - Do not replace all translation with an LLM; only escalate when business meaning is required and configured.
- [ ] **Step 3: Verify and commit**
  - `git commit -m "refactor: keep deterministic follow-up policy local"`.

---

## Phase 3: Deterministic JSON Repair and Server OCR

### Task 8: Replace model-based JSON repair with local repair

**Files:**
- Modify: `skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py`
- Test: `tests/test_llm_json_repair.py`

**Interfaces:**
- `extract_json` accepts fenced JSON, balanced object extraction, trailing commas, and JSON scalar normalization without a second model call.
- `repair_once` is removed from the default path; model retry is reserved for semantic generation failure, not syntax repair.

- [ ] **Step 1: Write failing tests**
  - Trailing commas, fenced JSON, surrounding prose, and escaped quotes parse locally.
  - Malformed semantic content is rejected and marked for model retry/manual review rather than silently repaired.
  - Fake client call count proves no second call for syntax-only errors.
- [ ] **Step 2: Implement local parser/validator**
  - Use `json` and bounded scanning; never use `eval`.
  - Keep strict required-key and platform/order validation.
- [ ] **Step 3: Verify and commit**
  - `git commit -m "fix: repair llm json locally before retry"`.

### Task 9: Make S5 auto OCR server-safe

**Files:**
- Modify: `skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py`
- Modify: `deploy/docker-entrypoint.sh`
- Test: `tests/test_s5_ocr_llm.py`, `tests/test_docker_runtime_contract.py`

**Interfaces:**
- `auto` selects native Vision only on supported macOS, otherwise multimodal LLM when configured, then tesseract fallback.
- Explicit `--ocr-engine vision|tesseract|llm` remains authoritative.

- [ ] **Step 1: Write failing tests**
  - On Linux/container, `auto` does not invoke Swift Vision.
  - Configured `OPENAI_API_KEY` chooses multimodal path before tesseract.
  - No key falls back to tesseract and records the fallback engine.
- [ ] **Step 2: Implement capability selection**
  - Detect platform and key availability; preserve deterministic post-processing, matching, review thresholds, and blocked fields.
  - Add explicit engine choice to pipeline environment/config.
- [ ] **Step 3: Verify and commit**
  - Run OCR tests and Docker static contract tests, commit `fix: select server-safe automatic ocr engine`.

---

## Phase 4: Follow-up Schedule

### Task 10: Add due-date scheduler without automatic sending

**Files:**
- Create: `skills/S3-ag-reply-draft-ops/scripts/followup_scheduler.py`
- Modify: `mailkit/config.example.toml`
- Modify: `mailkit/mailkit/followup_worker.py`
- Test: `tests/test_followup_scheduler.py`

**Interfaces:**
- `compute_due_followup(row, now) -> DueFollowup | None`.
- `schedule_due_followups(master_csv, output_jsonl, now) -> list[DueFollowup]`.
- Due records contain row key, wave, due time, reason, and approval state; they do not contain credentials or send commands.

- [ ] **Step 1: Write failing tests**
  - Mail1 sent with no reply becomes due only after configured delay.
  - Any reply, opt-out, closed state, or existing draft suppresses the next automatic follow-up.
  - Timezone and DST handling is explicit and tested with UTC-aware datetimes.
  - Scheduler cannot invoke SMTP and worker leaves records at draft/approval state.
- [ ] **Step 2: Implement**
  - Reuse existing master status fields and configured delays; no new parallel status machine.
  - Use atomic JSONL output and stable job IDs.
- [ ] **Step 3: Wire worker and verify**
  - Push inbound event evaluates due follow-up and semantic reply path; a separate periodic scheduler can process no-reply deadlines.
  - Commit `feat: schedule safe follow-up drafts`.

---

## Phase 5: Documentation, Cross-Review, and Hardening

### Task 11: Update runtime and operator documentation

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/architecture/event-driven-followup.md`
- Modify: `docs/architecture/llm-boundaries.md`
- Test: `tests/test_docker_runtime_contract.py`

- [ ] **Step 1: Document deployment roles and data flow**
  - Add receiver -> event worker -> sync -> semantic classify/summary -> draft -> approval gate flow.
  - Document polling fallback, event HMAC, retry/ledger inspection, and no-send guarantee.
  - Keep English and Chinese files separate and cross-linked.
- [ ] **Step 2: Add contract assertions**
  - Compose includes receiver and follow-up roles with shared data/workbench volumes and no extra secret leakage.
- [ ] **Step 3: Verify docs and commit**
  - Run documentation lint/grep and commit `docs: document event-driven follow-up architecture`.

### Task 12: Full audit, adversarial Workflow, and optimization pass

**Files:**
- Potentially modify only files identified by verified findings.
- Create: `docs/audits/2026-09-23-event-followup-final.md`

- [ ] **Step 1: Run subagent attack reviews**
  - Security: HMAC, SSRF/dispatch URL, body/secret leakage, auth, replay.
  - Reliability: crash windows, duplicate events, lock recovery, retry storms, backpressure.
  - LLM: prompt injection, schema drift, cost/latency, fallback correctness, overuse/underuse.
  - Product: approval gates, opt-out, no-reply schedule, operator recovery.
- [ ] **Step 2: Run Workflow review**
  - Load `workflow-authoring`; run a bounded review workflow with independent architecture, security, AI, and test agents, then a verifier phase for every finding.
- [ ] **Step 3: Run architecture and code audits**
  - Use `ln-24-architecture-auditor`, `code-review-and-quality`, `security-review`, and `ai-system-testing` skills against the implemented tree.
  - Verify every surviving finding through a concrete call path and test.
- [ ] **Step 4: Apply fixes and repeat attacks**
  - Every confirmed P0/P1/P2 issue gets a focused test before code changes; repeat the relevant reviewer until no material finding remains.
- [ ] **Step 5: Final verification**
  - `PYTHONPATH=. .venv/bin/python -m pytest tests -q -p no:cacheprovider`.
  - Build `docker build -t rockbase:local .`.
  - Probe console, receiver, follow-up worker, pipeline plan, and health roles in isolated containers.
  - Run static secret/event payload checks and inspect git diff/status.
- [ ] **Step 6: Write final audit**
  - Include actual architecture, user requirement vs behavior, attack findings, resolved issues, residual risks, exact commands/results, and an explicit checklist of all twelve tasks.

**Definition of Done:** All tasks are checked, all focused and full tests pass, Docker roles build and probe successfully, every adversarial finding is resolved or explicitly documented with evidence, and the final audit is written.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Receiver dispatch blocks mail ingress | High | Commit first, daemon thread, bounded timeout, failure-only logging, test timing. |
| Duplicate push and polling writes CSV twice | High | Stable event ledger plus existing external-ID idempotency; test push-then-poll. |
| Concurrent workers corrupt master CSV | High | One process lock around mutation; crash-safe lock cleanup and recovery tests. |
| LLM prompt injection changes routing | High | Delimited input, fixed allow-list, model cannot choose destination/code, manual-review fallback. |
| LLM outage stalls follow-up | Medium | Deterministic fallback, retry budget, explicit manual-review state. |
| Server OCR loses native Vision behavior | Medium | Capability detection, multimodal path when configured, tesseract fallback and engine telemetry. |
| Scheduler bypasses human approval | High | Scheduler emits due draft jobs only; worker and orchestrator retain send gate. |
| Cross-review creates speculative refactors | Medium | Materiality gate: only correctness, security, ownership, deployment, or recurring maintenance findings survive. |

## Open Questions Resolved by Default

- Event delivery is at-least-once, not exactly-once; idempotency is the contract.
- The follow-up worker is a separate process role sharing the existing project data volume.
- Semantic LLM calls may draft and classify, but may not select policy destinations, bypass opt-out, or send mail.
- Google/other deterministic translation remains an operational normalization tool; it is not promoted to a business-decision engine.
- The periodic scheduler exists for no-reply deadlines; inbound replies trigger immediately through the worker.
