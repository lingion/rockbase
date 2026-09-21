# Implementation Plan: Phase 2 Server Orchestration

## Overview
Add a thin, resumable command-line orchestrator that runs the existing Rockbase jobs in order. It will own stage state and process artifacts; mailkit remains responsible for SMTP, receiving, rate limits, manifests, and master synchronization.

## Architecture Decisions
- Use one Python stdlib runner under `scripts/` rather than a workflow framework.
- Persist state as JSON beside the run artifacts. Each stage records `pending`, `running`, `completed`, or `failed`, timestamps, command, exit code, and artifact paths.
- Default to dry-run for every external write. A separate explicit execution flag is required for mail send and master write-back.
- Resume only completed artifacts and rerun the first incomplete stage; never silently skip a failed stage.
- Invoke existing scripts through subprocesses so each stage keeps its current CLI contract and can be run independently.
- Keep real account credentials in environment/configuration, never in state files or command logs.

## Task List

### Phase 2A: Runner foundation
- [ ] Task 1: Add state-file model and atomic state persistence.
- [ ] Task 2: Add command execution wrapper with captured stdout/stderr, timeout, and stage failure records.
- [ ] Task 3: Add `--plan`/dry-run mode that prints the ordered stages without running external writes.

### Checkpoint: Foundation
- [ ] Unit tests cover fresh state, atomic writes, resume after completed stage, and failed-stage stop.
- [ ] Existing full suite remains green.

### Phase 2B: First vertical pipeline
- [ ] Task 4: Implement S2 Mail1 generation stage and artifact discovery.
- [ ] Task 5: Implement mailkit send stage with dry-run default and explicit `--execute-send`.
- [ ] Task 6: Implement reply fetch and master sync stages with explicit `--execute-sync`.

### Checkpoint: Mail loop
- [ ] Local mailkit rehearsal proves plan -> draft/send dry-run -> fetch -> sync command ordering.
- [ ] A rerun does not repeat completed stages or send without the execution flag.

### Phase 2C: S1/S5 integration and operations
- [ ] Task 7: Add optional S1 export/apply and S5 OCR stages behind explicit inputs.
- [ ] Task 8: Add structured run summary and non-zero exit behavior for failed stages.
- [ ] Task 9: Add cron/systemd deployment example and operator recovery notes.

### Checkpoint: Complete
- [ ] Full offline suite and local end-to-end rehearsal pass.
- [ ] Dry-run and resume behavior are documented with a clean example.
- [ ] No production credentials or data are required by tests.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Existing script output/flags drift | Medium | Keep subprocess boundaries and add CLI contract tests. |
| A rerun sends duplicate mail | High | Respect mailkit manifest and require `--execute-send` on every send invocation. |
| State says completed while artifact is missing | High | Validate artifact existence before skipping a stage. |
| A master write is hard to undo | High | Keep sync dry-run default and require backup/report checks before execute. |
| Long-running API job hangs | Medium | Per-stage timeout and persisted failure state. |

## Open Questions
- The deployment team's exact cron or systemd environment and secret-manager mechanism are not yet specified. Keep the runner portable and provide both an example cron invocation and a systemd service template later.
