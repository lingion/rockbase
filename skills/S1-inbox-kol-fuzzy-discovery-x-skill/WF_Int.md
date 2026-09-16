---
description: "[Runner] X KOL fuzzy discovery 总工作流 | 只负责编排 intake、query library、batch execution、S2 workbench outputs、multi-batch merge 与 3.2 DM fill handoff。"
---

# WF_Int

> 这是 `S1-inbox-kol-fuzzy-discovery-x-skill` 的唯一默认启动入口。  
> `S1` 只是历史目录名；当前默认业务终点是 `S2 Cold(workbench) + merged final deliverable`，必要时继续进入 `3.2 cold DM fill`。  
> 本文件只做总 runner，子流程细节统一放到 `WF/` 目录。

## 一、当前默认闭环

默认链路：

```text
自然语言需求
-> Intake
-> QUERY_LIBRARY 更新
-> 当天 spec
-> Implementation Plan
-> Batch Allocation Table
-> Todo List
-> 用户确认
-> run_batch_pipeline.py
-> L1 candidates
-> L2 enriched
-> L3 shortlist
-> S2 cold (workbench only)
-> 如有多 batch：merge / dedupe / org filter / follower desc sort
-> deliverables/{YYYY-MM-DD}/【S2_cold】..._merged_final.csv
-> STOP：向用户汇报合并结果并等待确认
-> 如需触达：读取 S2-ag-gmail-bulk-drafts 的 3.2 模板并填入 Mail1 cold DM
```

已经接上的部分：

- `run_batch_pipeline.py` 默认会执行 `L3 -> S2(workbench only)`
- `S1 inbox` 不是默认产物；只有显式 `--emit-legacy-s1` 才输出
- 多 batch 合并由 `run_merge_s2_deliverables.py` 承接

仍需特别注意的部分：

- `3.2 cold DM fill` 的 authoritative template 在外部 skill：`../S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`
- 本 skill 只负责把 S2 数据准备好并触发/记录这一步，不要在多个地方复制维护正文模板

## 二、子工作流位置

根目录只保留入口与核心索引：

- `SKILL.md`
- `README.md`
- `WF_Int.md`
- `QUERY_LIBRARY.md`
- `UPGRADE_LOG.md`

子工作流统一在：

- `WF/README.md`
- `WF/WF_Spec.md`
- `WF/L1-WF_x_kol_discovery_csv.md`
- `WF/L2-WF_x_kol_enrichment_csv.md`
- `WF/L3-WF_x_kol_selection_csv.md`
- `WF/L3-WF_to-S2-cold-outreach-mapping.md`
- `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
- `WF/L3-WF_to-S2-DM-fill.md`
- `WF/Lx-Field-Matrix_x_kol_csv.md`
- `WF/legacy/L3-WF_to-S1-inbox-mapping-full.md`

## 三、Intake 最小字段

Friday 启动后，应优先确认这些字段。若用户已经给出明确值，不要重复追问。

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `KOL平台` | 本次找哪一个平台 | `X` |
| `语言` | 目标语言区 | `en` |
| `热度 / 阅读量` | 热帖阈值 | `5000+ views` |
| `粉丝量` | 进入 shortlist 的最低粉丝量 | `1000+ followers` |
| `帖子覆盖时间` | 搜索最近多久的帖子 | `过去 7 天` |
| `搜索关键词` | 核心 topic / brand / tool | `Claude Code` |
| `执行节奏` | 今天打算跑几次、几个 cookies | `2 cookies，每个 3 batch` |
| `最终动作` | 是否只要 S2，还是继续填 DM | `合并后填 3.2 cold DM` |

原则：

- 缺少关键字段时才问
- 用户目标明确时直接执行，不让用户替我们写 spec
- 多 cookies / 多 batch 时必须生成 `Batch Allocation Table`

## 四、Runner 标准步骤

### Step 1. 更新 QUERY_LIBRARY

先看：

- `QUERY_LIBRARY.md`

规则：

- topic 已存在：复用并微调
- topic 不存在：在 Part 2 新建 topic query matrix
- 有新方法论：回写 Part 1
- `Batch Allocation Table` 里的所有 `Query Names` 必须先在 `QUERY_LIBRARY.md` 的 Part 2 中存在
- 严禁先在 plan / spec 里临时发明 `Query Names`，再事后回填 library
- 新增 `Query Name` 的正确顺序必须是：先写入 `QUERY_LIBRARY.md` Part 2，再生成 spec / plan / allocation，再执行 batch
- 若 spec 里的 `search_queries[].name` 未先出现在 `QUERY_LIBRARY.md`，pipeline 应在跑前直接报错，而不是先执行再补文档
- 新 topic 必须按 Part 2 现有 topic 编号顺延；非 topic 说明不要占用 `2.2.x` 编号
- `QUERY_LIBRARY.md` 更新完成并自检后，才能进入 Step 2

### Step 2. 生成当天执行设计

在 `workbench/{YYYY-MM-DD}/` 生成：

- spec JSON
- implementation plan
- batch allocation table
- todo

`Batch Allocation Table` 必须包含：

- `Cookie`
- `Batch`
- `Query Names`
- `Primary Goal`
- `Fallback Rule`
- `Stop / Continue Rule`

边界：

- `batch1 / batch2 / batch3` 表示 discovery round
- `chunk01 / chunk02 / chunk03` 只表示 Layer2 provider 内部分块

### Step 3. 执行每个 batch

默认入口：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_batch_pipeline.py \
  --run-date 2026-04-07 \
  --batch batch1 \
  --spec workbench/2026-04-07/spec.json
```

如需指定 cookie：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_batch_pipeline.py \
  --run-date 2026-04-07 \
  --batch batch4 \
  --spec workbench/2026-04-07/spec.json \
  --cookie-profile steven20492198
```

完成后必须核对：

- `workbench/{YYYY-MM-DD}/x_kol_S2_cold_{batch}_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_S2_mapping_runlog_{batch}_{YYYY-MM-DD}.json`

### Step 4. 多 batch 合并

当同一天跑了多个 batch，并且用户要一张总表时，执行：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07
```

默认输出：

- `workbench/{YYYY-MM-DD}/x_kol_S2_merged_filtered_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_S2_merged_filter_audit_{YYYY-MM-DD}.json`
- `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_final.csv`

默认规则：

- 只读取 `workbench/{YYYY-MM-DD}/x_kol_S2_cold_batch*_{YYYY-MM-DD}.csv`
- 按 `账号ID` / `账号链接` 去重
- 脚本层只按明确 handle denylist 做保守初筛，不把它当作最终机构号判断
- `suspected_org_rows` 只是候选池；最终“明显机构号去除”必须进入 `LLM / 人工复核`
- 不移除 300k+ 个人头部账号
- 按 `粉丝数` 从高到低排序

### Step 4.1 明显机构号 LLM / 人工复核

在 `run_merge_s2_deliverables.py` 完成后，正式封板前必须做一次 `obvious org review`。

执行原则：

- 这一步不应只依赖脚本，因为脚本只能做保守 denylist 和关键词审计
- 这一步默认由 `LLM judgment + operator quick review` 完成
- 若用户未特别要求保留机构号，则应主动完成这一步，而不是停留在 `suspected_org_rows`

复核标准：

- `官方品牌 / 产品 / 公司 / 组织 / 媒体 / 项目官方账号` 直接视为机构号，应该移除
- `账号名 + bio + handle` 明显指向品牌、公司、基金会、实验室、媒体、newsletter、newsroom、VC、社区官方账号时，应移除
- 虽然命中 `inc / labs / media / community / studio / company` 等词，但主体明显是个人创作者时，不应仅靠词命中删除
- 若账号的主要身份是“个人”，只是附带公司头衔、工作单位或项目 affiliation，默认保留
- 对边界模糊账号，进入 `review`，不要强删

建议纳入标准的 `明显机构号` 判断维度：

1. `账号主体是谁`
   - 是公司 / 品牌 / 官方产品 / 项目 / 组织本身，还是一个具体个人
2. `账号运营目的`
   - 主要在发官方公告、产品更新、招聘、品牌传播、媒体分发，通常判为机构号
3. `命名与 handle 形态`
   - 直接使用品牌名、产品名、组织名、`newsroom`、`official`、`hq`、`io`、`foundation` 等，更偏机构号
4. `bio 的第一身份`
   - 第一身份若是 company / startup / lab / fund / media / newsletter / community official，更偏机构号
5. `个人性是否足够强`
   - 有明确真人姓名、第一人称表达、稳定个人输出、长期个人品牌痕迹，则更偏个人号

输出要求：

- 复核后应产出一版 `manual-clean final`
- 必须记录：
  - removed obvious org rows
  - kept but reviewed rows
  - remaining suspected rows
- 对用户汇报时，应同时给出：
  - system merged count
  - manual clean count

强制确认门：

- 合并、去重、脚本初筛、LLM/人工明显机构号复核完成后必须暂停。
- 必须向用户汇报：
  - raw rows
  - deduped rows
  - removed org rows
  - kept rows
  - suspected org rows
  - 合并 CSV 路径
- 若用户确认今天以该 merged 表封板，则必须把 final merged CSV 复制进 `deliverables/{YYYY-MM-DD}/`
- 只有用户明确说“继续 / 进入 3.2 / 填 DM / 可以填”之后，才能执行 Step 5。
- 如果用户只说“完成到排序”，默认停在合并 CSV，不进入 DM fill。

如需额外移除机构号：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07 \
  --org-handle @example_org
```

如需删除关键词可疑机构号，必须显式加：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07 \
  --remove-suspected-orgs
```

默认不要开启它，因为 `team / ai / lab / media / code / daily / community` 等词会误伤个人品牌和内容账号。

### Step 5. 3.2 Cold DM Fill

Step 5 是 gated step，不自动执行。

只有在 Step 4 汇报后用户明确确认继续填 DM，才使用：

- `../S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`
- section `3.2 Approved DM Template - Launch / Media Kit First`

执行口径：

- 先读外部 `3.2`，不要在本 skill 复制改写正文
- 生成当天 config 到 `workbench/{YYYY-MM-DD}/`
- 小样本通过后再全量
- 填充目标：
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Content V1`
  - `DM_Angle`
  - `DM_*_Variant`

如果 Codex / LLM 子进程不可用：

- 可以使用 deterministic fallback
- 必须写入 audit / summary
- 必须说明哪些行是 fallback 补齐

最终产物应复制到：

- `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_filtered_dm_3.2.csv`

deliverables 目录约束：

- `deliverables/{YYYY-MM-DD}/` 只放正式 CSV
- 不要把 audit / summary / json 放进 `deliverables`
- audit / summary / config 统一留在 `workbench/{YYYY-MM-DD}/`

### Step 6. 完成校验

一个当天任务要算完成，至少检查：

- 每批 `S2 mapping runlog` 存在
- 每批 `deliverables` 存在
- 如有多批总表：合并 audit 存在
- 如进入 DM：`Mail1_Greeting_Name / Mail1_Hook / Mail1_Content V1` 全部非空
- final deliverable 存在
- 写 handoff 到 `workbench/handoff/`

## 五、过时 / Legacy 处理

已降级：

- `WF/WF_Spec.md`: 旧 spec-first 入口，仅兼容历史流程
- `WF/legacy/L3-WF_to-S1-inbox-mapping-full.md`: 旧 `L3 -> S1` 详细映射，只在历史表兼容时看
- `legacy/L3-WF_to-S1-inbox-mapping.md`: 短说明，仅保留跳转与历史备注
- `WF/L3-WF_to-S2-DM-fill.md`: 早期 in-skill DM fill 规则，当前 `3.2` 正文应优先参考外部 `S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`

仍保留但不做默认入口：

- `WF/Lx-Field-Matrix_x_kol_csv.md`: 字段契约索引
- `docs/`: 架构与历史开发记录

不要删除：

- `QUERY_LIBRARY.md`: query 方法论与 topic pack
- `WF/S2-WF_merge-deliverables-and-dm-3.2.md`: 当前补上的多批合并与 3.2 handoff 子流程

## 六、修改原则

以后改流程时：

- 总流程顺序改 `WF_Int.md`
- L1 细节改 `WF/L1-WF_x_kol_discovery_csv.md`
- L2 细节改 `WF/L2-WF_x_kol_enrichment_csv.md`
- L3 细节改 `WF/L3-WF_x_kol_selection_csv.md`
- L3 到 S2 映射改 `WF/L3-WF_to-S2-cold-outreach-mapping.md`
- 多 batch 合并与 3.2 handoff 改 `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
- cold DM 正文模板改 `../S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`
