# Phase 2 Orchestration Checklist

- [x] Inspect existing runner/script conventions and test layout.
- [x] Add atomic JSON state model.
- [x] Add subprocess stage runner with timeout and failure persistence.
- [x] Add plan/dry-run CLI surface.
- [ ] Add first vertical S2 -> mailkit send pipeline.
- [ ] Add local contract tests for ordering, resume, and execution gates.
- [~] Local contract tests currently cover resume/failure/plan behavior; ordering and send execution gates remain for the next slice.
- [x] Run focused tests and the full offline suite (28 passed after foundation slice).
- [ ] Review documentation and deployment examples.
