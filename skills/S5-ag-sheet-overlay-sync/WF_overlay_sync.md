# WF Overlay Sync

## Purpose

Use this workflow when the user wants to use one structured sheet as the source of truth to overwrite or backfill matching rows in another structured sheet.

Typical requests:

- use A table to update matching rows in B table
- overlay source fields onto master
- map fields first, then write
- write only selected columns back to the target

## Scope

This workflow is for local structured files such as:

- CSV
- Excel-export CSV
- segmented master CSV

It is best when:

- the source and target share stable matching keys
- target row structure should be preserved
- the user wants dry-run, test copy, backup, and controlled write

## Scripts

- main generic overlay script:
  - relative path: `.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py`
  - absolute path: [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py)
- pricing-specialized overlay script:
  - relative path: `.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/overlay_pricing_to_master.py`
  - absolute path: [${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/overlay_pricing_to_master.py](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20420%20Social%20Agency/.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/overlay_pricing_to_master.py)

## Default Process

1. Read source and target structure.
2. Detect real target header row if the master has markers or fake header rows.
3. Build matching strategy, usually:
   - `账号链接`
   - then `账号ID`
4. Produce a dry-run summary first.
5. If risk is non-trivial, write to a test copy first.
6. Before any formal write, create a physical backup.
7. Only overwrite fields that are explicitly allowed by rule.

## Guardrails

- Never trust visual column positions.
- Never skip the mapping stage on unstable tables.
- Never write without a backup.
- Keep protected columns such as `备注` unless the workflow explicitly allows overwrite.
- Keep fill-only columns as fill-only when configured.

## Recommended Overlay Rules For Master KOL Maintenance

Default match priority:

- `账号链接`
- fallback: `账号ID`

Default overwrite fields:

- `频道/作者名称`
- `平台`
- `语言`
- `博主国家`
- `粉丝数`
- `账号类目标签`
- `账号简介`
- `置顶最高播放`
- `近期10条均播`
- `rate（USD$)报价`
- `原价`
- `粉丝受众`
- `粉丝性别`
- `粉丝年龄`

Conflict resolution for freshness-sensitive fields:

- if `语言`, `博主国家`, `粉丝数`, `置顶最高播放`, `近期10条均播` differ between source and target, use the newer project sheet as source of truth
- this freshness rule applies even when the target already contains an older normalized value
- only apply this override to matched rows; do not append unmatched rows unless the task explicitly asks for append

Keep blank / do not write from source unless the task explicitly says otherwise:

- `提报人`
- `提报时间`

Protected master-only fields that should not be overlaid by project sheets:

- `备注`
- `多平台标记`
- `Sample Content`
- `Latest Activity Proof`
- `联系方式`
- `Tag_Section`
- `tag_topics`
- `tag_scenarios`
- `tag_audience`
- `tag_narrative`
- `tag_platform_fit`
- `tag_market`
- `tag_commercial`
- `tag_risk`
- `tag_confidence`

Normalization rules when source sheets come from mixed generations:

- map `提报日期` -> `提报时间`
- map `置顶最高单条播放量` -> `置顶最高播放`
- ignore helper columns such as `CPM`, `利润`, `联系方式备注`, `Unnamed:*`
- when multiple source sheets contain the same creator, run overlay by source recency so the latest validated values win

## Overlay Field Format Constraints

Apply these rules during staging or before formal overlay write, so the target master does not receive mixed formats from different source generations.

| 字段 | 目标格式 | Overlay 处理动作 | 示例 | 红线 |
| :--- | :--- | :--- | :--- | :--- |
| `账号链接` | 规范化 URL | 统一小写域名、去 query、去末尾 `/`、补齐 `www` 后再匹配 | `youtube.com/@abc?si=1 -> https://www.youtube.com/@abc` | 不可用展示文本代替真实链接 |
| `账号ID` | 规范化 handle | 匹配时去掉前导 `@` 并转小写；写回时默认保留目标原值 | `@CreatorX -> creatorx` | 不因 source 脏值强行改坏 target 主键 |
| `频道/作者名称` | 保持 source 最新有效值 | 允许覆盖 | `AI Optimist (Tam Walsh)` | 不靠该字段单独做匹配 |
| `平台` | 标准平台名 | 统一为 `YouTube` / `TikTok` / `Instagram` / `X` 后再写入 | `YT -> YouTube` | 不混用 `YT`、`TT`、`Twitter` 等别名写回 master |
| `语言` | 标准中文语言名 | 先标准化，再允许覆盖 | `English -> 英语` | 无法确认时保留原值，不主观猜测 |
| `博主国家` | 标准中文国别 | 先标准化，再允许覆盖 | `United States -> 美国` | 不主观补写未知国家 |
| `粉丝数` | 纯数字字符串 | 若为 `K/M/B` 紧凑表达则换算为完整数字；若已有纯数字则直接保留 | `1.6M -> 1600000` | 不写成 `K/M`，不加千分位逗号 |
| `置顶最高播放` / `置顶最高单条播放量` | 纯数字字符串或空 | 统一视为同一字段后再写入 master | `12.5K -> 12500` | 不同时保留两种列名，不加千分位逗号 |
| `近期10条均播` | 纯数字千分位或空 | 统一格式后再写入 | `34.8K -> 34,800` | 不保留混乱的 `K/M/纯数字` 混排 |
| `rate（USD$)报价` | `"$"` 数值或保留原结构文本 | 纯数值报价转 `$` + 千分位；多档位文本保留原结构 | `4000 -> $4,000` | 组合报价、区间报价不强行扁平化 |
| `原价` | `"$"` 数值或保留原结构文本 | 与 `rate（USD$)报价` 同规则 | `1800 -> $1,800` | 不把说明性文本误清洗成单一价格 |
| `粉丝受众` / `粉丝性别` / `粉丝年龄` | 可读文本 | 保持 source 中最新可用表达后覆盖 | `美国 35% / 印度 20%` | 不凭空补齐缺失画像 |
| `提报人` | 留空 | overlay staging 时清空，不写回 source 值 | `跃 -> 空` | 本 workflow 默认不回写 |
| `提报时间` | 留空 | overlay staging 时清空，不写回 source 值 | `2026-04-13 -> 空` | 本 workflow 默认不回写 |
| `备注` 及 master 专属标签列 | 保留 target 原值 | 设为 protected，不参与 overlay | `tag_topics` | 除非任务明确授权，否则禁止覆写 |

## Recommended Commands

### Dry Run

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --source-date 'M月D日'
```

### Test Copy

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --source-date 'M月D日' \
  --write-test-copy \
  --diff-report
```

### Formal Write

```bash
python3 '.agent/skills/S5-ag-sheet-overlay-sync/scripts/overlay_sync/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --output 'OUTPUT_CSV' \
  --backup-root 'BACKUP_ROOT' \
  --source-date 'M月D日' \
  --write \
  --diff-report
```

## Best Fit

Choose this workflow when the job is fundamentally:

- row matching
- field overlay
- selective overwrite
- local master maintenance

If the job instead is "read Feishu online master and append only new rows to the bottom while preserving teammate notes and highlights", use `WF_feishu_X_DM_append.md` instead.
