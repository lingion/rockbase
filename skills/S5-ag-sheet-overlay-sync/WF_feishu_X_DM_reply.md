# WF Feishu X DM Reply

## Purpose

Use this workflow when the user wants to reconcile reply evidence from screenshots or extracted name lists back into the Feishu online master by updating a reply-status column such as `DM 回复状态` or `DM二次回复状态`.

Typical requests:

- extract names from screenshots and mark replies in master
- if `DM 回复状态` is already `Y`, pass
- if a matched row has blank `DM 回复状态`, write `Y`
- tell me how many new `Y` were added today

Current target:

- target URL:
  - [https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7](https://ccn6eqlztbr4.feishu.cn/sheets/TD5JsKrCrhDmrztK9aEczmzInyh?sheet=GsQAL7)
- current target sheet:
  - `内部总表-Steve`
- current target `sheet_id`:
  - `GsQAL7`

## Scope

This workflow is for:

- screenshot-driven or manually extracted name list input
- Feishu online master as target
- reply-status-only updates
- preserving all unrelated fields, notes, colors, and highlights

Accepted structured inputs for the script:

- repeated `--name 'Person Name'`
- `--names-file` with one name per line
- `--names-json` with a JSON array of names

Names are automatically deduped after normalization before matching, because adjacent screenshots may contain repeated conversation names.

## Evidence Modes

Before matching names, first identify what the screenshot represents.

### `inbox_list`

Use this when the screenshot is an X DM conversation list / inbox list.

Business meaning:

- names shown in the list are treated as reply-positive conversation evidence
- the list itself is enough to mark the matched rows as replied candidates
- do not require a per-thread message-content re-interpretation such as checking whether preview text starts with `You:`

### `thread_detail`

Use this when the screenshot is a single conversation thread.

Business meaning:

- only names with clear counterparty reply evidence should be extracted and passed into reconcile
- do not mark a row replied just because the visible message is sent by us

### `manual_name_list`

Use this when the operator already curated the names outside the screenshot step.

Business meaning:

- trust the provided names as the intended reply candidates
- still keep conservative matching against master rows

## Scripts

- DM reply reconcile script:
  - relative path: `.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py`
  - absolute path: [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py)
- screenshot OCR helper:
  - relative path: `.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/extract_x_dm_reply_names_from_screenshots.py`
  - absolute path: [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/extract_x_dm_reply_names_from_screenshots.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/extract_x_dm_reply_names_from_screenshots.py)

## Auth And Transport

This workflow uses the same stable OpenAPI credential path as:

- relative path: `Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot`
- absolute path: [${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02 💼 Office/ag-feishu-copilot](${ROCKBASE_HOME}/Documents/github/AG-Skills-Hub/02%20💼%20Office/ag-feishu-copilot)

It reuses:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

from the shared runtime config used by `ag-feishu-copilot`.

## Core Design

This workflow must treat the Feishu master as the source of truth and change only one reply-status field per run:

1. read the full master header and rows
2. normalize screenshot names into match keys
3. match against master `频道/作者名称` and `账号ID`
4. choose the target reply column for this run, such as `DM 回复状态` or `DM二次回复状态`
5. if the target reply column = `Y`, pass
6. if the target reply column is blank, write `Y`
7. do not overwrite any non-blank non-`Y` status without explicit user instruction
8. never reorder rows
9. never touch unrelated columns

For a second-round DM reply run:

- prefer target reply column `DM二次回复状态`
- if that column does not exist yet and the sheet still has a blank header slot, create it only when `--create-reply-column-if-missing` is passed

## Matching Rules

Default matching should be conservative but practical:

- normalize spaces, punctuation, and casing
- allow matching against:
  - `频道/作者名称`
  - `账号ID` without leading `@`
- allow cleanup of cosmetic suffixes like punctuation or simple title markers

If a screenshot name maps to multiple candidate rows:

- do not guess
- mark the case as ambiguous
- exclude it from automatic write

Interpretation rule:

- ambiguity handling applies to row matching in Feishu master
- it does not mean the agent should second-guess the screenshot semantics after the operator has declared the evidence mode

## Backup Contract

Before every `apply` run, the script must create a local `xlsx` backup of the current master inside the run's `output-dir`.

Rules:

- backup happens automatically before any write
- backup file format must be `xlsx`
- backup file must be saved inside `workbench/{YYYY-MM-DD}/`
- if backup fails, stop before writing

## Output Contract

After each run, return the user-facing business summary first:

```text
今日 X-DM 状态更新 - YYYY-MM-DD
表格名单总数：
已发送 DM总数：
已发送 DM今日新增：
DM 已回复总数：
DM 已回复今日新增：
```

## Stats Method

The workflow must use the following fixed counting method:

- `表格名单总数`
  - total rows in target sheet where `账号ID` is non-empty
- `已发送 DM总数`
  - total rows in target sheet where `DM 发送状态 = Y`
  - exclude rows where `DM 发送状态 = DM 未开通`
- `已发送 DM今日新增`
  - latest known same-day send-sync increment where `DM 发送状态 = Y`
  - inherit this value from the latest same-day `feishu_master_append_audit.json` when available
  - do not recompute this value from reply screenshots
  - if there was no same-day send sync context, return `0`
- `DM 已回复总数`
  - total rows in target sheet where the target reply column = `Y` after this run
- `DM 已回复今日新增`
  - number of rows changed from blank target reply column to `Y` in this run

## Output Expression

The user-facing summary should use exactly this concise structure:

```text
今日 X-DM 状态更新 - YYYY-MM-DD
表格名单总数：
已发送 DM总数：
已发送 DM今日新增：
DM 已回复总数：
DM 已回复今日新增：
```

If needed, `DM 未开通数量` can be reported separately in a follow-up line or technical summary, but it must not be merged into `已发送 DM总数`.

Then include the technical reconcile summary:

- `截图名字总数`
- `命中 master 数量`
- `本来已经是 Y 的数量`
- `今日新写入 Y 的数量`
- `未命中数量`
- `歧义匹配数量`

This workflow should also provide:

- sample of new writes
- sample of already-`Y` rows
- unmatched names
- ambiguous matches

## Recommended Modes

### Dry Run

Use this first to preview match quality without touching master:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py' \
  --names-file 'NAMES.txt' \
  --mode dry-run \
  --output-dir 'workbench/YYYY-MM-DD'
```

If the source is screenshots, OCR them first:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/extract_x_dm_reply_names_from_screenshots.py' \
  --screenshots-dir '${ROCKBASE_HOME}/Downloads/未命名文件夹' \
  --output-dir 'workbench/YYYY-MM-DD'
```

### Apply

Use this only after the dry-run preview looks correct:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py' \
  --names-file 'NAMES.txt' \
  --mode apply \
  --output-dir 'workbench/YYYY-MM-DD'
```

Second-round DM reply writeback example:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py' \
  --names-file 'workbench/YYYY-MM-DD/x_dm_second_reply_names.txt' \
  --reply-column 'DM二次回复状态' \
  --create-reply-column-if-missing \
  --mode dry-run \
  --output-dir 'workbench/YYYY-MM-DD'
```

Alternative input examples:

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_dm_reply_reconcile/feishu_x_dm_reply_writeback.py' \
  --name 'Paul Solt' \
  --name 'Hasan Toor' \
  --mode dry-run \
  --output-dir 'workbench/YYYY-MM-DD'
```

If sheet title is unavailable or duplicated, use `--sheet-id` instead.

## Guardrails

- Never rewrite the whole sheet for this task.
- Never change row order for reply reconciliation.
- Never update unrelated columns.
- Never auto-resolve ambiguous matches.
- Never treat a visual conversation list as a reason to overwrite existing nonblank reply statuses unless the user explicitly asks.
- Never confuse `inbox_list` screenshots with `thread_detail` screenshots. Decide the evidence mode first, then reconcile.
- Do not physically move matched rows to the bottom of the master as part of writeback; use the second-round reply column plus a downstream view or sorted export instead.
