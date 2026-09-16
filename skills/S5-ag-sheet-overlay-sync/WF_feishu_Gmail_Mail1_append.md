# WF Feishu Gmail Mail1 Append

## Purpose

Use this workflow when Gmail drafts have already been created, and only after user confirmation we should sync the same creator list into the Feishu online master sheet:

- target URL:
  - [https://ccn6eqlztbr4.feishu.cn/sheets/CTIXstF9eheJCztRfPdcZlKunYd](https://ccn6eqlztbr4.feishu.cn/sheets/CTIXstF9eheJCztRfPdcZlKunYd)
- current target sheet:
  - `Sheet1`
- current target `sheet_id`:
  - `8LE4hy`

This workflow is for a `Mail1`-style outbound tracker, not a DM tracker.

Script entry:

- relative path:
  - `.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_gmail_mail1_append.py`
- absolute path:
  - [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_gmail_mail1_append.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/feishu_master_incremental_sync/feishu_gmail_mail1_append.py)

Core requirement:

1. Gmail drafts are created first
2. user reviews and confirms
3. only then append rows into Feishu master
4. append rows with `Mail1发送 = Y`
5. leave `Mail1 回复` empty

## Scope

This workflow is for:

- local CSV as source
- Feishu online sheet as target
- append-only sync
- post-draft confirmation gate
- `Mail1` mail-tracking schema

It is not for:

- rewriting existing rows
- updating reply status
- DM status sync

## Current Target Schema

As read from the live sheet on `2026-04-27`, the target header is:

1. `分区`
2. `账号ID`
3. `频道/作者名称`
4. `Mail1发送`
5. `Mail1 回复`
6. `报价标准化`
7. `报价原文`
8. `平台`
9. `多平台标记`
10. `账号链接`
11. `语言`
12. `博主国家`
13. `粉丝数`
14. `账号类目标签__平台抓取`
15. `置顶最高播放`
16. `原价`
17. `账号简介`
18. `账号简介__平台抓取`
19. `联系方式`
20. `联系方式备注`
21. `外链__平台抓取`

## Source Truth And Confirmation Gate

This workflow must not run immediately after draft creation without a human checkpoint.

Required gate:

1. create Gmail drafts first
2. return sample / draft result to user
3. user explicitly confirms the synced batch
4. source rows must already pass `obvious-org + dirty-contact hygiene`
5. then run Feishu append

In short:

- Gmail draft creation is execution step A
- Feishu append is execution step B
- B must not happen automatically without user confirmation

Date rule:

- the first column `分区` must store the actual Feishu append date
- do not write the source deliverable date into `分区`
- if source batch is `2026-05-12` but append happens on `2026-05-13`, then write `分区 = 2026-05-13`
- source batch date should be kept in audit / summary context only

## Field Mapping Contract

The Feishu master schema is the only output contract.

Recommended source for this workflow:

- relative path:
  - `workbench/{YYYY-MM-DD}/youtube_kol_L3_final80_ecom_realestate_email_enriched_*.csv`

Recommended mapping:

| Feishu Column | Source Column / Rule |
| :-- | :-- |
| `分区` | actual Feishu write date, for example `2026-05-13`; use sync date, not source deliverable date |
| `账号ID` | prefer platform-style public handle if available; fallback to source `creator_handle` |
| `频道/作者名称` | `display_name` |
| `Mail1发送` | fixed `Y` after confirmed draft creation |
| `Mail1 回复` | empty string |
| `报价标准化` | empty by default unless already available |
| `报价原文` | empty by default unless already available |
| `平台` | fixed `YouTube` for current run |
| `多平台标记` | keep source value if available, else empty |
| `账号链接` | prefer `profile_url`; fallback to channel URL |
| `语言` | normalized language label; current batch usually `English` |
| `博主国家` | country signal if available, else empty |
| `粉丝数` | `followers_count`, normalized to full raw integer string such as `1200`, `54300`, `1000000` |
| `账号类目标签__平台抓取` | best available tag field such as category / query / content tags |
| `置顶最高播放` | `max_views` or best content view signal |
| `原价` | empty unless negotiated rate already exists |
| `账号简介` | `bio` |
| `账号简介__平台抓取` | same as `bio` when no second source exists |
| `联系方式` | `email` |
| `联系方式备注` | `contact_note` or `email_qc_flag` |
| `外链__平台抓取` | `external_links` |

## Identity And Dedupe Rules

This workflow is append-only, but cloud dedupe must happen first.

Preferred dedupe keys:

1. `账号链接`
2. `账号ID`

Rules:

- if cloud master already has the same `账号链接`, skip append
- if `账号链接` is missing but `账号ID` matches, skip append
- only append true net-new rows
- never rewrite existing rows in this workflow

## Hygiene Gate

Before append:

- source rows with `manual_clean_decision = drop` must be excluded
- source rows with `email_qc_flag in {dirty, invalid, suspect}` must be excluded
- source rows with `粉丝数 <= 1000` must be excluded
- obvious junk emails such as image-asset strings or telemetry domains must not reach Feishu

This gate is intentionally conservative. If a row is uncertain, keep it in local review/audit first and do not append it.

Follower formatting rule:

- `粉丝数` must be written as pure digits
- do not use `K` / `M`
- do not use comma separators
- examples:
  - `1.2K -> 1200`
  - `54K -> 54000`
  - `1M -> 1000000`

## Mail1 Write Rules

This workflow uses mail, not DM.

Therefore:

- write `Mail1发送 = Y`
- write `Mail1 回复 = ""`
- do not write `DM 发送状态`
- do not write `DM 回复状态`

If a future source file also carries reply truth:

- that belongs to a separate reply workflow
- do not silently overload this append workflow

## Backup Contract

Before every apply run:

1. read live Feishu sheet
2. export local `xlsx` backup
3. save backup into current `workbench/{YYYY-MM-DD}/`
4. stop before write if backup fails

Required naming style:

- `feishu_mail1_master_backup_{YYYY-MM-DD}_{HHMMSS}.xlsx`

## Recommended Execution Order

1. confirm source CSV and final creator batch
2. confirm Gmail drafts were created successfully
3. read live Feishu schema and header
4. dry-run dedupe against cloud master
5. show:
   - total source rows
   - cloud duplicates
   - rows to append
   - field mapping preview
6. wait for user confirmation
7. create local `xlsx` backup
8. append new rows only
9. return sync stats

## Dry Run Contract

The dry-run output should clearly show:

- target URL
- target `sheet_id`
- target header
- append candidate count
- skipped duplicate count
- preview CSV path
- mapped values for at least a few sample rows

Dry-run must not write any Feishu cell.

## Apply Contract

Apply mode should:

1. write only the append block at the bottom
2. preserve all existing rows
3. preserve teammate notes, colors, and formatting on old rows
4. preserve blank `Mail1 回复`
5. write `Mail1发送 = Y` for confirmed rows only

## Stats Contract

After each successful apply, return:

- `表格一共多少账号`
- `今日新增多少账号`
- `Mail1发送 一共多少`
- `Mail1发送 今日新增多少`
- `Mail1 回复 一共多少`
- `Mail1 回复 今日新增多少`

Definitions:

- total accounts: target rows where `账号ID` is non-empty
- today new accounts: rows appended in this run
- total `Mail1发送`: target rows where `Mail1发送 = Y`
- today new `Mail1发送`: appended rows where `Mail1发送 = Y`
- total `Mail1 回复`: target rows where `Mail1 回复 = Y`
- today new `Mail1 回复`: appended rows where `Mail1 回复 = Y`

## Runtime Parameter Rule

For the current script:

- `--write-date` controls the actual value written into Feishu column `分区`
- `--source-date` is optional audit metadata for the source batch
- never use `--source-date` as the first-column value

## Guardrails

- Never append before user confirmation after draft creation
- Never rewrite existing rows in this workflow
- Never treat `Mail1发送` as `DM 发送状态`
- Never write `Mail1 回复 = Y` in this workflow by default
- Never guess a field if the target schema has changed; read live header first
- If the live header no longer includes `Mail1发送`, stop and re-map before write

## Implementation Note

Current `WF_feishu_X_DM_append.md` and its base script are centered on `DM 发送状态` / `DM 回复状态`.

This new workflow establishes a separate contract for `Mail1发送` / `Mail1 回复`.

That means the actual runtime should either:

1. add `Mail1` schema aliases into the existing Feishu incremental sync path, or
2. create a dedicated `Mail1` append variant under:
   - `scripts/feishu_master_incremental_sync/`

Until that alias layer exists, do not assume the old DM workflow can safely write this sheet unchanged.
