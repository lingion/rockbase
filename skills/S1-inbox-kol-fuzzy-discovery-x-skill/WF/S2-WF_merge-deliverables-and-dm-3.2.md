---
description: "[Workflow] S2 multi-batch merge and 3.2 DM fill handoff | 目标：把多批 workbench S2 合并、去重、机构过滤、排序，并交给 3.2 cold DM 模板填充。"
---

# S2-WF_merge-deliverables-and-dm-3.2

> 用途：承接多个 `batchN` 已经产出的 `workbench S2`。  
> 它不重新搜索，不重新打分，只负责把多批净新增 S2 表收口成一张 DM-ready 表。

## 一、触发条件

当当天跑了多个 batch，并且用户需要进入手动 X DM / Gmail draft 前，应启动本工作流。

典型场景：

- `batch1-batch6` 已分别产出 `workbench/{YYYY-MM-DD}/x_kol_S2_cold_batch*_{YYYY-MM-DD}.csv`
- 用户需要一张合并后的总表
- 需要按 `粉丝数` 降序
- 只移除机构号，不移除 300k+ 个人头部账号
- 需要使用 `S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md` 的 `3.2` 内容填入 cold DM

## 二、输入

- `workbench/{YYYY-MM-DD}/x_kol_S2_cold_batch*_{YYYY-MM-DD}.csv`
- `S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md` section `3.2 Approved DM Template - Launch / Media Kit First`

## 三、输出

- workbench 合并底稿：
  - `workbench/{YYYY-MM-DD}/x_kol_S2_merged_filtered_{YYYY-MM-DD}.csv`
- workbench 合并审计：
  - `workbench/{YYYY-MM-DD}/x_kol_S2_merged_filter_audit_{YYYY-MM-DD}.json`
- final merged deliverable：
  - `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_final.csv`
- DM fill audit / summary：
  - `workbench/{YYYY-MM-DD}/x_kol_S2_merged_dm_fill_summary_{YYYY-MM-DD}.json`

deliverables 目录约束：

- `deliverables/{YYYY-MM-DD}/` 只放唯一正式 merged final CSV
- 不放 audit / summary / json
- audit / summary / config 一律留在 `workbench/{YYYY-MM-DD}/`

## 四、合并规则

1. 只读取 `workbench/{YYYY-MM-DD}/x_kol_S2_cold_batch*_{YYYY-MM-DD}.csv`，不读取已经合并过的 `merged` 文件。
2. 按 `账号ID` 去重；若 `账号ID` 缺失，则按 `账号链接` 去重。
3. 默认只移除明确机构号。
4. 脚本层只做保守机构号初筛，不把脚本结果视为最终机构判断。
5. 合并后必须补一轮 `明显机构号 LLM / 人工复核`，再决定 final merged。
6. 不再自动移除 `300k+` 或国际头部个人账号。
7. 最终按 `粉丝数` 降序；相同粉丝量时按 `账号ID` 升序。

完成到排序后必须暂停：

- 不要自动进入 `3.2 DM Fill`。
- 先向用户汇报合并结果与 CSV 路径。
- 等用户明确确认“继续填 3.2 DM”之后，才进入正文填充。
- 如果用户只要求“合并 / 去重 / 排序”，本工作流停在合并 CSV。
- 若用户确认今天以当前总表封板，则必须先完成 `明显机构号 LLM / 人工复核`，再把 final merged CSV 写入 `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_final.csv`

机构号过滤必须保守：

- 默认只按明确 `org handle denylist` 删除。
- 宽泛关键词只进入 `suspected_org_rows` 审计，不自动删除。
- 不允许用 `team / ai / lab / media / code / daily / community` 这类词直接删除，因为会误伤个人品牌和内容账号。
- 如果确实要删除可疑机构号，必须显式传 `--remove-suspected-orgs`，或更推荐用 `--org-handle @xxx` 精确追加。

明显机构号复核标准：

1. 若账号主体本身是品牌、产品、公司、基金会、实验室、媒体、newsroom、newsletter、社区官方号，直接移除。
2. 若 handle / 名称 / bio 的主要指向是组织，而不是具体个人，直接移除。
3. 若账号以官方公告、品牌传播、产品更新、活动宣传为主，直接移除。
4. 若账号虽然命中 `inc / labs / media / community / studio / company`，但主体是明确个人创作者，则默认保留。
5. 对模糊账号，进入 review，不因单一关键词误杀。

## 五、执行脚本

从 skill 根目录执行：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07
```

如需临时追加机构号：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07 \
  --org-handle @example_org
```

如需仅查看可疑机构号，不删除，默认运行即可，审计里会写：

- `suspected_org_rows`
- `suspected_org_rows_detail`

如需强制删除关键词可疑机构号，必须显式执行：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-07 \
  --remove-suspected-orgs
```

## 六、3.2 DM Fill 规则

这是 gated step。

进入条件：

- 已完成合并、去重、机构过滤、粉丝降序排序。
- 已把合并结果汇报给用户。
- 用户明确确认继续进入 `3.2` cold DM fill。

当前 `3.2` 正文模板的 authoritative source 是外部 skill：

- `../S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`

默认使用：

- `3.2 Approved DM Template - Launch / Media Kit First`
- CTA 固定：`media_kit_or_whatsapp`

语言规则：

- `语言=中文` 的行，必须使用中文 DM subject 与中文正文
- `语言=英语` 的行，必须使用英文 DM subject 与英文正文
- `语言=其他语言` 的行，当前统一走英文 DM
- 这里的判断依据是最终 S2 表里的 `语言` 字段，不是模型自由判断
- 因此 3.2 DM fill 在执行前，必须先确认 `语言` 列已稳定

推荐执行顺序：

1. 先从 `WF_Cold DM Template.md` 读取 `3.2`。
2. 生成当天 config：
   - `workbench/{YYYY-MM-DD}/cold_dm_workflow_config_3.2_media_kit_first_{YYYY-MM-DD}.json`
3. 先跑小样本。
4. 样本通过后再跑全量。
5. 若 LLM / Codex 子进程不可用，允许用 deterministic fallback 补齐，但必须写入 summary 说明。

## 七、完成判定

本工作流完成必须满足：

- 合并 CSV 行数可解释
- 去重数量可解释
- 机构号移除清单可审计
- final merged CSV 已复制到 `deliverables/{YYYY-MM-DD}/`
- `Mail1_Greeting_Name` 填满
- `Mail1_Hook` 填满
- `Mail1_Content V1` 填满
- final CSV 已复制到 `deliverables/{YYYY-MM-DD}/`
