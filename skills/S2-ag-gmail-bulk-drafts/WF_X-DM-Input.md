# WF_X-DM-Input

> Purpose: Rockbase X DM operator workflow. Open each target in AdsPower, enter the DM window, paste `Mail1_Content V1`, and stop before sending.

## 1. Use Case

Use this workflow when an S2 cold DM CSV already has `Mail1_Content V1` filled and the operator asks to:

- continue the next `5` rows
- open X profiles in AdsPower
- enter the DM window
- paste the DM content into the input box
- write back `备注` if DM is unavailable

This workflow is business-owned by `S2-ag-gmail-bulk-drafts` because it sits after DM template fill and before manual sending.

The low-level AdsPower browser driver currently lives in:

```text
${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js
```

## 2. Safety Rules

- Default behavior must never send the DM.
- Sending requires an explicit `--send` flag and explicit user instruction.
- Each selected row should open in its own browser tab when processing a batch.
- If the script returns `no_dm_button`, write `DM 没有开通` to `备注`.
- If the script returns `dm_opened_but_no_input_found`, treat it as `DM 没有开通` unless visual inspection shows a temporary page issue.
- Any CSV writeback must first create a physical backup under `Agency/list-bak/{YYYY-MM-DD}/`.

## 3. Standard Command

Single row:

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --row 64
```

Five-row batch, each in a separate tab:

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --rows 67-71
```

Only use this if the user explicitly asks to send:

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --row 64 \
  --send
```

## 4. Writeback Command

When a target cannot receive a DM:

```bash
python3 ".agent/skills/S2-ag-gmail-bulk-drafts/scripts/x/apply_manual_dm_notes.py" \
  --input "/absolute/path/to/dm-ready.csv" \
  --set @handle="DM 没有开通" \
  --backup-root "Agency/list-bak"
```

## 5. Status Interpretation

- `pasted_not_sent`: success; DM content is in the input box and was not sent.
- `sent`: sent only because `--send` was explicitly provided.
- `no_dm_button`: DM is unavailable; write back `DM 没有开通`.
- `dm_opened_but_no_input_found`: usually unavailable or blocked DM; write back `DM 没有开通` unless the visible page suggests a transient load issue.
- `error`: stop and report the exact error.

## 6. Operator Loop

1. Identify the next `5` CSV sheet rows.
2. Run `x_dm_input.js --rows START-END`.
3. Keep all successful `pasted_not_sent` tabs open for operator review.
4. Write back `DM 没有开通` for unavailable DMs.
5. Report handles and statuses to the user.

## 7. Proven Tests

- `2026-04-07`: `@beginbot`, row `64`, pasted into DM input and stopped before sending.
- `2026-04-07`: rows `67-71`, five independent tabs, all `pasted_not_sent`.
- `2026-04-07`: rows `72-76`, four `pasted_not_sent`; `@genai_is_real` returned `dm_opened_but_no_input_found` and was written back as `DM 没有开通`.
