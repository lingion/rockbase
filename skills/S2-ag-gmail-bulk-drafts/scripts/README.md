# Scripts Layout

This directory is now split by workflow responsibility instead of mixing Gmail draft automation and X manual DM helpers in one flat folder.

## Active Folders

- `gmail/`
  - Canonical Gmail draft pipeline scripts
  - `fill_mail1_with_codex.py`
  - `prepare_jobs.py`
  - `sample_send.py`
  - `bulk_send.py`
  - `send_draft_batch.py`
  - `reconcile_drafts.py`
  - `dedupe_drafts.py`
- `x/`
  - Canonical X manual DM helper scripts
  - `open_x_profiles_in_adspower.py`
  - `apply_manual_dm_notes.py`
- `shared/`
  - Shared utility module used by active scripts
  - `common.py`
- `legacy/`
  - Historical or transitional scripts that are not current canonical entrypoints
  - `fill_x_dm_llm.py`
  - `fill_x_dm_with_codex.py`
  - `apply_x_dm_results.py`

## Canonical Entries

Use these as the default operational entrypoints:

- `scripts/gmail/prepare_jobs.py`
- `scripts/gmail/fill_mail1_with_codex.py`
- `scripts/gmail/sample_send.py`
- `scripts/gmail/bulk_send.py`
- `scripts/gmail/send_draft_batch.py`
- `scripts/gmail/reconcile_drafts.py`
- `scripts/gmail/dedupe_drafts.py`
- `scripts/x/open_x_profiles_in_adspower.py`
- `scripts/x/apply_manual_dm_notes.py`

## Important Notes

- `legacy/` scripts are kept for auditability and backward reference, not as preferred production paths.
- `WF_Cold Mail Run.md` should not treat `legacy/fill_x_dm_*` as a long-term Gmail-native solution.
- If a future Gmail-specific Mail1 filling runner is added, it should live under `scripts/gmail/`.
