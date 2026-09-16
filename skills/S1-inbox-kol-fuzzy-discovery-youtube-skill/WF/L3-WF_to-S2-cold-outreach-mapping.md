---
description: "[Workflow] Map YouTube L3 shortlist to S2 outreach export."
---

# L3-WF_to-S2-cold-outreach-mapping

## 输出目标

把 `L3 shortlist` 转成 agency 可以继续外联的 `S2 cold outreach` 表。

## 关键结论

参考 X 的成熟 workflow，`Mail1` 相关字段不是在 `S2 merge` 才新增，而是在 `L3 -> S2 base mapping` 这一步就必须进入 CSV。

执行顺序：

1. `L3 shortlist`
2. `obvious-org + dirty-contact hygiene`
3. `contact / email enrichment for missing rows`
4. `L3 -> S2 base mapping`
5. `S2 batch base export`
6. `S2 merge`
7. `Mail1 / 3.2 DM fill`

`Mail1 / 3.2 DM fill` 的默认 workflow 固定为：

- 相对路径：`.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`
- YouTube 侧直接转调 runner：`src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`

边界规则：

- `L1 / L2 / L3` 不加入 `Mail1` 字段
- 从 `S2 base mapping` 开始，CSV 必须预留 `Mail1` 列
- `S2 merge` 只保留这些列，不负责首次建列
- 真正填写 `Mail1_Greeting_Name / Hook / Subject / Content` 是 merge 后的 DM fill 阶段

## Contact / email enrichment gate

在 `L3 shortlist` 进入 `S2 base mapping` 前，应先补一轮 missing email。

规则：

- 目标是补 `contact_value`，不是因为缺 email 就删人
- 没拿到 email 的行也可以进入 `S2`，但 `联系方式` 留空
- 优先复用现有 `L2 enriched` 中已经抓到的：
  - `contact_value`
  - `contact_note`
  - `external_links`
  - `contact_signals`
- 若仍为空，再补：
  1. `scrapecreators` fallback 结果
  2. `contact page crawl`
  3. `augment_layer2_contact_crawl.py` 增量补抓

建议入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/augment_layer2_contact_crawl.py \
  --input-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_{YYYY-MM-DD}.csv \
  --output-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_contact_crawl_{YYYY-MM-DD}.csv \
  --timeout-seconds 3 \
  --max-urls-per-creator 4
```

## 默认映射

- `creator_handle` -> `Handle`
- `display_name` -> `Name`
- `platform` -> `Platform`
- `channel_url` / `profile_url` -> `Profile URL`
- `contact_value` -> `联系方式`
- `contact_note` -> `联系方式备注`
- `external_links` -> `外链__平台抓取`
- `bio` -> `Profile Summary`
- `sample_contents` / `top_content_title` -> `Content Evidence`
- `decision_reason` -> `Why Now`
- `matched_queries` -> `Discovery Query`

联系方式字段规则必须写死：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `外链__平台抓取 = website / link page / newsletter / socials`
- `contact_signals` 不能直接映射到 `联系方式`

## 默认输出

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_cold_{batch}_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_mapping_runlog_{batch}_{YYYY-MM-DD}.json`

默认情况下，batch 级 `S2` 只写入 `workbench/`。

当前规则已经收紧为：

- `deliverables/` 不再接收 batch 级 `S2`
- `deliverables/` 不再生成 batch 级 `netnew`
- `deliverables/` 只保留 merge 后的 final 文件

默认入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_l3_to_s2_mapping.py \
  --input-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_shortlist_{batch}_{YYYY-MM-DD}.csv \
  --run-date {YYYY-MM-DD} \
  --batch {batch}
```

当前最小实现说明：

- 在 YouTube 的 `L3 runner` 尚未独立实现前，允许先使用 `L2 shortlist` 作为 `S2 base mapping` 的输入
- 只要行内已经有 `recommended_action=keep/review`，就允许进入 `S2`

## Hygiene Gate

YouTube 在 `S2` 前必须走一次保守清洗，逻辑借鉴 X skill 的 `merge + obvious-org review`：

- 默认只自动删除：
  - 明确机构号
  - 明显脏邮箱
- 宽泛可疑机构：
  - 只进入 audit
  - 不因单一关键词自动删除
- clean 之后的 final CSV 才允许进入 Gmail / Feishu

建议入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_s2_hygiene_filter.py \
  --input-csv workbench/{YYYY-MM-DD}/youtube_kol_L3_final*_with_email*.csv \
  --run-date {YYYY-MM-DD}
```

dirty-contact 规则：

- `联系方式` 只接受可用 email
- 资源文件后缀伪邮箱，如 `*.png / *.jpg / *.avif`，直接 drop
- telemetry / builder junk，例如 `*.sentry.io`，直接 drop
- 修不回合法邮箱的行，不进 S2

obvious-org 规则：

- 默认只按明确 `channel_id / public handle / display name denylist` 删除
- 关键词可疑机构只写进审计
- 如需 aggressive 删除，必须显式传 `--remove-suspected-orgs`

## Merge 约定

`S2 base mapping` 之后，默认进入单独的 merge workflow：

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_merged_filtered_{YYYY-MM-DD}.csv`
- `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_youtube_kol_S2_merged_final.csv`

也就是说，正式 `deliverables/` 只保留 merge 后的 final 文件，而不是每个 batch 的中间过程文件。

`S2 merge` 之后进入唯一主表阶段：

- `【S2_cold】{YYYY-MM-DD}_youtube_kol_S2_merged_final.csv` 是唯一 final 主表
- 后续补 email、补历史 EasyKOL overlay、写 `Mail1`、排序、subject 清洗，都直接改这张表
- `workbench merged_filtered` 可以保留过程态，但最终最新状态必须同步回 `merged_final`
- 不允许 merge 之后再平行维护另一份“另一个 final”

merge runner 保护规则：

- merge 默认从 `workbench/{YYYY-MM-DD}/YouTube/` 读取 batch 级 `S2`
- 若已有 `merged_final` 的已填邮箱数更高，runner 默认拒绝覆盖
- 只有明确知道要回退时，才允许使用 downgrade override

收口规则：

- merge runner 直接从 `workbench/{YYYY-MM-DD}/YouTube/` 读取 batch 级 `S2`
- merge runner 写出 final 后，会清理同日期 `deliverables/` 下误留的 `batch*.csv` 与 `*_netnew.csv`

这一步只做：

- 多 batch 合并
- 按 `账号ID` / `账号链接` 去重
- 按 `粉丝数` 排序
- 轻量 obvious-org script 预过滤

这一步不做：

- `Mail1` 建列
- `Mail1` 文案填充

## S2 需要从一开始预留的 Mail1 字段

- `Mail1发出状态`
- `Mail1_Hook`
- `Mail1_Greeting_Name`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`

默认规则：

- 在 `L3 -> S2 base mapping` 时全部建列
- 初次映射时默认留空
- 只有 `Mail1发出状态` 可作为状态机列保留空值
- 文案列的首次填充发生在 `S2 merge` 之后

## DM / code mail 生成依据

`S2` 不应该凭空写 DM。默认只允许使用这些证据：

- `bio`
- `external_links`
- `contact_signals`
- `contact_value`
- `contact_note`
- `content_tags_or_hashtags`
- `sample_contents`
- `top_content_title`
- `matched_queries`
- `decision_reason`

## Mail1 Fill Handoff

`S2 merge` 完成后，默认不在本 workflow 内继续发明邮件模板，而是切换到：

- 相对路径：`.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`

固定衔接规则：

- `Mail1_Greeting_Name`、`Mail1_Hook`、`Mail1_Subject` 的填写规则以该 workflow 为准
- `Mail1_Content V1` 默认采用冻结正文结构，不做自由漂移式改写
- `Mail1_Content V2` 可以更强调 creator fit，但不得改坏统一 CTA
- 若后续同时存在旧命名的 email fill workflow，YouTube skill 一律优先读取 `WF_Cold Mail Run.md`

## 原则

- 只输出 `keep / review`
- 没拿到联系方式则留空，不伪造
- `manual_clean_decision=drop` 的行不允许进入 Gmail / Feishu
- hook 需要能追溯到 `description / tag / content evidence`
- `Mail1` 的文案生成不得早于 `S2`
