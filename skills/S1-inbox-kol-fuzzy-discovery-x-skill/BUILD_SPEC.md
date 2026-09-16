---
tags: [spec, build-log, x, kol, skill, execution]
date: 2026-04-10
status: active
---

# X KOL Discovery Build Spec

这份文档用于把当前 X skill 的成熟执行方式固定成一个根目录级 `BUILD_SPEC.md`。  
它不是取代现有 `WF_Int.md / QUERY_LIBRARY.md / WF/*`，而是把这些分散规则汇总成一个总说明，方便和 `YouTube / TikTok / Instagram` 保持一致命名。

## 1. 总目标

X 这条链路的目标是：

1. 接收一个模糊的 topic / brand / tool brief
2. 先搜大量相关热帖
3. 从热帖反推背后的 creator
4. 用 `L2 / L3 / S2` 收口成可继续外联的标准表

也就是：

`search-first, hot-post-led KOL mining`

不是：

- 平台总榜采集
- 直接搜 creator 名单
- 一上来就写 coldmail

## 2. 当前成熟骨架

X skill 当前已经沉淀出的主骨架是：

- `WF_Int -> QUERY_LIBRARY -> spec -> batch pipeline`
- `L1 -> L2 -> L3 -> S2 Cold`
- `merge / dedupe / obvious-org review`
- 如用户明确继续，再进入 `Mail1 / 3.2 fill`

其中最关键的成熟规则是：

- `QUERY_LIBRARY` 先于 spec
- `L2` 前先过 `views gate`
- `L2 provider` 前先查 `master`
- `L3` 前先过 `followers gate`
- `S2` 只保留标准交付列
- `Mail1` 字段从 `S2 base` 才进入 CSV

## 3. 当前默认执行顺序

1. 用 `WF_Int.md` 做 intake
2. 在 `QUERY_LIBRARY.md` 注册或复用 query names
3. 生成当天 spec / plan / allocation / todo
4. 跑 `run_batch_pipeline.py`
5. 产出 `L1 candidates`
6. 跑 `L2 enrichment`
7. 跑 `L3 shortlist`
8. 跑 `L3 -> S2 cold mapping`
9. 多 batch 时跑 `run_merge_s2_deliverables.py`
10. 合并后先做明显机构号复核
11. 用户明确确认后，才继续 `Mail1 / 3.2`

## 4. 各层职责

### L1

目标：

- 搜热帖
- 留下关键词命中证据
- 聚合 creator
- 做第一轮流量筛选

当前关键门槛：

- `max_views >= 5000`

L1 最重要的字段是：

- `theme_text`
- `creator_handle`
- `top_content_url`
- `matched_queries`
- `matched_content_count`
- `max_views`

### L2

目标：

- 补齐 X profile
- 补齐粉丝数
- 补齐 bio / 外链 / 联系线索
- 形成可判断 creator table

当前默认 provider：

- `ScrapeCreators Twitter profile`

当前门槛：

- 只有通过 `views gate` 且不在 `master` 里的账号，才进入 L2

### L3

目标：

- 只做判断和 shortlist
- 输出 `keep / review / drop`

当前门槛：

- `followers_count >= 1000`

### S2

目标：

- 形成标准 cold outreach 底稿
- 为 merge 和后续 `Mail1` 做准备

当前规则：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `Mail1` 列从 `S2 base` 开始进入

## 5. Query 设计规则

X skill 最成熟的一层就在 query 设计，所以这里固定几个原则：

- `QUERY_LIBRARY.md` 是唯一 query 注册表
- 所有正式执行的 `Query Name` 必须先写进 library
- 不允许先在 spec 里发明 `Query Name` 再回填 library
- topic 新增时，先扩 library，再生成 spec，再执行 batch

也就是说，正确顺序必须是：

`QUERY_LIBRARY -> spec -> batch run`

## 6. Master 去重设计

X 的成熟经验同样是：

- 去重不能等到 merge
- 最省成本的去重点在 `L2` 前

固定顺序：

1. `L1 candidates`
2. `views gate`
3. `check discovery master`
4. 只对 net-new creator 调 L2 provider
5. 本批进入 L2 的账号写回 master

## 7. workbench 与 deliverables

X 的成熟分层是：

### workbench

放所有过程文件：

- raw
- runlog
- audit
- L1 / L2 / L3 / S2 中间稿
- merge 中间稿

### deliverables

只放最终交付：

- `【S2_cold】..._merged_final.csv`

## 8. 机构号复核

X 这条线还有一个成熟经验必须保留：

- 脚本只能做保守初筛
- merge 后必须再做一次 `LLM / 人工 obvious-org review`

原因：

- `team / ai / lab / media / community / studio` 这类词会误伤个人号
- 但品牌、媒体、项目官方账号又必须在封板前清掉

所以：

- `suspected_org_rows` 只是候选池
- 最终封板前必须再复核一次

## 9. Mail1 进入时点

当前 X 的成熟规则已经明确：

- `Mail1` 不进入 `L1 / L2 / L3`
- 从 `L3 -> S2 base mapping` 开始建列

预留列包括：

- `Mail1发出状态`
- `Mail1_Hook`
- `Mail1_Greeting_Name`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`

而真正填充正文的 authoritative 流程在：

- `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
- 外部 `S2-ag-gmail-bulk-drafts` skill 的 `3.2`

## 10. 当前推荐阅读顺序

1. `SKILL.md`
2. `WF_Int.md`
3. `QUERY_LIBRARY.md`
4. `WF/Lx-Field-Matrix_x_kol_csv.md`
5. `WF/L1-WF_x_kol_discovery_csv.md`
6. `WF/L2-WF_x_kol_enrichment_csv.md`
7. `WF/L3-WF_x_kol_selection_csv.md`
8. `WF/L3-WF_to-S2-cold-outreach-mapping.md`
9. `WF/S2-WF_merge-deliverables-and-dm-3.2.md`

## 11. 当前结论

X skill 现在已经是最成熟的参考父本之一：

- query 设计最成熟
- batch 编排最成熟
- merge / org review / Mail1 handoff 最成熟

所以它的 `BUILD_SPEC.md` 主要作用不是补功能，而是把成熟经验固定成和 `YT / TT / INS` 一样的根目录命名。
