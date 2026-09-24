# S1-S5 LLM Decision Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned, Console-controlled approval protocol around LLM-generated S1-S5 artifacts while retaining a separately selectable fully automatic mode for non-forbidden stages.

**Architecture:** Introduce a shared artifact/decision contract in the existing local JSONL/run-state architecture. Every semantic stage produces a bounded artifact with deterministic validation results and pauses at a Console decision boundary in review mode; reject feedback creates a new artifact version and re-runs the LLM stage. Auto mode records a run-scoped pre-approval for non-forbidden stages but still produces the same artifacts, validation, and audit records. Real sending, production master writes, opt-out rejection, and invalid artifacts remain independently blocked.

**Tech Stack:** Python 3.11+, stdlib `http.server`, JSON/JSONL, existing `console/`, `scripts/rockbase_orchestrator.py`, `mailkit/`, OpenAI-compatible SDK already used by the repository, pytest, existing static Console frontend.

## Global Constraints

- Console is the only approval write entrypoint; CLI and approval files may inspect state but cannot create decisions.
- Users can approve, reject, or reject with feedback; users cannot edit generated business artifacts.
- Feedback is input to a new LLM generation attempt, not a direct field override.
- LLM handles language, intent, generation, semantic extraction, and visual interpretation; deterministic code handles protocol parsing, matching, dedupe, policy, limits, routing, serialization, and approval state.
- Every artifact is schema-validated, bounded, versioned, hashed, and auditable before it can advance.
- LLM failure, invalid schema, timeout, or low confidence becomes `manual_review`; it never silently auto-approves.
- `mailkit.send --execute`, `master_sync --execute`, and opt-out hard rejection remain outside `approve_run`.
- Existing send/sync approval behavior and polling fallback remain compatible.
- No credentials, full email bodies, or production data may enter events, logs, ordinary summaries, or approval records.
- Run only offline/local verification: `PYTHONPATH=. .venv/bin/python -m pytest tests -q -p no:cacheprovider`.
- Do not add a dependency unless the existing OpenAI-compatible SDK and stdlib cannot provide the contract.
- Do not push, tag, release, deploy, or call real third-party accounts as part of implementation.

---

## File and Boundary Map

### Shared decision protocol

- Create `rockbase/decision_models.py`: typed dictionaries/dataclasses and validation for artifact envelopes, stage validation results, decisions, feedback, and run mode.
- Create `rockbase/artifact_store.py`: atomic JSONL/JSON persistence, version allocation, content hashes, bounded payloads, and lookup by run/stage/artifact.
- Modify `scripts/rockbase_orchestrator.py`: stage decision boundary and auto/review policy evaluation; keep process execution and send/sync gates separate.
- Modify `scripts/run_full_pipeline.py`: accept `--mode review|auto`, run identifier, and artifact/decision directories; pass mode into the orchestrator.
- Test in `tests/test_decision_models.py`, `tests/test_artifact_store.py`, `tests/test_orchestrator_decisions.py`, and `tests/test_full_pipeline.py`.

### Console approval API and UI

- Modify `console/runs.py`: repository access to artifacts and decisions, Console-only decision methods, optimistic version checks, and auto-mode authorization records.
- Modify `console/server.py`: authenticated operator endpoints for listing artifacts, approving, rejecting, feedback rejection, and run-start mode selection.
- Modify `console/audit.py`: redact and record decision metadata without full business content.
- Modify `console/static/index.html`, `console/static/console.js`, and `console/static/console.css`: read-only artifact cards and decision controls.
- Test in `tests/test_console_runs.py`, `tests/test_console_http.py`, `tests/test_console_security.py`, and `tests/test_console_frontend.py`.

### S3 semantic stage

- Modify `skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py`: finish LLM intent classification integration and expose bounded artifact output.
- Create `mailkit/mailkit/reply_semantics.py`: summary, conditions, next action, language, confidence schema; LLM call plus deterministic fallback.
- Modify `mailkit/mailkit/master_sync.py`: consume bounded semantic artifact fields while retaining deterministic thread matching and CSV write logic.
- Modify `mailkit/mailkit/followup_worker.py`: create a semantic artifact and stop at the correct decision boundary.
- Modify `skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py`: keep local syntax repair and reserve retries for semantic/schema failure.
- Add `tests/test_semantic_boundaries.py`, extend `tests/test_followup_worker.py`, `tests/test_mail_loop.py`, and retain `tests/test_llm_json_repair.py`.

### S2, S5, S1, S4 adapters

- Create `rockbase/llm_stage_contracts.py`: stage-specific input/output validators and redacted summaries shared by adapters.
- Modify `skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py`: emit a versioned draft artifact; keep recipient, links, and send policy deterministic.
- Modify `skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py`: emit OCR artifact/validation data; preserve deterministic post-processing and engine selection.
- Create `skills/S5-ag-kol-brief-matching/scripts/brief_match.py`: LLM semantic matching followed by deterministic candidate and field validation.
- Create `skills/S1-inbox-enrichment/scripts/capability_adapter.py`: normalize S1 API export/apply outputs into artifact envelopes.
- Modify `skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/src/youtube_kol_discovery/pipelines/run_layer3_review.py`: emit candidate review artifacts without letting LLM choose storage or policy destinations.
- Modify `skills/S4-ag-kol-active-enrichment/scripts/apply_tag_llm_output.py` and `apply_x_bio_llm_output.py`: accept approved artifact versions and produce bounded write previews.
- Add stage-specific tests under `tests/test_stage_artifacts.py`, `tests/test_s2_artifacts.py`, `tests/test_s5_artifacts.py`, `tests/test_s1_artifacts.py`, and `tests/test_s4_artifacts.py`.

---

## Task 1: Finish and isolate the current S3 semantic prerequisites

**Files:**
- Modify: `skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py`
- Modify: `skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py`
- Create: `tests/test_semantic_boundaries.py`
- Test: `tests/test_llm_json_repair.py`

**Interfaces:**
- `classify_reply_intent(row, latest_reply, client=None, model="gpt-4o-mini") -> IntentResult`
- `extract_json(text: str) -> dict`
- `repair_once(...)` may retry only semantic/schema failures; syntax-only failures are repaired locally.

- [ ] **Step 1: Add failing intent tests**

```python
def test_paraphrased_budget_reply_uses_llm_intent(fake_client):
    result = classify_reply_intent({}, "We can discuss after next month's budget approval", fake_client)
    assert result.intent == "ask_budget_first"
    assert result.manual_review is False


def test_invalid_intent_falls_back_and_marks_review(fake_client):
    result = classify_reply_intent({}, "maybe later", fake_client_returning={"intent": "send_money"})
    assert result.intent == "manual_review"
    assert result.manual_review is True
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_semantic_boundaries.py -q -p no:cacheprovider`
Expected: FAIL because the new test module and semantic assertions are not present.

- [ ] **Step 3: Implement the minimal tested boundary**

Keep `ALLOWED_INTENTS` fixed. Delimit untrusted reply text in the prompt. Validate the model object locally, clamp reason length, set `manual_review` on invalid output/low confidence, and call the existing deterministic classifier when no client or a model error is present. Never accept template code or destination from model output.

- [ ] **Step 4: Add JSON repair assertions**

Add cases for fenced JSON, surrounding prose, trailing commas, nested braces, malformed semantic fields, no `eval`, and zero extra model calls for syntax-only repair.

- [ ] **Step 5: Run the focused tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_semantic_boundaries.py tests/test_llm_json_repair.py -q -p no:cacheprovider`
Expected: all focused tests pass.

- [ ] **Step 6: Commit the isolated prerequisite**

```bash
git add skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py skills/S3-ag-reply-recovery-sync-v3/scripts/run_part2_llm_batch.py tests/test_semantic_boundaries.py tests/test_llm_json_repair.py
git commit -m "feat(s3): add bounded semantic intent and local JSON repair"
```

## Task 2: Define and test artifact, validation, and decision envelopes

**Files:**
- Create: `rockbase/decision_models.py`
- Create: `rockbase/artifact_store.py`
- Create: `tests/test_decision_models.py`
- Create: `tests/test_artifact_store.py`

**Interfaces:**
- `ArtifactEnvelope.new(run_id, stage_id, payload, validation, *, parent_id=None) -> ArtifactEnvelope`
- `ArtifactEnvelope.content_hash() -> str`
- `ArtifactStore.put(artifact) -> ArtifactEnvelope`
- `ArtifactStore.get(artifact_id, version=None) -> ArtifactEnvelope | None`
- `ArtifactStore.list_for_run(run_id) -> list[ArtifactEnvelope]`
- `DecisionRequest(artifact_id, artifact_version, action, actor, feedback=None)`
- `validate_decision(request, artifact) -> None`

- [ ] **Step 1: Write failing model tests**

```python
def test_artifact_versions_are_monotonic_and_hashed(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.put(ArtifactEnvelope.new("run-1", "s3.intent", {"intent": "quoted"}, {"ok": True}))
    second = store.put(ArtifactEnvelope.new("run-1", "s3.intent", {"intent": "decline"}, {"ok": True}, parent_id=first.artifact_id))
    assert second.version == first.version + 1
    assert second.content_hash() != first.content_hash()
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_decision_models.py tests/test_artifact_store.py -q -p no:cacheprovider`
Expected: FAIL with missing modules/types.

- [ ] **Step 3: Implement bounded envelopes and atomic storage**

Store only redacted summaries and references required by the card. Write a temporary file, flush and `os.replace`; reject oversized payloads, invalid IDs, unknown actions, missing artifact versions, and feedback over the configured bound. Allocate versions per `(run_id, stage_id)` under a process/file lock.

- [ ] **Step 4: Add stale and forbidden decision tests**

Verify that a decision against an old version, a non-operator actor, a direct field override, or `approve_run` on a forbidden action is rejected without writing an audit record.

- [ ] **Step 5: Run focused tests and commit**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_decision_models.py tests/test_artifact_store.py -q -p no:cacheprovider`

```bash
git add rockbase/decision_models.py rockbase/artifact_store.py tests/test_decision_models.py tests/test_artifact_store.py
git commit -m "feat(approval): add versioned artifact and decision contracts"
```

## Task 3: Add stage decision boundaries to the orchestrator

**Files:**
- Modify: `scripts/rockbase_orchestrator.py`
- Modify: `scripts/run_full_pipeline.py`
- Create: `tests/test_orchestrator_decisions.py`
- Modify: `tests/test_full_pipeline.py`

**Interfaces:**
- `Stage(..., decision_stage: str | None = None, artifact_path: Path | None = None, forbidden_auto: bool = False)`
- `run_pipeline(..., mode="review", artifact_store=None, decision_store=None) -> int`
- State fields: `mode`, `policy_version`, `current_artifact_id`, `decision_status`.

- [ ] **Step 1: Write failing review/auto tests**

```python
def test_review_mode_pauses_after_artifact(tmp_path):
    rc = run_pipeline([stage_with_artifact], state_path=tmp_path / "state.json", mode="review")
    assert rc != 0
    assert json.loads((tmp_path / "state.json").read_text())["decision_status"] == "awaiting_approval"


def test_auto_mode_advances_non_forbidden_but_not_send(tmp_path):
    state = run_pipeline(stages, state_path=tmp_path / "state.json", mode="auto")
    assert state["stages"]["draft"]["status"] == "completed"
    assert state["stages"]["send"]["status"] == "gate-blocked"
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_orchestrator_decisions.py tests/test_full_pipeline.py -q -p no:cacheprovider`
Expected: FAIL because stage decisions and mode are not part of the current runner contract.

- [ ] **Step 3: Implement review pause and policy evaluation**

Persist run mode at start and refuse a later mode change. In review mode, stop after a valid artifact until a Console-created decision is present. In auto mode, record an authorization decision for non-forbidden stage artifacts, but route send/sync/production write stages through their existing independent gates.

- [ ] **Step 4: Verify resume, stale decision, and no-bypass behavior**

Test that approving the current artifact resumes once, duplicate decisions are idempotent, a stale decision is rejected, and auto mode cannot pass `execute-send` or `execute-sync` without the existing approvals.

- [ ] **Step 5: Run focused tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_orchestrator_decisions.py tests/test_full_pipeline.py -q -p no:cacheprovider
git add scripts/rockbase_orchestrator.py scripts/run_full_pipeline.py tests/test_orchestrator_decisions.py tests/test_full_pipeline.py
git commit -m "feat(orchestrator): pause stages for artifact decisions"
```

## Task 4: Add Console artifact cards and decision API

**Files:**
- Modify: `console/runs.py`
- Modify: `console/server.py`
- Modify: `console/audit.py`
- Modify: `tests/test_console_runs.py`
- Modify: `tests/test_console_http.py`
- Modify: `tests/test_console_security.py`

**Interfaces:**
- `RunManager.list_artifacts(run_id, stage_id=None) -> list[dict]`
- `RunManager.decide_artifact(run_id, artifact_id, version, action, feedback, actor, request_id) -> dict`
- `GET /api/runs/<run_id>/artifacts`
- `POST /api/runs/<run_id>/artifacts/<artifact_id>/decisions`
- Request body: `{artifact_version, action, feedback?}`

- [ ] **Step 1: Write failing HTTP contract tests**

```python
def test_operator_can_approve_current_artifact(client, seeded_run):
    response = client.post(f"/api/runs/{seeded_run}/artifacts/a1/decisions", json={"artifact_version": 1, "action": "approve"})
    assert response.status_code == 200
    assert response.json["decision"]["action"] == "approve"


def test_stale_or_direct_override_is_rejected(client, seeded_run):
    response = client.post(f"/api/runs/{seeded_run}/artifacts/a1/decisions", json={"artifact_version": 0, "action": "approve", "payload": {"intent": "decline"}})
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_console_runs.py tests/test_console_http.py tests/test_console_security.py -q -p no:cacheprovider`
Expected: FAIL with missing artifact routes and methods.

- [ ] **Step 3: Implement operator-only endpoints**

Reuse current session and CSRF checks. Validate artifact version and action in the domain model, derive actor from the authenticated session rather than request JSON, append redacted audit data, and never accept artifact payload overrides. Viewer sessions receive 403 for decision writes.

- [ ] **Step 4: Test feedback and idempotency**

Verify `reject_with_feedback` stores bounded feedback and creates a regeneration request, duplicate decision IDs do not duplicate execution, and all audit records include run/artifact/version/actor/request IDs without bodies or secrets.

- [ ] **Step 5: Run Console tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_console_runs.py tests/test_console_http.py tests/test_console_security.py -q -p no:cacheprovider
git add console tests/test_console_runs.py tests/test_console_http.py tests/test_console_security.py
git commit -m "feat(console): add artifact approval decisions"
```

## Task 5: Add read-only approval cards to the Console frontend

**Files:**
- Modify: `console/static/index.html`
- Modify: `console/static/console.js`
- Modify: `console/static/console.css`
- Modify: `tests/test_console_frontend.py`

**Interfaces:**
- Consume `GET /api/runs/<run_id>/artifacts`.
- Submit only the decision request contract from Task 4.

- [ ] **Step 1: Add frontend contract assertions**

Assert the static bundle contains artifact list rendering, validation summary rendering, approval/rejection controls, feedback submission, and no editable controls for generated payload fields.

- [ ] **Step 2: Run the frontend test to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_console_frontend.py -q -p no:cacheprovider`
Expected: FAIL because artifact cards and controls are absent.

- [ ] **Step 3: Implement the card**

Render stage, artifact version, bounded LLM result, confidence, validation counts, evidence references, pending action, and decision status. Use a textarea only for rejection feedback; generated fields remain text/read-only. Disable controls while a request is pending and display stale-version errors.

- [ ] **Step 4: Run frontend tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_console_frontend.py -q -p no:cacheprovider
git add console/static tests/test_console_frontend.py
git commit -m "feat(console): render read-only stage approval cards"
```

## Task 6: Complete S3 semantic artifacts and follow-up approval boundary

**Files:**
- Create: `mailkit/mailkit/reply_semantics.py`
- Modify: `mailkit/mailkit/master_sync.py`
- Modify: `mailkit/mailkit/followup_worker.py`
- Modify: `skills/S3-ag-reply-draft-ops/scripts/suggest_reply_templates.py`
- Create: `tests/test_semantic_boundaries.py` extensions
- Modify: `tests/test_followup_worker.py`
- Modify: `tests/test_mail_loop.py`

**Interfaces:**
- `summarize_reply(text, client=None, model="gpt-4o-mini") -> ReplySummary`
- `ReplySummary.to_artifact() -> dict`
- `FollowupWorker` returns `artifact_id`, `artifact_version`, and `decision_status` for semantic results.

- [ ] **Step 1: Write failing semantic tests**

```python
def test_reply_summary_extracts_conditions_and_next_action(fake_client):
    summary = summarize_reply("We can do $500 after the brief is approved", fake_client)
    assert summary.next_action == "send_brief"
    assert summary.conditions
    assert summary.manual_review is False


def test_summary_timeout_returns_bounded_manual_review(fake_timeout_client):
    summary = summarize_reply("long reply", fake_timeout_client)
    assert summary.manual_review is True
    assert len(summary.summary) <= 160
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_semantic_boundaries.py tests/test_followup_worker.py -q -p no:cacheprovider`
Expected: FAIL because `reply_semantics.py` and artifact handoff do not exist.

- [ ] **Step 3: Implement semantic summary and bounded fallback**

Use a fixed schema for `summary`, `conditions`, `next_action`, `language`, `confidence`. Delimit reply text, validate length and allow-lists locally, redact addresses/URLs/phones from the summary, and use the existing bounded preview as a manual-review fallback.

- [ ] **Step 4: Wire worker output without bypassing send**

The worker may synchronize, classify, summarize, and prepare a draft artifact. It must stop before `send --execute`; it must retain event idempotency and the master lock.

- [ ] **Step 5: Run S3/mail tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_semantic_boundaries.py tests/test_followup_worker.py tests/test_mail_loop.py tests/test_llm_json_repair.py -q -p no:cacheprovider
git add mailkit skills/S3-ag-reply-draft-ops tests/test_semantic_boundaries.py tests/test_followup_worker.py tests/test_mail_loop.py tests/test_llm_json_repair.py
git commit -m "feat(s3): add semantic reply artifacts and approval handoff"
```

## Task 7: Add S2 draft artifacts without giving LLM policy control

**Files:**
- Modify: `skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py`
- Modify: `skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`
- Create: `tests/test_s2_artifacts.py`

**Interfaces:**
- `build_mail1_artifact(row, generated_body, validation) -> dict`
- Artifact payload contains redacted input references, generated body, deterministic checks, and pending action; it does not contain a send command or recipient policy override.

- [ ] **Step 1: Write failing artifact tests**

Verify generated Mail1 text is bounded, sensitive fields are redacted from summaries, missing required fields become `manual_review`, and an LLM response cannot change recipient, link policy, or send mode.

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_s2_artifacts.py tests/test_s2_mail1_fill_llm.py -q -p no:cacheprovider`
Expected: FAIL because the artifact envelope is not emitted.

- [ ] **Step 3: Implement artifact emission and approval handoff**

Keep the existing dry-run default and manifest format. Add the artifact reference and validation summary alongside the existing report so old consumers continue to work. Only a later Console decision may advance the artifact to queueing; only the send gate can execute SMTP.

- [ ] **Step 4: Run tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_s2_artifacts.py tests/test_s2_mail1_fill_llm.py -q -p no:cacheprovider
git add skills/S2-ag-gmail-bulk-drafts skills/S1-inbox-kol-fuzzy-discovery-youtube-skill tests/test_s2_artifacts.py
git commit -m "feat(s2): expose Mail1 drafts as approval artifacts"
```

## Task 8: Add S5 OCR and semantic brief-matching artifacts

**Files:**
- Modify: `skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py`
- Create: `skills/S5-ag-kol-brief-matching/scripts/brief_match.py`
- Create: `tests/test_s5_artifacts.py`

**Interfaces:**
- `build_ocr_artifact(results, validation) -> dict`
- `match_brief_to_master(brief, rows, client=None) -> list[MatchResult]`
- `MatchResult` contains row key, semantic reason, confidence, deterministic constraints, and `manual_review`.

- [ ] **Step 1: Write failing OCR/matching tests**

Test LLM visual extraction for ambiguous layout, deterministic email/handle/percentage post-processing, duplicate image suppression, semantic brief candidates, confidence thresholds, and invalid model output fallback.

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_s5_artifacts.py tests/test_s5_ocr_llm.py -q -p no:cacheprovider`
Expected: FAIL because artifact output and brief matcher do not exist.

- [ ] **Step 3: Implement OCR artifact output**

Preserve Vision → LLM → tesseract engine selection and all current normalization/dedupe logic. Put only bounded extracted fields, validation counts, image references, and write diff in the artifact; never put raw image data or credentials in the card.

- [ ] **Step 4: Implement semantic brief matching**

Use LLM only to explain semantic relevance and rank candidates. Apply deterministic allow-lists, required fields, hard exclusions, row identity, and duplicate handling after the model. A model cannot select a row outside the deterministic candidate set.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_s5_artifacts.py tests/test_s5_ocr_llm.py -q -p no:cacheprovider
git add skills/S5-ag-ocr-sync skills/S5-ag-kol-brief-matching tests/test_s5_artifacts.py
git commit -m "feat(s5): add OCR and brief matching approval artifacts"
```

## Task 9: Add S1 candidate artifacts and S4 enrichment artifacts

**Files:**
- Create: `rockbase/llm_stage_contracts.py`
- Modify: `skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py`
- Modify: `skills/S1-inbox-enrichment/scripts/api/instagram_scrapecreators_s1_export.py`
- Modify: `skills/S1-inbox-enrichment/scripts/api/tiktok_scrapecreators_s1_export.py`
- Modify: `skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/src/youtube_kol_discovery/pipelines/run_layer3_review.py`
- Modify: `skills/S4-ag-kol-active-enrichment/scripts/apply_tag_llm_output.py`
- Modify: `skills/S4-ag-kol-active-enrichment/scripts/apply_x_bio_llm_output.py`
- Create: `tests/test_s1_artifacts.py`
- Create: `tests/test_s4_artifacts.py`

**Interfaces:**
- `build_candidate_artifact(rows, model_results, validation) -> dict`
- `build_enrichment_artifact(row_key, suggestions, evidence, validation) -> dict`
- `apply_approved_artifact(artifact_id, version, target, *, execute=False) -> dict`

- [ ] **Step 1: Write failing stage tests**

Test candidate relevance/entity classification, hard platform/API validation, S1 preview/apply separation, S4 label allow-list, evidence retention, low-confidence manual review, and refusal to apply an unapproved/stale artifact.

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_s1_artifacts.py tests/test_s4_artifacts.py -q -p no:cacheprovider`
Expected: FAIL because normalized artifact builders and approved-version checks do not exist.

- [ ] **Step 3: Implement S1 artifact adapters**

Let LLM classify semantic relevance and entity type, but keep API pagination, dedupe, platform identity, hard filters, and storage destination deterministic. Emit the candidate set and explanations as an approval artifact.

- [ ] **Step 4: Implement S4 artifact adapters**

Consume existing LLM JSONL outputs or configured LLM calls, validate labels and evidence locally, and require an approved artifact version before apply. Preserve backups and dry-run behavior.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_s1_artifacts.py tests/test_s4_artifacts.py -q -p no:cacheprovider
git add rockbase skills/S1-inbox-enrichment skills/S1-inbox-kol-fuzzy-discovery-youtube-skill skills/S4-ag-kol-active-enrichment tests/test_s1_artifacts.py tests/test_s4_artifacts.py
git commit -m "feat(stages): expose S1 and S4 semantic artifacts"
```

## Task 10: Add auto-mode run authorization and permanent safety gates

**Files:**
- Modify: `console/runs.py`
- Modify: `console/server.py`
- Modify: `scripts/rockbase_orchestrator.py`
- Modify: `scripts/run_full_pipeline.py`
- Create: `tests/test_auto_mode_safety.py`
- Modify: `tests/test_console_http.py`

**Interfaces:**
- Run start accepts `{mode: "review" | "auto", policy_version: str}`.
- `RunManager.authorize_auto_mode(run_id, actor, policy_version, request_id) -> dict`
- `is_forbidden_auto_action(stage_name, action) -> bool`

- [ ] **Step 1: Write failing safety tests**

Test mode is fixed at run start, auto mode records actor/policy, auto stages stop at invalid/manual-review artifacts, send/sync remain independently blocked, opt-out rows are never queued, and changing mode mid-run is rejected.

- [ ] **Step 2: Run focused tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_auto_mode_safety.py tests/test_console_http.py -q -p no:cacheprovider`
Expected: FAIL because run mode and forbidden-action policy do not exist.

- [ ] **Step 3: Implement policy and authorization**

Store `mode`, `policy_version`, `authorized_by`, and `authorized_at` in run state. Require the authenticated Console operator for auto start. Treat send execute, master production write, opt-out, invalid artifact, and manual-review artifact as forbidden; a run-level authorization cannot override them.

- [ ] **Step 4: Verify recovery and audit**

Ensure interrupted auto runs resume with the same mode/policy, duplicate authorization is idempotent, and every automatic advancement has an audit record referencing artifact hash and policy version.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_auto_mode_safety.py tests/test_console_http.py -q -p no:cacheprovider
git add console scripts tests/test_auto_mode_safety.py tests/test_console_http.py
git commit -m "feat(approval): add safe run-wide auto mode"
```

## Task 11: Full integration, docs, and regression verification

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/inventory/MIGRATION_STATUS.md`
- Modify: `docs/architecture/llm-boundaries.md`
- Modify: `docs/architecture/event-driven-followup.md`
- Modify: `tests/test_docker_runtime_contract.py`
- Create: `tests/test_approval_flow.py`

- [ ] **Step 1: Write end-to-end offline contract tests**

Test review mode through S3 artifact creation, Console approval, worker resume, semantic result, and blocked send; test reject-with-feedback creates a new artifact version; test auto mode advances non-forbidden stages but still blocks send/sync.

- [ ] **Step 2: Run the integration tests to verify failure**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_approval_flow.py tests/test_docker_runtime_contract.py -q -p no:cacheprovider`
Expected: FAIL until all stage and Console boundaries are wired.

- [ ] **Step 3: Update documentation from the implemented contract**

Document review/auto mode, Console-only decisions, artifact versioning, feedback regeneration, permanent safety gates, stage-specific LLM boundaries, polling fallback, and Docker role configuration in both README files and architecture docs. Keep the docs claim limited to the stages actually verified.

- [ ] **Step 4: Run the complete offline suite and static checks**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests -q -p no:cacheprovider
python -m compileall -q console mailkit rockbase scripts skills
python -m scripts.audit_server_paths .
```

Expected: all tests pass, compileall exits 0, and path-audit output is recorded without claiming historical assumptions are gone.

- [ ] **Step 5: Run Docker contract/build checks where available**

```bash
python -m pytest tests/test_docker_runtime_contract.py -q -p no:cacheprovider
docker build -t rockbase:local .
```

If Docker is unavailable, record the exact unavailable command and leave deployment verification incomplete; do not claim a successful image build.

- [ ] **Step 6: Commit documentation and integration tests**

```bash
git add README.md README.zh-CN.md docs/inventory/MIGRATION_STATUS.md docs/architecture tests/test_approval_flow.py tests/test_docker_runtime_contract.py
git commit -m "docs(approval): document S1-S5 decision workflow"
```

## Final Verification Checklist

- [ ] `PYTHONPATH=. .venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.
- [ ] `python -m compileall -q console mailkit rockbase scripts skills` passes.
- [ ] Review mode pauses at each configured artifact decision and resumes only after a current Console decision.
- [ ] Reject-with-feedback creates a new artifact version and never mutates the old artifact.
- [ ] Auto mode records operator/policy authorization and produces the same artifacts and audit trail as review mode.
- [ ] Auto mode cannot execute real send, production master write, opt-out override, or invalid/manual-review artifact.
- [ ] LLM is used for semantic intent, generation, extraction, language, and visual interpretation; deterministic code handles protocol, policy, matching, dedupe, limits, routing, and serialization.
- [ ] No full bodies, secrets, or raw images appear in event payloads, logs, approval summaries, or audit records.
- [ ] README and architecture docs match verified implementation, and residual real-account/deployment limitations are explicit.
