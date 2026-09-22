# Rockbase Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a localhost-first operations console that shows every persisted pipeline run and stage, and permits authorized operators to start, pause, resume, approve, and terminate runs with an append-only audit trail.

**Architecture:** Keep the existing JSON state file as the pipeline truth. Add a stdlib-only HTTP server that owns authentication, run process lifecycle, approval records, and audit events; serve a no-build static frontend from the same process. Extend the runner with cooperative stage-boundary pause, PID/process-group metadata, and console-scoped approval enforcement without changing bare CLI behavior.

**Tech Stack:** Python 3.10 stdlib (`http.server`, `subprocess`, `hashlib.pbkdf2_hmac`, `hmac`, `secrets`, `json`, `threading`), HTML/CSS/vanilla JavaScript, pytest.

## Global Constraints

- The console binds to `127.0.0.1:8790` by default; remote access is via TLS-terminating nginx or SSH tunnel.
- The frontend has no build step and no CDN dependencies.
- The backend adds no third-party runtime dependency and remains compatible with Python 3.10.
- The existing state JSON remains the single source of truth for stage status.
- Pause is cooperative and only takes effect between stages; it must never interrupt a stage midway.
- Force termination sends SIGTERM to the runner process group, waits 3 seconds, then sends SIGKILL if needed; resulting state is `interrupted`.
- Before any console-authorized write stage starts, it must have a current approval record for that gate; bare CLI behavior remains unchanged.
- Rerun/resume may change gates and retries; completed stages are still skipped when their artifacts exist, and every parameter diff is audited. Changed write gates require a fresh approval.
- Approval is single-operator, requires the batch label, expires after 24 hours, and is recorded in JSONL audit.
- Mutating HTTP endpoints require an authenticated operator and CSRF token. Viewer accounts are read-only.
- Never persist or return credential values in API responses, state, audit, or logs; reuse orchestrator redaction helpers where command output is involved.
- Do not read credentials from macOS Keychain. Use plaintext local files or user-provided values only; keep all actual secrets out of tracked files.
- Verify each task with its listed tests before moving on; do not deploy or expose the service externally as part of this plan.

---

## File Map

- `console/server.py`: HTTP routing, auth/session/CSRF, run listing/detail, mutation authorization, static-file serving, startup.
- `console/security.py`: user-file parsing, PBKDF2 verification, sessions, CSRF tokens, cookie helpers.
- `console/runs.py`: safe run discovery, state loading, run process lifecycle, pause/resume/kill, approval persistence and validation.
- `console/audit.py`: append-only JSONL writer and bounded reader; no secret or message-body fields.
- `console/static/index.html`: semantic page shell and accessible login/run/detail/control areas.
- `console/static/console.css`: responsive control-room layout, stage states, dialogs, reduced-motion behavior.
- `console/static/console.js`: login/session, run list/detail polling, stage rendering, guarded controls.
- `scripts/rockbase_orchestrator.py`: pause-marker check before each stage; runner PID and lifecycle state; console-scoped approval enforcement without changing CLI behavior.
- `scripts/run_full_pipeline.py`: accept/forward the console-only approval context and existing pipeline parameters.
- `tests/test_console_security.py`: passwords, sessions, CSRF, roles, cookies.
- `tests/test_console_runs.py`: run discovery, approvals, launch and controls, audit consequences.
- `tests/test_console_http.py`: real loopback HTTP contract tests and static resources.
- `tests/test_runner_pause.py`: deterministic stage-boundary pause, resume and interruption behavior.
- `tests/test_console_frontend.py`: static asset availability and DOM/API contract checks using available project test tools; no new runtime dependency.
- `deploy/rockbase-console.service`: systemd unit bound to loopback.
- `deploy/rockbase-console-nginx.conf`: example TLS reverse-proxy configuration; not enabled automatically.
- `.gitignore`: exclude console users, sessions, run metadata, approvals and audit data.
- `docs/console-operations.md`: local account provisioning, startup, proxy/tunnel, approvals, recovery, and verification.
- `README.md`: concise pointer to the operations guide.
- `docs/inventory/MIGRATION_STATUS.md`: record console completion and remaining host-integration gaps.

## Task 1: Configuration and Private Data Paths

**Files:**
- Create: `console/__init__.py`
- Create: `console/config.py`
- Modify: `.gitignore`
- Test: `tests/test_console_security.py`

**Interfaces:**
- `ConsoleConfig.from_env(environ: Mapping[str, str] | None = None) -> ConsoleConfig`.
- Fields: `host`, `port`, `repo_root`, `runs_dir`, `users_file`, `session_file`, `approval_dir`, `audit_file`, `cookie_secure`, `session_ttl_seconds`.
- Default bind is `127.0.0.1:8790`; runtime writable data defaults under `/etc/rockbase/console`, with test overrides via environment.

- [ ] **Step 1: Write config tests** for default host/port, env overrides, invalid port/TTL, and refusal of non-loopback bind unless `ROCKBASE_CONSOLE_ALLOW_REMOTE=1`.
- [ ] **Step 2: Run `pytest tests/test_console_security.py -q`**; confirm the config tests fail because the module is absent.
- [ ] **Step 3: Implement typed config parsing** with resolved filesystem paths and no secret values in errors or logs.
- [ ] **Step 4: Add gitignore rules** for `console/users.toml`, `console/state/`, `console/sessions.json`, `console/approvals/`, `console/audit.jsonl`, and local secret files.
- [ ] **Step 5: Run `pytest tests/test_console_security.py -q`** and verify config tests pass; confirm no runtime data appeared in the repository.

## Task 2: Authentication, Roles, Sessions, and CSRF

**Files:**
- Create: `console/security.py`
- Modify: `console/config.py`
- Test: `tests/test_console_security.py`

**Interfaces:**
- `load_users(path: Path) -> dict[str, User]` reads TOML `[[users]]` entries: `username`, `role`, `salt_hex`, `password_hash_hex`, `iterations`.
- `verify_password(user: User, password: str) -> bool` uses `hashlib.pbkdf2_hmac("sha256", ...)` and `hmac.compare_digest`.
- `SessionStore.create(username: str) -> Session`; `get(session_id: str) -> Session | None`; `revoke(session_id: str) -> None`.
- `Session` contains session ID, CSRF token, creation/expiry timestamps, username and role. Persist only hashed session IDs using atomic JSON replacement.
- `require_role(session: Session, role: Literal["viewer", "operator"]) -> bool` enforces viewer < operator.

- [ ] **Step 1: Write failing tests** for valid/invalid password, unknown user, role ordering, session expiry/revoke, CSRF token generation, cookie attributes, and malformed user file.
- [ ] **Step 2: Run `pytest tests/test_console_security.py -q`** and confirm the new cases fail.
- [ ] **Step 3: Implement PBKDF2 verification and user loading**; reject unknown roles and invalid hex/iteration values without exposing hashes.
- [ ] **Step 4: Implement sessions** with `secrets.token_urlsafe`, constant-time token checks, expiry, atomic JSON writes and restrictive file permissions where supported.
- [ ] **Step 5: Run `pytest tests/test_console_security.py -q`** and verify all security tests pass.

## Task 3: Audit, Run Discovery, and Approval Records

**Files:**
- Create: `console/audit.py`
- Create: `console/runs.py`
- Test: `tests/test_console_runs.py`

**Interfaces:**
- `AuditLog.append(event: str, *, request_id: str, actor: str, run_id: str | None = None, details: dict | None = None) -> None` writes one JSON line under a process lock, flushes and fsyncs.
- `AuditLog.tail(limit: int) -> list[dict]` caps limit at 500 and returns newest events chronologically.
- `RunRepository.list_runs() -> list[dict]`; `get_run(run_id: str) -> dict | None` reads validated state JSON only from configured run roots.
- `ApprovalStore.approve(run_id: str, gate: str, actor: str, batch_label: str, now: datetime) -> dict`; `validate(run_id: str, gate: str, now: datetime) -> bool`; only `send` and `sync` gates are accepted, expiry is 24 hours.
- Run IDs are opaque safe identifiers; reject traversal, symlinks escaping configured roots, oversized state files and malformed JSON.

- [ ] **Step 1: Write failing tests** for audit append/tail/line integrity, traversal rejection, malformed state isolation, ordering, gate-specific approval, label validation and expiry.
- [ ] **Step 2: Run `pytest tests/test_console_runs.py -q`** and verify failures.
- [ ] **Step 3: Implement allowlisted JSONL audit fields** (`event`, `request_id`, `actor`, `run_id`, timestamp, result and bounded safe details); do not persist arbitrary request bodies, commands, output or credentials.
- [ ] **Step 4: Implement run repository and approval storage** with atomic approval-file replacement and strict gate/label validation.
- [ ] **Step 5: Run `pytest tests/test_console_runs.py -q`** and verify data-layer tests pass.

## Task 4: Runner Pause, PID Metadata, and Console Approval Gate

**Files:**
- Modify: `scripts/rockbase_orchestrator.py`
- Modify: `scripts/run_full_pipeline.py`
- Test: `tests/test_runner_pause.py`
- Modify: `tests/test_orchestrator.py`

**Interfaces:**
- Extend `run_pipeline(..., pause_file: Path | None = None, approval_file: Path | None = None, console_run: bool = False) -> int`.
- Before each stage, if `pause_file` exists, persist top-level `status="paused"`, `paused_at`, keep that stage pending, print summary and return 0.
- Persist runner PID and process-group ID at pipeline start; clear PID fields on normal completion/failure; on termination persist `status="interrupted"` and return a signal-derived nonzero code.
- Before a console-run write stage, validate a current matching approval record. Missing, expired or wrong-gate approval prevents invocation and records a gate-blocked failure. `console_run=False` retains current CLI semantics.
- `run_full_pipeline.py` accepts private console context options and passes them to `run_pipeline`; existing defaults remain unchanged.

- [ ] **Step 1: Write failing two-stage tests** that create a pause marker after stage one, assert stage two is not invoked and state is paused, then clear the marker and assert resume skips stage one and runs stage two.
- [ ] **Step 2: Write approval tests** proving console send/sync is blocked without matching approval, allowed with valid approval and unchanged for ordinary CLI runs.
- [ ] **Step 3: Write process metadata tests** checking PID/process group persistence and clearing after normal completion.
- [ ] **Step 4: Run `pytest tests/test_runner_pause.py tests/test_orchestrator.py -q`** and confirm new behavior is missing.
- [ ] **Step 5: Implement pause checks, atomic state transitions, PID metadata and console-only approval validation** while preserving artifact-based resume behavior.
- [ ] **Step 6: Run `pytest tests/test_runner_pause.py tests/test_orchestrator.py tests/test_full_pipeline.py tests/test_mail_loop.py -q`** and verify all pass.

## Task 5: Run Lifecycle and Operator Controls

**Files:**
- Modify: `console/runs.py`
- Modify: `scripts/rockbase_health.py`
- Test: `tests/test_console_runs.py`
- Modify: `tests/test_phase3_ops.py`

**Interfaces:**
- `RunManager.start(parameters: dict, actor: str, request_id: str) -> dict` validates an allowlisted schema and launches the existing full-pipeline runner in a new process session.
- `pause(run_id, actor, request_id) -> dict` creates the pause marker only for an active run.
- `resume(run_id, parameters: dict | None, actor, request_id) -> dict` clears the pause marker, validates changed gates/retries, records old/new parameter diffs, ensures changed write gates have fresh approval, then launches the same state file.
- `kill(run_id, actor, request_id) -> dict` sends SIGTERM to the process group, waits at most 3 seconds, sends SIGKILL if needed, then reconciles state: top-level `status="interrupted"`, and every stage still recorded as `running`/`retrying` is rewritten to `status="failed"`, `returncode=None`, `error="interrupted by console kill"`. This matters because `scripts/rockbase_health.py::inspect_state` classifies a still-`running` stage as "degraded" — without this rewrite, a killed run would report degraded health forever instead of a real failure.
- Only one active process may own a state file; lock transitions and recheck process liveness.

- [ ] **Step 1: Write failing lifecycle tests** for parameter allowlist, duplicate active run rejection, pause marker, same-state resume, changed-gate audit, fresh-approval requirement and kill escalation against a controllable child process.
- [ ] **Step 2: Run `pytest tests/test_console_runs.py -q`** and confirm the lifecycle cases fail.
- [ ] **Step 3: Implement argument construction** from existing `run_full_pipeline.py` flags; reject arbitrary executable paths and shell strings from API input.
- [ ] **Step 4: Implement `Popen(..., start_new_session=True)` lifecycle** with per-run locks, bounded waits and PID validation.
- [ ] **Step 5: Persist only redacted parameters;** create a current 24-hour approval when a write gate is newly enabled or its approval is invalid; audit exact old/new gate and retry values.
- [ ] **Step 6: Add health regression coverage** proving an interrupted top-level run with no `running`/`retrying` stages is reported as `critical` (exit 2), not `degraded`; preserve the existing running-stage degraded behavior.
- [ ] **Step 7: Run `pytest tests/test_console_runs.py tests/test_phase3_ops.py -q`** and verify all run-control and health tests pass.

## Task 6: HTTP API and Static Resource Server

**Files:**
- Create: `console/server.py`
- Test: `tests/test_console_http.py`

**Interfaces:**
- `make_server(config: ConsoleConfig, *, run_manager: RunManager, sessions: SessionStore, users: dict[str, User], audit: AuditLog) -> ThreadingHTTPServer`.
- Implement spec routes: login/logout/me; run list/detail/start; run pause/resume/kill/approve; health; audit.
- JSON request body limit is 64 KiB. Reject invalid JSON, unknown fields, unsupported content type, oversized body and malformed IDs with stable 4xx responses.
- Responses include `X-Content-Type-Options: nosniff`, API `Cache-Control: no-store`, `X-Request-Id`, and restrictive CSP for HTML.
- Health reveals only health summary. All run/audit routes require a session; every mutation requires operator role and CSRF.

- [ ] **Step 1: Write real loopback HTTP tests** for endpoint authentication, role and CSRF matrix, request validation, request IDs, security headers and static resource paths.
- [ ] **Step 2: Run `pytest tests/test_console_http.py -q`** and confirm new route tests fail.
- [ ] **Step 3: Implement explicit route dispatch**; do not use `eval`, shell interpolation or request-derived filesystem paths.
- [ ] **Step 4: Implement login/logout/me cookies** with HttpOnly, SameSite=Strict, Path=/, bounded Max-Age and Secure when configured behind TLS.
- [ ] **Step 5: Route each mutation through role, CSRF, schema validation, request-ID audit and structured error handling.**
- [ ] **Step 6: Serve files only from `console/static`;** reject traversal/symlink escapes and use correct MIME types.
- [ ] **Step 7: Run `pytest tests/test_console_http.py -q`** and verify all endpoint and static-resource tests pass, including one run launched and paused through HTTP.

## Task 7: Responsive Operations UI

**Files:**
- Create: `console/static/index.html`
- Create: `console/static/console.css`
- Create: `console/static/console.js`
- Test: `tests/test_console_frontend.py`

**Interfaces:**
- UI consumes only documented API routes; poll selected run every 2 seconds while visible and stop when document is hidden.
- Render the actual `state.stages` object (a name→record dict, not a list) from state. Do not hard-code the conceptual five design steps as a fixed runner stage list. The runner's real stages come from `build_full_pipeline_stages(...)`, which currently yields names like `s1_export`, `s2_mail1_generate`, `mailkit_send`, `fetch_replies`, `master_sync_sent`, `master_sync_replies`, and optionally `s5_ocr`; the UI must display whatever names appear, in their actual order.
- Controls follow role and run state. Kill requires a second confirmation displaying run ID and batch label; approval requires typed batch label.

- [ ] **Step 1: Add DOM/API contract tests** for login, run list, dynamic timeline, stage detail/logs, audit region, action controls and absence of external scripts/styles.
- [ ] **Step 2: Run `pytest tests/test_console_frontend.py -q`** and verify asset tests fail before creation.
- [ ] **Step 3: Build semantic HTML** with login, run navigation, dynamic stage timeline, current-stage details, accessible status announcements, audit tail and confirmation dialogs.
- [ ] **Step 4: Implement responsive CSS** using approved cold gray/steel cyan and four signal colors; provide visible focus, avoid mobile overflow and honor `prefers-reduced-motion`.
- [ ] **Step 5: Implement vanilla JS** for session handling, two-second visible-page polling, safe text rendering through `textContent`, role-aware controls and explicit success/error states.
- [ ] **Step 6: Run frontend contract tests** and statically verify no remote assets and no API-data use through `innerHTML`.

## Task 8: Deployment, Operations Documentation, and Inventory

**Files:**
- Create: `deploy/rockbase-console.service`
- Create: `deploy/rockbase-console-nginx.conf`
- Create: `docs/console-operations.md`
- Modify: `README.md`
- Modify: `docs/inventory/MIGRATION_STATUS.md`

- [ ] **Step 1: Define docs acceptance coverage** for loopback bind, account file provisioning/permissions, local health check, SSH tunnel, nginx TLS proxy, backup/recovery, approval expiry and force-kill recovery.
- [ ] **Step 2: Add systemd unit** running `python3 -m console.server` as a dedicated unprivileged account, with working directory, environment file, `UMask=0077`, `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict`, and explicit writable paths.
- [ ] **Step 3: Add nginx example** proxying only to `127.0.0.1:8790`, setting forwarded proto/host headers and TLS configuration placeholders; document certificate provisioning without performing deployment.
- [ ] **Step 4: Document account creation** with a local one-shot Python command using `hashlib.pbkdf2_hmac`; do not put usable passwords or generated hashes in tracked docs.
- [ ] **Step 5: Link the operations guide from README** and update migration status with delivered console scope and remaining notification, secret-manager and real-account acceptance work.
- [ ] **Step 6: Run `pytest -q` and `python3 scripts/audit_server_paths.py .`;** investigate new failures/blockers rather than suppressing them.
- [ ] **Step 7: Review final diff** for secrets, traversal, shell use, fixed-stage assumptions, destructive file operations and spec mismatches.

## Final Acceptance

- Viewer can inspect all discovered runs and their actual stages, status, attempts, exit codes and redacted captured output; viewer cannot mutate runs.
- Operator can start a dry-run, pause at a stage boundary, resume the same state, approve a write gate with a batch label and force-kill with double confirmation.
- A console write stage never starts without a matching unexpired approval; enabling a write gate during rerun requires fresh approval and produces a parameter-diff audit event.
- Kill targets only the managed process group; resumed runs use existing artifact validation and mailkit idempotency/backup safeguards.
- Login, failed authorization, controls, approvals, parameter changes and outcomes are auditable with request IDs; secrets do not appear in state, audit or responses.
- Full tests and path audit pass; service defaults to loopback; no deployment or external exposure is performed.