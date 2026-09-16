# Upgrade Log

Date: `2026-04-02`

## Todo

- Fix `L3 shortlist` so `drop` rows no longer leak into the formal shortlist output.
- Add a stable default batching rule for `ScrapeCreators`: `30` accounts per chunk.
- Make explicit `search_queries` win by default when they are present in the spec.
- Update skill docs to explain `query registry`, `discovery master`, and the real write timing.
- Record every upgrade in this file so future runs can trace why behavior changed.

## Completed

### 2026-04-02

- Updated `src/x_kol_discovery/layer3/ranking.py`
  - `shortlist` now keeps only `recommended_action in {keep, review}`.
- Updated `src/x_kol_discovery/pipelines/run_layer3_from_enriched.py`
  - Added explicit `keep / review / drop` counts to runlog and audit summary.
  - Audit now states that shortlist exports `keep/review` rows only.
- Updated `src/x_kol_discovery/config.py`
  - Added `layer2_enrichment_chunk_size` with default `30`.
- Updated `src/x_kol_discovery/task_spec.py`
  - Added spec support for `layer2.chunk_size` / `layer2_enrichment_chunk_size`.
  - Changed query precedence so explicit `search_queries` are used by default.
  - Added `search_query_mode=prefer_generated` escape hatch for old behavior.
- Updated `src/x_kol_discovery/pipelines/run_layer2_from_candidates.py`
  - Added `--chunk-size` and defaulted Layer2 enrichment to chunked execution.
  - Runlog and audit now record `chunk_size` and `chunk_count`.
- Updated `src/x_kol_discovery/pipelines/run_batch_pipeline.py`
  - Layer2 enrichment now runs in chunks instead of sending the whole eligible pool at once.
  - Runlog and audit now record chunk metadata.
- Updated `WF_Int.md`
  - Added the `Layer2` chunking checkpoint to the implementation plan.
  - Documented the real `discovery master` write timing and explicit query precedence.
- Updated `SKILL.md`
  - Documented `ScrapeCreators` default chunk size `30`.
  - Clarified that formal `L3 shortlist` should only contain `keep/review`.
  - Clarified that explicit spec queries override generated packs by default.
- Updated `L3-WF_to-S2-cold-outreach-mapping.md`
  - Documented that `S2` should map from filtered shortlist rows.
  - Clarified that `Layer2` email/contact data is intentionally carried into `S2`.

## Next Phase Plan

### Phase 2: Discovery Master + Formal Batch Runner

- Upgrade `discovery master` schema so write behavior is easier to audit.
  - Add clearer strategy fields such as first write source, latest write source, and last decision class.
- Change master persistence policy so only `keep/review` rows enter `discovery master` by default.
  - Goal: avoid `drop` rows polluting future dedupe and blocking better re-entry later.
- Add a one-command formal execution script for:
  - `eligible -> chunk by 30 -> Layer2 -> Layer3 -> merged summary`
  - Goal: reduce manual CSV splitting and reduce operator confusion during long runs.
- Add merged batch summary outputs.
  - Expected summary should show per-batch counts, provider sends, request errors, keep/review/drop totals, and merged shortlist stats.
- Add explicit rerun notes for `batch 2+`.
  - Goal: make it obvious when a rerun is blocked by `query registry` vs `discovery master`.
- Fix naming semantics between discovery batches and enrichment chunks.
  - Reserve `batch1 / batch2 / batch3` for new query/discovery rounds only.
  - Reserve `chunk01 / chunk02 / chunk03` for Layer2 chunked enrichment inside the same discovery batch.
  - Avoid names like `eligible122_b02` in future formal workflows because they can be misread as a new discovery batch.
