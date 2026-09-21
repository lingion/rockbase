# Phase 2 Orchestration Checklist

- [x] Inspect existing runner/script conventions and test layout.
- [x] Add atomic JSON state model.
- [x] Add subprocess stage runner with timeout and failure persistence.
- [x] Add plan/dry-run CLI surface.
- [x] Add first vertical S2 -> mailkit send/fetch/sync pipeline.
- [x] Add local contract tests for ordering, resume, and independent execution gates.
- [x] Run focused tests and the full offline suite (38 passed; mailkit smoke 35 checks).
- [x] Review documentation, cron/systemd examples, and recovery notes.
- [x] Add optional S1 export/apply, S2 generation, and S5 OCR stages.
- [x] Add structured summaries, retries, and non-zero failure behavior.
- [ ] Add service-level alerts and host-specific secret-manager integration.
