# WF Feishu X DM 2nd Round Append

## Purpose

Use this workflow when a local X DM follow-up sheet has already been processed, and we need to write the second-round DM outcome back into the existing Feishu online master.

Current target:

- target URL:
  - [https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7](https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7)
- current target sheet:
  - `内部总表-Steve`
- current target `sheet_id`:
  - `GsQAL7`

Script entry:

- relative path:
  - `.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_2nd_round_writeback.py`
- absolute path:
  - [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_2nd_round_writeback.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_2nd_round_writeback.py)

## Scope

This workflow is for:

- local CSV as source
- Feishu online master as target
- existing-row writeback only
- second-round DM result sync

It is not for:

- appending new rows
- overwriting first-round `DM 发送状态`
- updating reply status
- rewriting unrelated teammate notes

## Source Truth

The local source of truth must be:

- `DM二次发送状态`

Accepted values:

- `Y`
- `DM 未开通`
- blank

Blank means:

- skip write
- do not clear existing Feishu cells

## Required Local Schema

The local CSV must include:

- `账号ID`
- `账号链接`
- `DM二次发送状态`

Recommended local placement:

- `DM 发送状态`
- `DM 回复状态`
- `DM二次发送状态`

The legacy local column `二次发送` may remain temporarily during transition, but this workflow only writes back `DM二次发送状态`.

## Required Feishu Schema

The target Feishu master must already contain:

- `账号ID`
- `账号链接`
- `DM二次发送状态`

If `DM二次发送状态` does not exist in Feishu:

- dry-run must stop
- report the missing target column
- do not fall back to writing `DM 发送状态`

## Matching Rules

Use the existing-row overlay matching order:

1. `账号链接`
2. `账号ID`

If neither produces a unique hit:

- keep the row in unmatched / ambiguous review
- do not write

## Backup Contract

Before every apply run:

1. read the live target sheet
2. export a local `xlsx` backup
3. save it into current `workbench/{YYYY-MM-DD}/`
4. stop before write if backup fails

Required naming style:

- `feishu_master_partial_overlay_backup_{YYYY-MM-DD}_{HHMMSS}.xlsx`

## Dry Run Contract

Dry-run must output:

- source rows
- matched rows
- changed rows
- unmatched rows
- ambiguous rows
- planned changes preview
- auth route used through inherited script behavior

Dry-run must not write any Feishu cell.

## Output Contract

After each run, return the user-facing business summary first:

```text
今日 X-DM 二轮写回 - YYYY-MM-DD
表格名单总数：
二轮状态已写入总数：
二轮状态今日新增写入：
二轮发送成功总数：
二轮 DM 未开通总数：
```

Then include the technical summary:

```text
技术摘要：
源表行数：
命中 Feishu 行数：
实际变更行数：
实际变更单元格数：
未命中数量：
歧义匹配数量：
```

## Apply Contract

Apply mode should:

1. create local backup first
2. write only matched rows
3. update only:
   - `DM二次发送状态`
4. preserve all unrelated cells

## Recommended Commands

### Dry Run

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_2nd_round_writeback.py' \
  --source-csv 'Agency/list-master/2026-05-19_X-second-round_human_dm_candidates.csv' \
  --mode dry-run \
  --output-dir 'workbench/YYYY-MM-DD'
```

### Apply

Only after dry-run looks correct:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_x_dm_2nd_round_writeback.py' \
  --source-csv 'Agency/list-master/2026-05-19_X-second-round_human_dm_candidates.csv' \
  --mode apply \
  --output-dir 'workbench/YYYY-MM-DD'
```

## Guardrails

- Never append duplicate creator rows for second-round DM status.
- Never overwrite `DM 发送状态` when the task is only about second-round status.
- Never use `备注` as the second-round system-of-record if `DM二次发送` exists.
- Always run dry-run first.
- If target Feishu schema is missing `DM二次发送状态`, stop before write.
