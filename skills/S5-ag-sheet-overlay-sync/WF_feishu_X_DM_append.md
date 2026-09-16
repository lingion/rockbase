# WF Feishu X DM Append

## Purpose

Use this workflow when the user wants to incrementally sync a local CSV into a Feishu online master sheet by appending only new rows.

Typical requests:

- add today's local sheet into online Feishu master
- dedupe against cloud master first
- append new rows to the bottom
- do not modify teammates' notes, colors, or highlights
- return DM status statistics after sync

Current target:

- target URL:
  - [https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7](https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7)
- current target sheet:
  - `内部总表-Steve`
- current target `sheet_id`:
  - `GsQAL7`

## Scope

This workflow is for:

- local CSV as source
- Feishu online sheet as target
- append-only sync
- online master maintenance with teammate-safe writes
- Scripts
- Feishu incremental sync script:

  - relative path: `.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py`
  - absolute path: [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py)

## Auth And Transport

This workflow uses the same stable OpenAPI credential path as:

- relative path: `Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot`
- absolute path: [${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot](${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02%20💼%20Office/ag-feishu-copilot)

It does not depend on `lark-cli` keychain auth for the actual read/write path.

Instead, it reuses:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

from the shared runtime config used by `ag-feishu-copilot`.

## Core Design

This workflow must treat the Feishu master schema as the only output contract.

It must:

1. read master metadata and header first
2. read existing `账号ID` and `账号链接`
3. dedupe local source against cloud master
4. if running `apply`, export the target sheet to local `xlsx` first
5. project source rows into master columns
6. set `DM 发送状态` from local source status column:
   - preferred source of truth: local `DM 发送状态`
   - `Y` -> write `Y`
   - `DM 未开通` -> write `DM 未开通`
   - if local `DM 发送状态` is blank, allow legacy fallback, then default `Y`
7. leave `DM 回复状态` empty unless specified
8. normalize selected presentation fields before write
9. write only into bottom empty rows
10. never touch existing rows

Implementation note:

- metadata read: Feishu Sheets OpenAPI
- values read: Feishu Sheets OpenAPI
- append write: Feishu Sheets OpenAPI
- backup export: local `xlsx` generated from the live sheet readback

## Backup Contract

Before every `apply` run, the script must create a local `xlsx` backup of the target Feishu sheet.

Rules:

- backup happens automatically before any write
- backup file format must be `xlsx`
- backup file must be saved inside the run's `output-dir`
- in production, `output-dir` should be the current day's `workbench/{YYYY-MM-DD}/`
- backup file naming format:
  - `feishu_master_backup_{YYYY-MM-DD}_{HHMMSS}.xlsx`
- if backup fails, the sync must stop before writing

This gives each production write a restorable point-in-time snapshot.

Current implementation detail:

- backup is generated from the live sheet values using OpenAPI + local `openpyxl`
- this avoids dependence on `lark-cli sheets +export`

## Field Normalization Rules

Before writing to Feishu master, the workflow should normalize these fields:

### `语言`

Use English labels, not Chinese labels.

Examples:

- `英语` -> `English`
- `日语` -> `Japanese`
- `中文` -> `Chinese`

If the source already uses a clean English label, keep it as is.

### `粉丝数`

Use pure digits only, without separators and without `K` / `M`.

Examples:

- `1233` -> `1233`
- `9.7K` -> `9700`
- `124.7K` -> `124700`
- `1.2M` -> `1200000`

Rules:

- convert compact social-style units to full raw integers
- remove comma separators before write
- write plain numeric strings only

## Why This Is Separate From Overlay Sync

This is not a classic "overlay" task.

The target is a shared online master with:

- teammate notes
- manual highlights
- color formatting
- cloud-only fields

So the correct operation is:

- `read -> dedupe -> append-only`

not:

- overwrite existing matching rows

## Current Tested Behavior

This workflow has already been validated on a sandbox Feishu copy:

- target URL:
  - [https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7](https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7)
- tested result:
  - appended `113` rows
  - updated range `GsQAL7!A428:BD540`
  - preserved existing rows
  - verified appended rows follow source-driven `DM 发送状态`

## Stats Contract

After each sync, return:

- `表格一共多少人账号`
- `今日新增多少账号`
- `已发送 DM 数量一共多少`
- `已发送 DM 数量今日新增多少`
- `DM 未开通数量一共多少`
- `DM 未开通数量今日新增多少`
- `DM 已回复一共多少`
- `DM 已回复今日新增多少`

Definitions:

- total accounts: non-empty `账号ID` rows in target
- today new accounts: rows appended in current run
- total DM sent: rows where `DM 发送状态 = Y`
- today new DM sent: appended rows where `DM 发送状态 = Y`
- total DM unavailable: rows where `DM 发送状态 = DM 未开通`
- today new DM unavailable: appended rows where `DM 发送状态 = DM 未开通`
- total replied: rows where `DM 回复状态 = Y`
- today new replied: appended rows where `DM 回复状态 = Y`

## Source Truth Rule

If the local source CSV already carries operational truth from the DM input workflow, preserve it when appending.

Rules:

- if source local `DM 发送状态 = Y`, append row with `DM 发送状态 = Y`
- if source local `DM 发送状态 = DM 未开通`, append row with `DM 发送状态 = DM 未开通`
- if source local `DM 发送状态` already has another explicit value, use that value directly
- only for legacy sources without local `DM 发送状态`, fallback to old fields such as `Mail1发出状态` or `备注`
- otherwise append row with `DM 发送状态 = Y`
- do not convert `DM 未开通` to `Y`
- counting logic must keep `Y` and `DM 未开通` separate

## Recommended Modes

For X fuzzy discovery runs, the default source CSV should now come from:

- relative path: `.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_filtered_dm_3.2.csv`

### Dry Run

Use this first to validate schema mapping and dedupe without touching Feishu:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py' \
  --source-csv '.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/deliverables/YYYY-MM-DD/【S2_cold】YYYY-MM-DD_x_kol_S2_merged_filtered_dm_3.2.csv' \
  --mode dry-run \
  --output-dir 'OUTPUT_DIR'
```

### Apply To Sandbox

Use this to verify write behavior safely:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py' \
  --source-csv '.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/deliverables/YYYY-MM-DD/【S2_cold】YYYY-MM-DD_x_kol_S2_merged_filtered_dm_3.2.csv' \
  --mode apply \
  --output-dir 'OUTPUT_DIR'
```

### Apply To Production Master

Only after dry-run and sandbox validation pass:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_append.py' \
  --source-csv '.agent/skills/S1-inbox-kol-fuzzy-discovery-x-skill/deliverables/YYYY-MM-DD/【S2_cold】YYYY-MM-DD_x_kol_S2_merged_filtered_dm_3.2.csv' \
  --mode apply \
  --output-dir 'workbench/YYYY-MM-DD'
```

The `apply` run will first export the current Feishu target into the same `output-dir` as a local `xlsx` backup, then continue with append-only sync.

## Guardrails

- Never use whole-sheet clear-and-rewrite logic on shared master.
- Never change master column order.
- Never rewrite existing rows just to "keep it clean".
- Never drop teammates' notes or manual formatting.
- Always test on a sandbox copy before first production use on a new schema.
- If `FEISHU_APP_ID` / `FEISHU_APP_SECRET` are unavailable, stop before write instead of falling back to a broken auth path.
- 
- 
-
